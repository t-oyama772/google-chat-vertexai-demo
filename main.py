import flask
import functions_framework
import vertexai
import uuid
import google.auth
from typing import Any, Mapping, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from vertexai.generative_models import GenerationConfig, GenerativeModel
from google.cloud import firestore
from datetime import datetime
import logging

# ロギングの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChatPlatform(Enum):
    """チャットプラットフォームの種類"""
    GOOGLE_CHAT = "google_chat"
    UNKNOWN = "unknown"


@dataclass
class ModelVariation:
    """モデルのバリエーション情報"""
    name: str
    description: str
    location: str


@dataclass
class BaseModel:
    """ベースモデル情報"""
    name: str
    variations: List[ModelVariation]


class VertexAIClient:
    """Vertex AI クライアント"""
    def __init__(self, project_id: str):
        self.project_id = project_id
        self._initialized = False

    def initialize(self, model_name: str) -> None:
        """モデルに応じたロケーションで Vertex AI を初期化"""
        location = self._get_model_location(model_name)
        logger.info(f"Initializing Vertex AI with location: {location} for model: {model_name}")
        vertexai.init(project=self.project_id, location=location)
        self._initialized = True

    def _get_model_location(self, model_name: str) -> str:
        """モデル名からロケーションを取得"""
        for model in MODELS:
            for variation in model.variations:
                if variation.name == model_name:
                    return variation.location
        return DEFAULT_LOCATION


class FirestoreClient:
    """Firestore クライアント"""
    def __init__(self, project_id: str):
        self.db = firestore.Client(project=project_id)

    def set_user_settings(
            self,
            user_id: str,
            select_model: str,
            conversation_id: str
    ) -> None:
        """ユーザ設定の保存"""
        logger.info(f"Setting user settings - user_id: {user_id}, model: {select_model}")
        doc_ref = self.db.collection("users").document(user_id).collection("messages").document("user_settings")
        doc_ref.set({
            "select_model": select_model,
            "timestamp": datetime.now(),
            "conversation_id": conversation_id,
        })

    def get_user_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """ユーザ設定の取得"""
        doc_ref = self.db.collection("users").document(user_id).collection("messages").document("user_settings")
        return doc_ref.get().to_dict()

    def set_chat_history(
            self,
            conversation_id: str,
            thread_id: str,
            user_id: str,
            user_email: str,
            user_name: str,
            select_model: str,
            user_message: str,
            chatbot_message: str,
            chat_platform: str
    ) -> None:
        """チャット履歴の保存"""
        doc_ref = self.db.collection("users").document(user_id).collection("messages").document()
        doc_ref.set({
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
        })


# 定数定義
DEFAULT_LOCATION = "asia-northeast1"
DEFAULT_MODEL = "gemini-1.5-pro-002"

# モデル定義
MODELS = [
    BaseModel(
        name="Gemini",
        variations=[
            ModelVariation(
                name="gemini-2.0-flash-001",
                description="優れた速度、ネイティブ ツールの使用、100 万トークンのコンテキスト ウィンドウなど、次世代の機能と強化された機能を提供します",
                location="us-central1"
            ),
            ModelVariation(
                name="gemini-2.0-flash-lite-001",
                description="費用対効果と低レイテンシを重視して最適化された Gemini 2.0 Flash モデル",
                location="us-central1"
            ),
            ModelVariation(
                name="gemini-1.5-pro-002",
                description="高度な推論能力と長文理解に優れた Gemini 1.5 Pro モデル",
                location="asia-northeast1"
            ),
            ModelVariation(
                name="gemini-1.5-flash-002",
                description="高速な応答と効率的な処理を実現する Gemini 1.5 Flash モデル",
                location="asia-northeast1"
            ),
            ModelVariation(
                name="text-embedding-005",
                description="テキストの意味を理解し、高品質な埋め込みベクトルを生成するモデル",
                location="asia-northeast1"
            )
        ]
    )
]

# グローバル変数の初期化
cred, PROJECT_ID = google.auth.default()
vertex_ai_client = VertexAIClient(PROJECT_ID)
firestore_client = FirestoreClient(PROJECT_ID)


@functions_framework.http
def hello_chat(req: flask.Request) -> Mapping[str, Any]:
    """Google Chat からのリクエストを処理するメイン関数"""
    if req.method == "GET":
        return "Hello! This function must be called from Google Chat."

    try:
        request_json = req.get_json(silent=True)
        if not request_json:
            raise ValueError("Invalid request: No JSON data")

        # チャットプラットフォームの判定
        chat_platform = _determine_chat_platform(request_json)
        logger.info(f"Chat platform: {chat_platform}")

        # スレッド情報の取得
        thread_id = _get_thread_id(request_json)
        logger.info(f"Thread ID: {thread_id}")

        # ユーザー情報とプロンプトの取得
        user_info, prompt = _get_user_info_and_prompt(request_json, chat_platform)
        logger.info(f"User info: {user_info}, Prompt: {prompt}")

        # レスポンスの生成
        response = _generate_response(prompt, user_info, chat_platform, thread_id)
        return response

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return {"text": f"エラーが発生しました: {str(e)}"}


