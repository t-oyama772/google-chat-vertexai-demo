import flask
import functions_framework
import os
import vertexai
import uuid
import google.auth
from typing import Any, Mapping
from vertexai.language_models import ChatModel, TextGenerationModel, CodeGenerationModel
from vertexai.generative_models import GenerationConfig, GenerativeModel
from google.cloud import firestore
from datetime import datetime
# from botbuilder.core import (
#     ConversationState,
#     MessageFactory,
#     UserState,
#     TurnContext,
# )
# from botbuilder.dialogs import Dialog
# from botbuilder.schema import Attachment, ChannelAccount
# from helpers.dialog_helper import DialogHelper

# from .dialog_bot import DialogBot

cred, PROJECT_ID = google.auth.default()
service_account_email = cred.service_account_email
print(f'{PROJECT_ID=}')

db = firestore.Client(project=PROJECT_ID)
vertexai.init(project=PROJECT_ID, location="asia-northeast1")
# vertexai.init(project=PROJECT_ID, location="global")
default_model = "gemini-1.5-pro-002"
models_json = [
        {
            "base_model": "Gemini",
            "variations": [
                # {
                #     "name": "gemini-2.0-flash-001",
                #     "description": "優れた速度、ネイティブ ツールの使用、100 万トークンのコンテキスト ウィンドウなど、次世代の機能と強化された機能を提供します"
                # },
                # {
                #     "name": "gemini-2.0-flash-lite-001",
                #     "description": "費用対効果と低レイテンシを重視して最適化された Gemini 2.0 Flash モデル"
                # },
                {
                    "name": "gemini-1.5-pro-002",
                    "description": ""
                },
                {
                    "name": "gemini-1.5-flash-002",
                    "description": ""
                },
                {
                    "name": "text-embedding-005",
                    "description": ""
                }
            ]
        },
]

