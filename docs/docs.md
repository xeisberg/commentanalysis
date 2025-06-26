**講義アンケートコメント分析システムの詳細**

このドキュメントは、講義アンケートコメント分析システムの構成要素と機能を詳細に説明します。本システムは、CSVフィードバックの自動処理、AWS Bedrockを使用したコメント分析、結果の保存、およびエクスポート機能を備えたウェブダッシュボードでの統計情報の可視化を行うように設計されています。

## 1. 概要

本プロジェクトは、AWS上にサーバーレスなデータ処理および可視化パイプラインを実装します。これは、Amazon Bedrockを介した大規模言語モデル (LLM) を使用して、CSVアンケートファイルのフリーテキストコメントの分析を自動化し、集計された洞察を静的ウェブサイトダッシュボードで表示します。主要な機能には、自動分析、統計集計、高リスクおよび重要コメントの特定、インタラクティブな可視化 (グラフと表)、データエクスポートが含まれます。

## 2. 要件マッピング

実装されたソリューションは、指定されたすべての要件に直接対応しています。

*   **ポジティブなフィードバック（賞賛・良い点）の集計：** `GetStatsLambda` が Bedrock によって分類された「Positive」センチメントの出現数をカウントすることで対応しています。
*   **ネガティブなフィードバック（改善要望）の集計：** `GetStatsLambda` が Bedrock によって分類された「Negative」センチメントの出現数をカウントすることで対応しています。
*   **自動的に4つのカテゴリに分類：講義内容、講義資料、運用、その他：** `ProcessFeedbackLambda` が Amazon Bedrock を使用してコメントをこれらの事前定義されたカテゴリに分類することで対応しています。
*   **高リスクコメントの特定：** `ProcessFeedbackLambda` が Amazon Bedrock を使用して `IsHighRisk` ブール値フラグを割り当てることで対応しています。`GetStatsLambda` はこれらのコメントをカウントし、リスト (`high_risk_comments_list`) を提供します。
*   **重要なコメントのランク付け表示：** `ProcessFeedbackLambda` が Amazon Bedrock を使用して `Importance` スコア (1-5) を割り当てることで対応しています。`GetStatsLambda` はこのスコアでコメントをソートし、上位のコメントのリスト (`top_important_comments`) を提供します。フロントエンドはこのリストを表示します。
*   **統計情報のカテゴリ別可視化（カテゴリごとのカウントとパーセンテージ (%) を表示し、「推奨アクション」フラグなどを表示）：** `GetStatsLambda` が `category_counts` と `category_percentages` を計算し、事前定義されたロジック (例: パーセンテージ閾値) に基づいて `recommended_actions` を決定することで対応しています。フロントエンドダッシュボード (`script.js`) はこのデータを使用してカテゴリテーブルとカテゴリ棒グラフを生成します。
*   **CSV形式でのエクスポート：** API Gateway を介してトリガーされる `ExportCsvLambda` 関数が、DynamoDB からすべてのデータを取得し、ダウンロード用にCSV形式に整形することで対応しています。
*   **ウェブサイトでの可視化のためにデータベースに保存可能：** `ProcessFeedbackLambda` が分析結果を `feedbackanalysis` DynamoDB テーブルに保存することで対応しています。フロントエンドウェブサイトは、`GetStatsLambda` を介してこのテーブルからデータを読み取り、可視化します。

## 3. アーキテクチャ

本プロジェクトは、サーバーレスかつイベント駆動型のアーキテクチャパターンに従っています。