def _determine_chat_platform(request_json: Dict[str, Any]) -> ChatPlatform:
    """チャットプラットフォームを判定"""
    if "configCompleteRedirectUrl" in request_json:
        if "https://chat.google.com/" in request_json["configCompleteRedirectUrl"]:
            return ChatPlatform.GOOGLE_CHAT
    elif "cardsV2" in request_json.get("message", {}):
        return ChatPlatform.GOOGLE_CHAT
    return ChatPlatform.UNKNOWN


def _get_thread_id(request_json: Dict[str, Any]) -> str:
    """スレッドIDを取得"""
    thread_name = request_json["message"]["thread"]["name"]
    return thread_name.split("/")[-1]


def _get_user_info_and_prompt(
        request_json: Dict[str, Any],
        chat_platform: ChatPlatform
) -> tuple:
    """ユーザー情報とプロンプトを取得"""
    if request_json["type"] in ["ADDED_TO_SPACE", "MESSAGE"]:
        user_info = {
            "email": request_json["user"]["email"],
            "id": request_json["user"]["name"].split("/")[-1] if chat_platform == ChatPlatform.GOOGLE_CHAT else request_json["user"]["name"],
            "name": request_json["user"]["displayName"]
        }
        prompt = request_json["message"]["text"]
        if "annotations" in request_json["message"]:
            mention = f"@{request_json['message']['annotations'][0]['userMention']['user']['displayName']} "
            prompt = prompt.replace(mention, "").strip()
    elif request_json["type"] == "CARD_CLICKED":
        user_info = {
            "email": request_json["user"]["email"],
            "id": request_json["user"]["name"].split("/")[-1] if chat_platform == ChatPlatform.GOOGLE_CHAT else request_json["user"]["name"],
            "name": request_json["user"]["displayName"]
        }
        prompt = request_json["action"]["parameters"][0]["value"]
    else:
        raise ValueError("Unsupported request type")

    return user_info, prompt


def _generate_response(
        prompt: str,
        user_info: Dict[str, str],
        chat_platform: ChatPlatform,
        thread_id: str
) -> Mapping[str, Any]:
    """レスポンスを生成"""
    if prompt == "はじめから":
        if chat_platform == ChatPlatform.GOOGLE_CHAT:
            return create_cards_for_google_chat(user_info["id"])
        return {"text": "このコマンドは Google Chat でのみ使用できます。"}

    # モデル選択の処理
    if any(prompt == variation.name for model in MODELS for variation in model.variations):
        return _handle_model_selection(prompt, user_info)

    # 通常のチャット処理
    return _handle_chat(prompt, user_info, chat_platform, thread_id)


def _handle_model_selection(prompt: str, user_info: Dict[str, str]) -> Mapping[str, Any]:
    """モデル選択の処理"""
    select_model = prompt
    conversation_id = str(uuid.uuid4())

    vertex_ai_client.initialize(select_model)
    firestore_client.set_user_settings(user_info["id"], select_model, conversation_id)

    return {"text": f"モデルを選択しました: {select_model}"}


def _handle_chat(
        prompt: str,
        user_info: Dict[str, str],
        chat_platform: ChatPlatform,
        thread_id: str
) -> Mapping[str, Any]:
    """チャット処理"""
    settings = firestore_client.get_user_settings(user_info["id"])

    if not settings:
        select_model = DEFAULT_MODEL
        conversation_id = str(uuid.uuid4())
        firestore_client.set_user_settings(user_info["id"], select_model, conversation_id)
    else:
        select_model = settings["select_model"]
        conversation_id = settings["conversation_id"]

    vertex_ai_client.initialize(select_model)
    response = _generate_ai_response(prompt, select_model)

    firestore_client.set_chat_history(
        conversation_id, thread_id, user_info["id"],
        user_info["email"], user_info["name"], select_model,
        prompt, response, chat_platform.value
    )

    return {"text": f"モデル: {select_model}\n{response}"}


def _generate_ai_response(prompt: str, model: str) -> str:
    """AIモデルを使用してレスポンスを生成"""
    if "gemini" in model:
        return vertex_gemini(query=prompt, model=model)
    elif "text" in model:
        return vertex_gemini(query=prompt, model=model)  # text-embedding-005 も Gemini を使用
    else:
        raise ValueError(f"Unsupported model: {model}")


def vertex_gemini(query: str, temperature: float = 0.2, model: str = DEFAULT_MODEL) -> str:
    """Gemini モデルを使用してレスポンスを生成"""
    logger.info(f"vertex_gemini()  query: {query}, model: {model}")
    model = GenerativeModel(model)

    generation_config = GenerationConfig(
        temperature=temperature,
        top_p=1.0,
        top_k=32,
        candidate_count=1,
        max_output_tokens=8192,
    )

    logger.info(f"prompt: {query}")

    responses = model.generate_content(
        query,
        generation_config=generation_config,
        stream=False,
    )

    logger.info(responses.text)
    return responses.text


def create_button(base_model: BaseModel, variation: ModelVariation, user_email: str) -> Dict[str, Any]:
    """
    ボタンを作成する
    """
    return {
        "text": f"{base_model.name}: {variation.name}",
        "onClick": {
            "action": {
                "function": "model_request",
                "parameters": [
                    {
                        "key": "select_model",
                        "value": variation.name
                    }
                ]
            }
        }
    }


def create_cards_for_google_chat(user_email: str) -> Mapping[str, Any]:
    """
    google chat のカードインタフェースを作成する
    """
    buttons = [
        create_button(model, variation, user_email) 
        for model in MODELS 
        for variation in model.variations
    ]

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
