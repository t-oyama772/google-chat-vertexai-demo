# Google Chat Vertex AI デモ

このプロジェクトは、Google ChatとGoogle Cloud Vertex AIを統合したデモ用のチャットボットアプリケーションです。
複数のAIモデルを切り替えて使用することができます。
チャット履歴を保存して、ユーザー設定を管理することができますが、チャット履歴を元にチャットを継続することはできません。

## 機能

- Google Chatとの統合
- 複数のAIモデルのサポート
  - Gemini 1.5 Pro
  - Gemini 1.5 flash
- チャット履歴の保存
- ユーザー設定の管理
- モデル選択のインタラクティブなインターフェース

## 前提条件

- Google Cloud Platform アカウント
- Vertex AI API の有効化
- Firestore データベース
- Google Chat API の有効化

## セットアップ

1. プロジェクトのクローン
```bash
git clone [repository-url]
cd google-chat-vertexai-demo
```

2. 必要なパッケージのインストール
```bash
pip install -r requirements.txt
```

3. Google Cloud の設定
- プロジェクトIDの設定
- サービスアカウントの作成と認証情報の設定
- Vertex AI APIの有効化
- Firestoreの設定

4. 環境変数の設定
```bash
export PROJECT_ID="your-project-id"
```

## 使用方法

1. Google Chatでボットを追加
2. "はじめから"と入力してモデル選択画面を表示
3. 使用したいモデルを選択
4. チャットを開始

## アーキテクチャ

- Cloud Functionsを使用したサーバーレスアーキテクチャ
- Firestoreを使用したデータ永続化
- Vertex AIを使用したAIモデルの統合

## 参考

- [Google Chat、Vertex AI、Firestore でプロジェクトを管理する](https://developers.google.com/workspace/chat/tutorial-project-management?hl=ja)