# Google Cloud Function that responds to messages sent in
# Google Chat.
#
# @param {Object} req Request sent from Google Chat.
# @param {Object} res Response to send back.
@functions_framework.http
def hello_chat(req: flask.Request) -> Mapping[str, Any]:
  if req.method == "GET":
    return "Hello! This function must be called from Google Chat."

  request_json = req.get_json(silent=True)
  thread_name = request_json["message"]["thread"]["name"]
  thread_id = thread_name.split("/")[-1]

  print(request_json)

  # メッセージが送信されたチャンネルが Google Chat か teams かを判定
  if "configCompleteRedirectUrl" in request_json:
    if "https://chat.google.com/" in request_json["configCompleteRedirectUrl"]:
      print("*** configCompleteRedirectUrl={}".format(request_json["configCompleteRedirectUrl"]))
      chat_platform = "google_chat"
    elif "channelId" in request_json:
        if request_json["channelId"] == "msteams":
            chat_platform = "teams"
        else:
            chat_platform = "unknown"
    else:
      chat_platform = "unknown"
  elif "cardsV2" in request_json["message"]:
    chat_platform = "google_chat"
  else:
    chat_platform = "unknown"

  print("*** chat_platform={}".format(chat_platform))
  print("*** thread_id={}".format(thread_id))

  if request_json["type"] == "ADDED_TO_SPACE" or request_json["type"] == "MESSAGE":
    user_email = request_json["user"]["email"]
    prompt = request_json["message"]["text"]
    user_id = request_json["user"]["name"]
    user_name = request_json["user"]["displayName"]
    if chat_platform == "google_chat":
       user_id = user_id.split("/")[-1]
    print("*** user_id={}".format(user_id))

    # メンションされた場合
    if "annotations" in request_json["message"]:
      mention = "@" + request_json["message"]["annotations"][0]["userMention"]["user"]["displayName"] + " "
      print("*** mention={}".format(mention))
      # プロンプトからメンションを削除
      prompt = prompt.replace(mention, "").strip()
  elif request_json["type"] == "CARD_CLICKED":
    user_email = request_json["user"]["email"]
    prompt = request_json["action"]["parameters"][0]["value"]
    user_id = request_json["user"]["name"]
    if chat_platform == "google_chat":
       user_id = user_id.split("/")[-1]
    print("*** user_id={}".format(user_id))
  else:
    return "Hello! This function must be called from Google Chat."
  
  print("user_email={}".format(user_email))
  print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")

  if prompt == "はじめから":
    if chat_platform == "google_chat":
      response = create_cards_for_google_chat(user_id)
      answer = response
    # teams のボタン作成は app service 側で実装のためコメントアウト
    # elif chat_platform == "teams":
    #   response = create_cards_for_teams(user_email)
    #   answer = response
  # モデル選択ボタンをクリックした場合
  elif any(prompt == variation['name'] for model in models_json for variation in model['variations']):
    select_model = prompt
    print("*** select model: {0}".format(select_model))
    response = "select model: {0}".format(select_model)
    conversation_id = str(uuid.uuid4())

    # データの書き込み
    set_user_settings(user_id, select_model, conversation_id)
    
    answer = {
      "text": response
    }
  else:
    # 選択モデルを取得
    ret = get_user_settings(user_id)
    print("*** get_user_settings({})".format(user_id))
    print(ret)
    # ユーザ設定がない場合はデフォルト設定（gemini）を使用
    if ret is None:
      print("*** user_settings is None. Use default settings.")
      select_model = default_model
      conversation_id = str(uuid.uuid4())
      set_user_settings(user_id, select_model, conversation_id)
    else:
      select_model = ret["select_model"]
      conversation_id = ret["conversation_id"]

    # 選択モデルによって分岐
    if "gemini" in select_model:
        response = vertex_gemini(query=prompt, model=select_model)
    elif "text" in select_model:
        response = vertex_palm2_for_text(query=prompt, model=select_model)
    elif "code" in select_model:
        response = vertex_palm2_for_code(query=prompt, model=select_model)
    else:
        response = vertex_palm2_for_chat(query=prompt, model=select_model)
    
    # チャット履歴の書き込み
    set_chat_history(conversation_id, thread_id, user_id, user_email, user_name, select_model, prompt, response, chat_platform)

    answer = {
      "text": "model: {0} \n{1}".format(select_model, response),
    }

  return answer


def set_user_settings(user_id: str, select_model: str, conversation_id: str) -> None:
    """
    ユーザ設定の書き込み
    """
    print("set_user_settings()  user_id: {}, select_model: {}, conversation_id: {}".format(user_id, select_model, conversation_id))
    doc_ref = db.collection("users").document(user_id).collection("messages").document("user_settings")
    doc_ref.set(
        {
            "select_model": select_model,
            "timestamp": datetime.now(),
            "conversation_id": conversation_id,
        }
    )


def set_chat_history(conversation_id: str, thread_id: str, user_id: str, user_email: str, user_name: str, select_model: str, user_message: str, chatbot_message: str, chat_platform: str) -> None:
    """
    チャット履歴の書き込み
    """
    doc_ref = db.collection("users").document(user_id).collection("messages").document()
    doc_ref.set(
        {
            "id": thread_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "user_email": user_email,
            "user_name": user_name,
            "model": select_model,
            "user_message": user_message,
            "chatbot_message": chatbot_message,
            "chat_platform": chat_platform,
            "timestamp": datetime.now(),
        }
    )


def get_user_settings(user_id: str) -> list:
    """
    ユーザ設定を取得する
    """
    query = (
        db.collection("users")
        .document(user_id)
        .collection("messages")
        .document("user_settings")
    )
    return query.get().to_dict()


def get_previous_messages(user_id: str) -> list:
    """
    チャット履歴を取得する
    """
    query = (
        db.collection("users")
        .document(user_id)
        .collection("messages")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(1)
    )
    return [
        {
            "select_model": doc.to_dict()["select_model"],
            "conversation_id": doc.to_dict()["conversation_id"],
        }
        for doc in query.stream()
    ]


