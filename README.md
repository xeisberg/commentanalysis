# 講義アンケートコメント分析プロジェクト

本プロジェクトは、AWS Bedrock（大規模言語モデル）を使用して講義アンケートのCSVファイルからフリーテキストコメントを自動的に処理・分析するサーバーレスパイプラインをAWS上に実装します。分析結果はDynamoDBに保存され、静的ウェブダッシュボードで可視化されます。

## 機能

*   AWS Bedrock を使用した CSV コメントの自動分析（センチメント、カテゴリ、重要度、リスク）。
*   DynamoDB への詳細な分析結果の保存。
*   ダッシュボード可視化のための統計情報の集計（カウント数、パーセンテージ）。
*   高リスクコメントおよび重要コメントの特定と表示。
*   チャートと表を備えたインタラクティブなダッシュボード。
*   全分析データの CSV 形式でのエクスポート機能。

## アーキテクチャ

[システム設計ドキュメント]![Comment analysis architecture diagram](https://raw.githubusercontent.com/xeisberg/commentanalysis/refs/heads/main/architecture.png) 

## プロジェクト構造

*   `backend/`: AWS Lambda 関数のコード（Python）が含まれています。
*   `frontend/`: Web ダッシュボードの静的ファイル（HTML, CSS, JS）が含まれています。
*   `docs/`: 詳細なプロジェクトドキュメントが含まれています。
*   `samples/`: サンプルの入力データが含まれています。

## 前提条件

*   AWS アカウント。
*   AWSにてBedrock,Lambda関数などを使用可

## デプロイ

1.  **バックエンドLambda** `backend/` Lambdaの関数をAWSで用意します。
2.  **S3トリガーの構成:** `feedbackinput` バケットの S3 イベント通知を手動で構成し、`process_feedback` Lambda 関数をトリガーするように設定します。
3.  **フロントエンドファイルのアップロード:** `frontend/` ディレクトリの内容を、静的ウェブサイトホスティング用に構成された S3 バケットに置きます。
4.  **フロントエンドAPI URLの更新:** API Gateway をデプロイ後 (ステップ2)、 AWS コンソールからその呼び出し URL を取得します。`frontend/script.js` の API URL プレースホルダーを、デプロイした API Gateway の実際の URL に置き換えます。最初のアップロード後に変更した場合は、`script.js` を再アップロードしてください。
5.  **ダッシュボードへのアクセス:** Web ブラウザで S3 静的ウェブサイトまたは CloudFront ディストリビューションの URL を開きます。

*詳細なデプロイ手順と構成については、docsのフォルダー を参照してください。*

## 使用方法

1.  デプロイ中に作成された `feedbackinput` S3 バケットに、'Comment' という名前の列を含む CSV ファイルをアップロードします。
2.  分析パイプラインがファイルを処理するまで数分待ちます。
3.  ダッシュボード URL にアクセスします。ダッシュボードは最新の分析結果を自動的にフェッチして表示します。
4.  「Export Full Analysis Data (CSV)」ボタンをクリックすると、DynamoDB から完全なデータセットがダウンロードされます。