![Comment analysis architecture diagram](https://raw.githubusercontent.com/xeisberg/commentanalysis/refs/heads/main/architecture.png)

**コンポーネントの説明：**

*   **User (ユーザー):** 手動でCSVファイルをアップロードし、ブラウザを介してウェブダッシュボードにアクセスすることでシステムとインタラクションします。
*   **S3 Bucket (`feedbackinput`):** 生のCSVファイルを受信するS3バケットです。S3イベント通知がファイル作成時に分析用Lambdaをトリガーします。
*   **AWS Lambda (`Process Feedback` - 例: `ProcessFeedbackPoCPipeline`):** S3イベントによってトリガーされ、このLambdaはCSVファイルを読み取り、コメントを抽出し、分析のためにAmazon Bedrockを呼び出し、構造化された結果をDynamoDBに書き込みます。
*   **Amazon Bedrock:** `Process Feedback` Lambda がセンチメント、カテゴリ、重要度、リスクについてコメントを分析するために使用するLLM (例: Amazon Titan Text Express v1) へのアクセスを提供します。
*   **Amazon DynamoDB (`feedbackanalysis` table):** 各個別のコメントの分析結果を項目として格納するNoSQLデータベーステーブルです。`CommentID` がプライマリキーとして機能します。
*   **S3 Bucket (`Static Website`):** 静的ウェブサイトホスティング用に構成されたS3バケットで、ダッシュボードフロントエンドのHTML、CSS、JavaScriptファイルが含まれます。
*   **User Browser (ユーザーブラウザ):** 静的ウェブファイルを実行し、ダッシュボードをレンダリングし、データを取得およびエクスポートするためにAPI呼び出しを行います。
*   **API Gateway:** ダッシュボードにデータを提供するバックエンドLambda関数への公開エンドポイントとして機能します。Lambdaプロキシ統合を使用します。
*   **AWS Lambda (`Get Stats`):** API Gatewayへの `GET /stats` リクエストによってトリガーされます。`feedbackanalysis` DynamoDB テーブル全体をスキャンし、データを集計して統計情報 (カウント、パーセンテージ) を生成し、リスト (高リスク、重要コメント上位) をフィルタリングし、JSONレスポンスとしてデータを返します。（注意: 大規模なテーブルではスキャンは非効率です。本番環境では、キーリストを使用したBatchGetItemまたはフィルタリング/ページネーションのためのグローバルセカンダリインデックス (GSIs) の使用を検討してください）。
*   **AWS Lambda (`Export CSV`):** API Gatewayへの `GET /export/csv` リクエストによってトリガーされます。`feedbackanalysis` DynamoDB テーブル全体をスキャンし、データをCSV文字列に整形し、ブラウザダウンロードに適したヘッダーとともに返します。（注意: 大規模なテーブルではスキャンは非効率です。本番環境では、ページネーションまたはデータレイクからのエクスポートを検討してください）。

## 4. コンポーネント詳細

### 4.1 AWS Lambda関数

すべてのLambda関数はPythonで記述され、Boto3を使用して他のAWSサービスと対話するように構成されています。構成には環境変数（テーブル/バケット名、BedrockモデルIDなど）を使用し、適切な権限を持つIAMロールを使用することを想定しています。API Gatewayトリガー関数にはLambdaプロキシ統合が使用されます。

#### 4.1.1 Process Feedback Lambda (例: `lambda_function.py`)

*   **トリガー:** `feedbackinput` バケットのS3 Put イベント。
*   **環境変数:**
    *   `S3_BUCKET_NAME`: `feedbackinput` S3バケットの名前（イベントから取得されますが、この環境変数に対して検証されます）。
    *   `DYNAMODB_TABLE_NAME`: `feedbackanalysis` DynamoDB テーブルの名前。
    *   `BEDROCK_MODEL_ID`: 使用するBedrockモデルの識別子（例: `amazon.titan-text-express-v1`）。
*   **主要ロジック:**
    *   S3イベントからバケットとキーを抽出します。
    *   S3からCSVファイルをダウンロードします。
    *   `csv.DictReader` を使用してCSVをパースし、「Comment」という名前の列を期待します。
    *   各コメント行をイテレーション処理します（LLM分析では空または空白のみのコメントをスキップしますが、レコードは格納します）。
    *   指定されたBedrockモデルのプロンプトを構築します。
    *   `bedrock-runtime.invoke_model` を呼び出し、コメントとプロンプトをBedrockに送信します。
    *   LLM応答をパースし、予期せぬ出力形式（Markdownブロック内のJSONを探す、または`{}`抽出を使用）に頑健に対応します。
    *   パースされたJSONから `sentiment`、`category`、`importance`、`isHighRisk` を抽出します。
    *   パースエラーまたはBedrock APIエラーが発生した場合を処理し、エラー詳細を項目に保存します。
    *   `CommentID` (UUID)、`OriginalComment`、`ProcessingTimestamp`、`OriginalCsvRowIndex`、および分析結果またはエラー情報を含むDynamoDB用の項目辞書を構築します。
    *   `dynamodb_resource.Table(DYNAMODB_TABLE_NAME).put_item` を使用して `feedbackanalysis` DynamoDB テーブルに項目を書き込みます。
*   **エラー処理:** S3ダウンロード、CSVパース、Bedrock API呼び出し、Bedrock応答パース、DynamoDB書き込みに対する包括的なエラー処理を含みます。警告とエラーをログに記録し、コメントの分析が失敗した場合はエラー詳細をDynamoDBに保存します。空のコメントのLLM分析をスキップし、これをログに記録し、プレースホルダー項目を保存します。

#### 4.1.2 Get Stats Lambda (`lambda_handler.py`)

*   **トリガー:** API Gateway `GET /stats`。
*   **環境変数:**
    *   `DYNAMODB_TABLE_NAME`: `feedbackanalysis` DynamoDB テーブルの名前。
*   **主要ロジック:**
    *   `feedbackanalysis` DynamoDB テーブル全体をスキャンして、すべての項目を取得します。（注意: 大規模なテーブルではスキャンは非効率です。本番環境では、キーリストを使用したBatchGetItemまたはフィルタリング/ページネーションのためのグローバルセカンダリインデックス (GSIs) の使用を検討してください）。
    *   スキャンが1MBを超えるデータを返す場合のページネーションを処理します。
    *   元のDynamoDB項目（`Decimal`を含み、属性が欠落または不整合である可能性あり）を、標準化された型（Importance/Indexは`int`、IsHighRiskは`bool`）を持つクリーンなPython辞書にマッピングします。
    *   「Skipped - Empty」と明示的にマークされた項目を、統計カウントおよび分析ベースの可視化に使用されるコメントリストから除外します。
    *   処理可能なコメントのフィルタリングされたリストに基づいて、センチメントとカテゴリのカウントを集計します。
    *   *処理可能な*コメントの総数に基づいてパーセンテージを計算します。
    *   カテゴリパーセンテージ（設定可能な閾値）に基づいて `recommended_actions` を決定します。
    *   処理可能なコメントを `Importance` でソートします（高から低）。
    *   ソートされたリストをフィルタリングして `top_important_comments` を特定します（例: Importance >= 4）。
    *   処理可能なリストをフィルタリングして `high_risk_comments_list` を特定します。
    *   フロントエンドチャート（Importance Distribution、Sentiment by Importance）用の `all_mapped_comments_list` の完全なリストをレスポンスに含めます。
    *   集計されたすべての統計情報とフィルタリング/ソートされたリストを含むPython辞書を構築します。
    *   `Decimal` オブジェクトがJSON数値に正しくシリアル化されるように、`decimal_default` ヘルパーを使用して、API Gatewayプロキシ形式（`statusCode`、`headers`、`body` はJSON文字列）で辞書を返します。
*   **エラー処理:** DynamoDBスキャンおよびデータ集計中の例外を捕捉し、500ステータスコードとエラーメッセージを返します。

#### 4.1.3 Export CSV Lambda (`lambda_handler.py`)

*   **トリガー:** API Gateway `GET /export/csv`。
*   **環境変数:**
    *   `DYNAMODB_TABLE_NAME`: `feedbackanalysis` DynamoDB テーブルの名前。
*   **主要ロジック:**
    *   `feedbackanalysis` DynamoDB テーブル全体をスキャンして、すべての項目を取得します。（注意: 大規模なテーブルではスキャンは非効率です。本番環境では、ページネーションまたはデータレイクからのエクスポートを検討してください）。
    *   ページネーションを処理します。
    *   CSV出力のヘッダーリストを定義し、一貫した列順序を保証します。
    *   取得された各項目をイテレーション処理します。
    *   `Decimal` 値（`Importance`、`OriginalCsvRowIndex`、`LLMStatusCode`）を、CSVに適した `int`、`float`、または `str` に変換します。
    *   `IsHighRisk` 値（ブール値、Decimal、または文字列表現）を文字列「True」または「False」に変換します。
    *   `csv.DictWriter` を `quoting=csv.QUOTE_ALL` とともに使用して、コメントテキスト内のコンマと引用符を正しく処理します。
    *   ヘッダー行と処理された各項目行をインメモリの `io.StringIO` バッファに書き込みます。
    *   バッファから完全なCSVコンテンツ文字列を取得します。
    *   項目が見つからなかった場合を処理し、ヘッダーと「データなし」メッセージ行を含むCSVを返します。
    *   CSVコンテンツ文字列をAPI Gatewayプロキシ形式で返し、`statusCode: 200`、`Content-Type: text/csv`、`Content-Disposition: attachment; filename="..."`、および `isBase64Encoded: False` を設定します。
*   **エラー処理:** DynamoDBスキャンまたはCSV生成中の例外を捕捉し、500ステータスコードとJSONエラーメッセージを返します。

### 4.2 Amazon DynamoDB

*   **テーブル名:** `feedbackanalysis`（環境変数経由で構成）。
*   **プライマリキー:** `CommentID`（文字列型）。
*   **属性:**
    *   `CommentID` (文字列): 各コメントの一意の識別子。
    *   `OriginalComment` (文字列): コメントの元のテキスト。
    *   `ProcessingTimestamp` (文字列): コメントが処理されたISO形式のタイムスタンプ。
    *   `OriginalCsvRowIndex` (数値): 元のCSVファイル内の行番号（ヘッダーを含む）。
    *   `Sentiment` (文字列): Bedrockが分類したセンチメント（"Positive"、"Negative"、"Neutral"、"Mixed"、"Unknown"、"Skipped - Empty"、"Failed Analysis"）。
    *   `Category` (文字列): Bedrockが分類したカテゴリ（"Lecture Content"、"Lecture Materials"、"Operations"、"Other"、"Unknown"、"Skipped - Empty"、"Failed Analysis"）。
    *   `Importance` (数値): Bedrockが割り当てた重要度スコア（1-5）、数値型として保存。
    *   `IsHighRisk` (ブール値): Bedrockが割り当てた高リスクフラグ、ブール型として保存。
    *   `BedrockModelId` (文字列): 分析に使用されたBedrockモデルのID（スキップされた場合は 'N/A'）。
    *   `LLMError` (文字列): Bedrock呼び出しまたはパースが失敗した場合のエラーメッセージを保存。
    *   `LLMRawResponseSnippet` (文字列): 分析が失敗した場合の生のBedrock出力またはエラーボディのスニペットを保存。
    *   `LLMStatusCode` (数値/文字列): Bedrockモデルエラーが発生した場合のHTTPステータスコードを保存。

### 4.3 Amazon S3

*   **`feedbackinput` バケット:** 生のCSVファイルのランディングゾーンとして機能し、分析ワークフローをトリガーします。`PutObject` イベント時に `Process Feedback` Lambda をトリガーするようにS3イベント通知が構成されている必要があります。
*   **静的ウェブサイトホスティングバケット:** フロントエンドファイル（`index.html`、`style.css`、`script.js`）をホストします。静的ウェブサイトホスティング用に構成されています。オプションでCloudFrontを前に配置できます。

### 4.4 Amazon API Gateway

*   **APIタイプ:** REST API。
*   **エンドポイント:**
    *   `GET /stats`: **Lambdaプロキシ統合**を使用して `GetStatsLambda` と統合されます。JSON形式の統計情報を返します。CORSヘッダーはメソッド応答で構成されます。
    *   `GET /export/csv`: **Lambdaプロキシ統合**を使用して `ExportCsvLambda` と統合されます。CSVデータを返します。CORSヘッダーはメソッド応答で構成されます。
*   **CORS:** APIまたは特に `GET /stats` および `GET /export/csv` メソッドで、CORS (オリジン間リソース共有) が構成されています。`Access-Control-Allow-Origin: '*'` は開発用に使用されますが、本番環境では制限する必要があります。
*   **デプロイ:** APIの変更は、アクティブにするためにステージ（例: `v1`）にデプロイする必要があります。

### 4.5 フロントエンドWebアプリケーション (HTML, CSS, JavaScript)

*   **ホスティング:** S3 (オプションでCloudFront経由) 上で静的ファイルとしてホストされます。
*   **`index.html`:** ダッシュボードの構造を提供し、全体統計、センチメント内訳、カテゴリ内訳、重要度分析、高リスクコメント、重要なコメント上位、エクスポートのセクションを含みます。Chart.jsの可視化のための `<canvas>` 要素が含まれています。`style.css` と `script.js` をリンクしています。
*   **`style.css`:** ダッシュボードのレイアウト、要素、テーブル、チャートコンテナをスタイル設定します。一般的なスタイリングにはCSS変数を使用してカラーパレットを定義しますが、チャートの色はJavaScriptで直接定義されます。
*   **`script.js`:**
    *   `DOMContentLoaded` イベントで実行されます。
    *   `GET /stats` APIエンドポイントからデータをフェッチします。
    *   API Gatewayプロキシ応答を処理します（外側のJSONをパースし、次に内側のJSONボディをパースします）。
    *   ダッシュボード上のステータスメッセージ（`loading`、`success`、`error`）を管理します。
    *   新しいデータを読み込む前に、以前のデータをクリアし、古いChart.jsインスタンスを破棄します。
    *   統計JSON応答からのデータを使用して、データテーブル（センチメント、カテゴリ、高リスクコメント、重要なコメント上位）にデータを投入します。
    *   JavaScriptオブジェクトとしてカラーパレットを直接定義します。
    *   統計JSONからのデータとJSカラーパレットを使用して、Chart.jsインスタンス（`createSentimentBarChart`、`createCategoryChart`、`createImportanceDistributionChart`、`createSentimentImportanceChart`）を作成および構成します。
    *   テーブル/チャートラベルのソートロジックと、リスト（高リスク、重要なコメント上位、重要度チャートに使用されるデータ）のデータフィルタリングを含みます。
    *   エクスポートボタンにイベントリスナーを追加し、ブラウザを `GET /export/csv` APIエンドポイントにナビゲートします。
    *   テーブルにコメントテキストを安全に表示するための `escapeHTML` ヘルパーを含みます。

## 5. デプロイ手順

これは高レベルのガイドです。AWSコンソール、SAM、CloudFormation、またはTerraformの使用方法によって具体的な手順は異なる場合があります。

1.  **CSVアップロード用S3バケットの作成:** 新しいS3バケットを作成します（例: `feedbackinput`）。必要に応じてバージョニングを有効にします。
2.  **静的ウェブサイト用S3バケットの作成:** 別の新しいS3バケットを作成します（例: `feedback-analysis-frontend`）。このバケットで静的ウェブサイトホスティングを有効にし、インデックスドキュメントとして `index.html` を設定します。バケットをパブリックに *するか* 、CloudFrontオリジンアクセス制御 (OAC) を構成します。
3.  **(オプション) CloudFrontディストリビューションの作成:** S3静的ウェブサイトバケットをオリジンとするCloudFrontディストリビューションを作成します。HTTPSを構成します。ブラウザのURLをCloudFrontドメインを使用するように更新します。
4.  **DynamoDBテーブルの作成:** `feedbackanalysis` という名前のDynamoDBテーブルを作成します。パーティションキーとして `CommentID` (文字列型) を定義します。このスキーマではソートキーは不要です。読み取り/書き込みキャパシティを構成します（オンデマンドが可変負荷に対して最も簡単です）。
5.  **IAMロールの作成:**
    *   **Lambda実行ロール:** Lambda関数用のIAMロールを作成します。このロールには、以下を許可するポリシーが必要です。
        *   CloudWatch Logs アクセス (`CreateLogGroup`、`CreateLogStream`、`PutLogEvents`)。
        *   DynamoDB アクセス (`dynamodb:Scan`、`dynamodb:PutItem`)。
        *   S3 アクセス (`s3:GetObject` for `feedbackinput`、`s3:PutObject` for `feedbackinput` - ただし、手動アップロードのみがトリガーである場合、最初のLambdaには厳密には `s3:GetObject` のみが必要です)。
        *   Bedrock アクセス (`bedrock-runtime:InvokeModel`)。
6.  **Lambda関数のデプロイ:**
    *   `Process Feedback`、`Get Stats`、`Export CSV` のコードをパッケージ化します。
    *   希望するAWSリージョンに各Lambda関数を作成します。
    *   ステップ5で作成したIAMロールを割り当てます。
    *   ランタイム（Python 3.x）を設定します。
    *   ハンドラ名を設定します: `lambda_function.lambda_handler` (コードが `lambda_function.py` にあると仮定)。
    *   環境変数（`DYNAMODB_TABLE_NAME`、最初のLambdaには `S3_BUCKET_NAME`、`BEDROCK_MODEL_ID`）を設定します。
7.  **S3トリガーの構成:** `feedbackinput` S3バケットのプロパティで、イベント通知を追加します。Put イベント (`s3:ObjectCreated:*`) に対して `Process Feedback` Lambda をトリガーするように設定します。
8.  **API Gatewayの構成:**
    *   新しいREST APIを作成します。
    *   リソースを作成します: `/stats`、`/export`、`/export/csv`。
    *   `/stats` と `/export/csv` に対して `GET` メソッドを作成します。
    *   `GET /stats` および `GET /export/csv` の両方について、**Lambdaプロキシ統合**を使用するように統合リクエストを構成し、対応するLambda関数を選択します。
    *   APIまたは特に `GET /stats` および `GET /export/csv` メソッドでCORSを有効にし、`Access-Control-Allow-Origin` を `*` (開発用) またはS3静的ウェブサイトドメイン (本番用) に設定します。
    *   APIをステージ（例: `v1`）にデプロイします。呼び出しURLを控えておきます。
9.  **フロントエンドAPI URLの更新:** `script.js` ファイル内のプレースホルダー `https://xxxx.execute-api.ap-northeast-1.amazonaws.com/v1` を、デプロイしたAPI Gatewayステージの実際の呼び出しURLに置き換えます。
10. **フロントエンドファイルのアップロード:** `index.html`、`style.css`、および変更した `script.js` をS3静的ウェブサイトホスティングバケットにアップロードします。
11. **ブラウザキャッシュのクリア:** 重要です！ダッシュボードにアクセスする前に、ブラウザのキャッシュをクリアしてください。

## 6. 使用方法

1.  **データのアップロード:** 「Comment」列を含むCSVファイルを手動で `feedbackinput` S3バケットにアップロードします。
2.  **分析の待機:** S3トリガーが発火し、Lambdaが実行され、Bedrockを呼び出し、DynamoDBに結果を書き込むまで、1〜2分待ちます。
3.  **ダッシュボードの表示:** S3静的ウェブサイトのURLをブラウザで開きます。ダッシュボードが読み込まれ、最新の分析データがフェッチされるはずです。
4.  **データの確認:** 統計情報、テーブル、チャートを確認します。
5.  **データのエクスポート:** 「Export Full Analysis Data (CSV)」ボタンをクリックして、全データセットをCSVファイルとしてダウンロードします。

## 7. 今後の改善点と考慮事項

*   **DynamoDBスキャン:** テーブル全体のスキャン（`GetStatsLambda`、`ExportCsvLambda`）は、大規模なデータセットでは非効率的でコストがかかります。ページネーションを実装するか、分析クエリのためにAWS Glue/Athena/Redshiftを使用することを検討してください。
*   **LLMコスト/スループット:** 予測可能なコスト/レイテンシのためにBedrockプロビジョンドスループットを検討するか、LLM呼び出しのためにコメントをバッチ処理することを検討してください。
*   **エラー処理:** LambdaエラーやBedrock障害に対するより洗練されたログ記録とアラートを実装します。
*   **フロントエンドの更新:** フルページリロードなしで手動で `fetchAndDisplayStats` をトリガーする「データの更新」ボタンをダッシュボードに追加します。
*   **フィルタリング/検索:** ダッシュボードに、センチメント、カテゴリ、重要度、キーワードでコメントをフィルタリングする機能を追加します。これには、`GetStatsLambda` がクエリパラメータを受け入れ、DynamoDBのQueryまたはScan with filters（または分析ストアをクエリする）を使用するように更新する必要があります。
*   **認証/認可:** 機密データである場合、API GatewayエンドポイントとS3ウェブサイトバケットを保護します。
*   **CI/CD:** AWS SAM、CloudFormation、CDK、またはCodePipeline/CodeBuildのようなツールを使用して、Lambda、API Gateway、フロントエンドのデプロイを自動化します。
*   **より詳細な分析:** コメントからより多くのエンティティ、キーワード、または特定の課題を抽出するために、Bedrockプロンプトを強化するか、モデルを切り替えます。
*   **代替データストア:** 非常に大量のデータまたは複雑なクエリの場合、分析結果をS3（データレイク）またはRedshiftに移行し、AthenaまたはRedshift Spectrumを使用してクエリすることが有益かもしれません。
*   **モデルとデータの評価・改善:**　モデルを入れ替えたり、データについて評価・特徴エンジニアリングしますと、さらによい分析ができます。