def vertex_palm2_for_text(query: str, temperature: float = 0.2, model: str = "chat-bison@001") -> None:
    print("vertex_palm2_for_text()  query: {}, model: {}".format(query, model))
    text_model = TextGenerationModel.from_pretrained(model)

    parameters = {
        "temperature": temperature,  # Temperature controls the degree of randomness in token selection.
        "max_output_tokens": 256,  # Token limit determines the maximum amount of text output.
        "top_p": 0.95,  # Tokens are selected from most probable to least until the sum of their probabilities equals the top_p value.
        "top_k": 40,  # A top_k of 1 means the selected token is the most probable among all tokens.
    }

    print(f"prompt: {query}")

    response = text_model.predict(query, **parameters)
    print(f"Response from Model: {response.text}")

    return response.text


def vertex_palm2_for_code(query: str, temperature: float = 0.2, model: str = "chat-bison@001") -> None:
    print("vertex_palm2_for_code()  query: {}, model: {}".format(query, model))
    code_model = CodeGenerationModel.from_pretrained(model)

    parameters = {
        "temperature": temperature,  # Temperature controls the degree of randomness in token selection.
        "max_output_tokens": 256,  # Token limit determines the maximum amount of text output.
    }

    print(f"prompt: {query}")

    response = code_model.predict(
        prefix=query, **parameters
    )
    print(f"Response from Model: {response.text}")

    return response.text


def vertex_palm2_for_chat(query: str, temperature: float = 0.2, model: str = "chat-bison@001") -> None:
    print("vertex_palm2_for_chat()  query: {}, model: {}".format(query, model))
    chat_model = ChatModel.from_pretrained(model)

    parameters = {
        "temperature": temperature,  # Temperature controls the degree of randomness in token selection.
        "max_output_tokens": 256,  # Token limit determines the maximum amount of text output.
        "top_p": 0.95,  # Tokens are selected from most probable to least until the sum of their probabilities equals the top_p value.
        "top_k": 40,  # A top_k of 1 means the selected token is the most probable among all tokens.
    }

    chat = chat_model.start_chat(
        context="""You are a professional Google Cloud Engineer.""",
    )
    print(f"prompt: {query}")

    response = chat.send_message(query, **parameters)
    print(f"Response from Model: {response.text}")

    return response.text


def vertex_gemini(query: str, temperature: float = 0.2, model: str = default_model) -> None:
    print("vertex_gemini()  query: {}, model: {}".format(query, model))
    model = GenerativeModel(model)

    generation_config = GenerationConfig(
        temperature=temperature,
        top_p=1.0,
        top_k=32,
        candidate_count=1,
        max_output_tokens=8192,
    )

    print(f"prompt: {query}")

    output_response = ""

    responses = model.generate_content(
        query,
        generation_config=generation_config,
        stream=False,
    )

    print(responses.text)
    output_response = responses.text

    # for response in responses:
    #   print(f"Response from Model: {response.text}", end="")
    #   output_response = output_response + response.text

    return output_response


def create_button(base_model, variation_model, user_email):
    """
    ボタンを作成する
    """
    return {
        "text": base_model + ": " + variation_model,
        "onClick": {
            "action": {
                "function": "model_request",
                "parameters": [
                    {
                        "key": "select_model",
                        "value": variation_model
                    },
                    # {
                    #     "key": "user_email",
                    #     "value": user_email
                    # }
                ]
            }
        }
    }


def create_cards_for_google_chat(user_email: str) -> Mapping[str, Any]:
    """
    google chat のカードインタフェースを作成する
    """
    buttons = [create_button(model['base_model'], variation['name'], user_email) for model in models_json for variation in model['variations']]

    model_section = {
        "widgets": [
            {
                "buttonList": {
                    "buttons": buttons
                }
            }
        ]
    }

    header = {"title": "モデルを選択してください"}

    cards = {
        "cardsV2": [
            {
                "cardId": "modelSelect",
                "card": {
                    "name": "model select",
                    "header": header,
                    "sections": [model_section],
                },
            }
        ]
    }

    return cards
