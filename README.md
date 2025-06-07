# Google Chat Vertex AI デモ

このプロジェクトは、Google ChatとGoogle Cloud Vertex AIを統合したデモ用のチャットボットアプリケーションです。<br>
複数のAIモデルを切り替えて使用することができます。<br>
チャット履歴を保存して、ユーザー設定を管理することができますが、チャット履歴を元にチャットを継続することはできません。

## 機能

- Google Chatとの統合
- 複数のAIモデルのサポート
  - Gemini 2.0 Flash
  - Gemini 2.0 Flash Lite
  - Gemini 1.5 Pro
  - Gemini 1.5 Flash
  - Text Embedding
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
2. 以下のいずれかのコマンドを入力してモデル選択画面を表示
   - "はじめから"
   - "モデルを選択"
3. 使用したいモデルを選択
4. チャットを開始

## サポートされているモデル

### Gemini 2.0 シリーズ
- **gemini-2.0-flash-001**: 優れた速度、ネイティブ ツールの使用、100 万トークンのコンテキスト ウィンドウなど、次世代の機能と強化された機能を提供します
- **gemini-2.0-flash-lite-001**: 費用対効果と低レイテンシを重視して最適化された Gemini 2.0 Flash モデル

### Gemini 1.5 シリーズ
- **gemini-1.5-pro-002**: 高度な推論能力と長文理解に優れた Gemini 1.5 Pro モデル
- **gemini-1.5-flash-002**: 高速な応答と効率的な処理を実現する Gemini 1.5 Flash モデル

### その他
- **text-embedding-005**: テキストの意味を理解し、高品質な埋め込みベクトルを生成するモデル

## アーキテクチャ

- Cloud Functionsを使用したサーバーレスアーキテクチャ
- Firestoreを使用したデータ永続化
- Vertex AIを使用したAIモデルの統合

## 参考

- [Google Chat、Vertex AI、Firestore でプロジェクトを管理する](https://developers.google.com/workspace/chat/tutorial-project-management?hl=ja)
- [Vertex AI の生成AIのロケーション](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations?hl=ja#asia-pacific)
