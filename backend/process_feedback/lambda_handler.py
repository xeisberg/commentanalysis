import json
import boto3
import os
import csv
import uuid
import io
import urllib.parse
import datetime
import re # Import regular expressions for robust JSON extraction
# import time # Not used, can remove

# --- Configuration (Using Environment Variables) ---
# Make sure these environment variables are set in your Lambda function configuration
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
# Set this to 'amazon.titan-text-express-v1' or similar on-demand Titan Text model
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID')

# --- Constants ---
COMMENT_COLUMN_NAME = 'Comment' # The expected name of the column with comments

# --- AWS Clients (Initialized Globally for potential reuse) ---
# Using configuration from the environment/Lambda execution role
s3_client = boto3.client('s3')
dynamodb_resource = boto3.resource('dynamodb')
bedrock_runtime_client = boto3.client('bedrock-runtime')

# --- Prompt Definition ---
# Define the core instruction for the model.
# Simplified for Titan Text Express: just provide the instruction and comment,
# remove conversational turns (User:/Assistant:) and explicit markdown fences
# from the *instruction text itself*. The request body config handles parameters.
# Keep the instruction simple, rely on parsing robustness for varied output.
instruction = """Analyze the following feedback comment and provide the analysis results as a JSON object.

The JSON object must contain the following keys and value types:
- sentiment (string: "Positive", "Negative", "Neutral", "Mixed")
- category (string: "Lecture Content", "Lecture Materials", "Operations", "Other")
- importance (integer: 1 to 5, where 5 is highest urgency/impact)
- isHighRisk (boolean: true or false)

Respond **EXACTLY and ONLY** with the JSON object. Do NOT include any other text, explanations, or conversational filler before or after the JSON object."""

# The prompt template for Amazon Titan Text models ( inputText format)
# Simple structure: instruction followed by the comment.
# Use double curly braces {{}} for .format() placeholder.
bedrock_prompt_template = f"""{instruction}

Comment: {{comment_placeholder}}
"""

# --- Main Lambda Handler Function ---
def lambda_handler(event, context):
    """
    AWS Lambda handler to process CSV feedback from S3,
    analyze using Amazon Bedrock, and store results in DynamoDB.
    """
    print("Lambda function started (Bedrock version).")
    # print("Event:", json.dumps(event)) # Use caution when logging full event in production

    # --- 1. Extract S3 Bucket and Key from Event ---
    bucket_name = None
    object_key = None
    file_size = 0 # Initialize file size

    # Check for S3 trigger event structure
    if 'Records' in event and len(event['Records']) > 0 and 's3' in event['Records'][0]:
        print("Detected S3 trigger event.")
        s3_record = event['Records'][0]['s3']
        bucket_name = s3_record['bucket']['name']
        object_key = urllib.parse.unquote_plus(s3_record['object']['key'])
        file_size = s3_record['object'].get('size', 0)
        print(f"File size: {file_size} bytes")
        if file_size == 0:
             print("Warning: Received trigger for 0-byte file, skipping.")
             return {'statusCode': 200, 'body': json.dumps('Skipped 0-byte file.')}

    # Allow a simple manual test event structure for debugging/testing
    elif 'bucket_name' in event and 'object_key' in event:
         print("Detected potential manual test event.")
         bucket_name = event['bucket_name']
         object_key = event['object_key']
         # For manual test, we don't have size easily, proceed assuming non-zero
         print(f"Manual trigger for s3://{bucket_name}/{object_key}")
    else:
         print("Error: Could not determine S3 bucket and key from event.")
         # print("Event structure:", json.dumps(event)) # Avoid logging potentially sensitive event data structure
         return {
             'statusCode': 400,
             'body': json.dumps('Invalid event structure. Expecting S3 trigger or manual input with bucket_name and object_key.')
         }

    print(f"Attempting to process s3://{bucket_name}/{object_key}")

    # --- Validate Environment Variables ---
    # Check *after* extracting S3 info so we can return 400 for bad event structure first
    if not all([S3_BUCKET_NAME, DYNAMODB_TABLE_NAME, BEDROCK_MODEL_ID]):
         missing_vars = [var_name for var_name, var_value in {'S3_BUCKET_NAME': S3_BUCKET_NAME, 'DYNAMODB_TABLE_NAME': DYNAMODB_TABLE_NAME, 'BEDROCK_MODEL_ID': BEDROCK_MODEL_ID}.items() if not var_value]
         print(f"Error: Required environment variables are not set: {', '.join(missing_vars)}")
         return {
             'statusCode': 500,
             'body': json.dumps(f'Configuration error: Missing environment variables: {", ".join(missing_vars)}.')
         }
    # --- Add a log about the selected model ---
    print(f"Using Bedrock model: {BEDROCK_MODEL_ID}")

    # Optional: Validate that the event bucket matches the configured bucket
    # This adds a safety check, uncomment if you *only* want to process files
    # from the bucket specified in the environment variable.
    # if bucket_name != S3_BUCKET_NAME:
    #     print(f"Error: Event bucket '{bucket_name}' does not match configured bucket '{S3_BUCKET_NAME}'. Stopping.")
    #     return {
    #         'statusCode': 400,
    #         'body': json.dumps(f'Bucket mismatch: Event bucket {bucket_name} does not match configured bucket {S3_BUCKET_NAME}. Processing stopped.')
    #     }
    # else:
    #      print(f"Event bucket '{bucket_name}' matches configured bucket '{S3_BUCKET_NAME}'.")


    # --- Initialize DynamoDB Table Resource ---
    try:
        dynamodb_table = dynamodb_resource.Table(DYNAMODB_TABLE_NAME)
        print(f"Initialized DynamoDB table resource: {DYNAMODB_TABLE_NAME}")
    except Exception as e:
        print(f"Error initializing DynamoDB table resource '{DYNAMODB_TABLE_NAME}': {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error initializing DynamoDB: {e}')
        }

    # --- 2. Download CSV from S3 ---
    csv_content = None
    try:
        print(f"Downloading s3://{bucket_name}/{object_key}...")
        # Use the bucket_name and object_key obtained from the event trigger
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        csv_content = response['Body'].read().decode('utf-8')
        print(f"File downloaded successfully. Content length: {len(csv_content)} characters.")
    except Exception as e:
        print(f"Error downloading file {object_key} from bucket {bucket_name}: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error downloading file from S3: {e}')
        }

    # --- 3. Parse CSV and Extract Comments ---
    comments = []
    try:
        csv_file = io.StringIO(csv_content)
        # Use DictReader with explicit fieldnames if possible, or handle errors
        # more robustly if headers might be missing or malformed.
        # For now, assume DictReader handles header reading correctly.
        csv_reader = csv.DictReader(csv_file)

        # Store original fieldnames in case we need to add missing ones later
        fieldnames = csv_reader.fieldnames

        if COMMENT_COLUMN_NAME not in fieldnames:
            error_message = f"Error: CSV file '{object_key}' does not contain a '{COMMENT_COLUMN_NAME}' column. Found columns: {fieldnames}"
            print(error_message)
            return {
                'statusCode': 400,
                'body': json.dumps(error_message)
            }

        print(f"CSV headers detected: {fieldnames}")
        # Store comments as dictionaries to keep original index
        for i, row in enumerate(csv_reader):
            comment_text = row.get(COMMENT_COLUMN_NAME)
            # Store even empty/whitespace comments but flag them later
            # We store them now to keep track of the original row index for *all* rows after the header
            comments.append({'text': comment_text, 'original_row_index': i + 2}) # +2 for header and 0-based index


        print(f"Parsed {len(comments)} rows (including empty/whitespace comments) from CSV.")

    except Exception as e:
        print(f"Error parsing CSV file '{object_key}': {e}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error parsing CSV: {e}')
        }

    if not comments:
        print("No rows found after header in the CSV file. Exiting.")
        return {
            'statusCode': 200,
            'body': json.dumps('No comments processed as no rows were found after the header.')
        }

    # --- 4. Loop through Comments, Call Bedrock, Parse Response, Write to DDB ---
    # Using counters to track outcomes
    successfully_analyzed_and_stored = 0 # Successfully analyzed by LLM and written to DDB
    skipped_empty_comments = 0   # Comments skipped due to being empty/whitespace
    failed_llm_analysis = 0      # LLM call failed OR parsing LLM response failed
    failed_ddb_write = 0         # DDB write failed (after potential LLM analysis/skip)

    for i, comment_info in enumerate(comments):
        comment = comment_info.get('text', '') # Use .get with default empty string
        original_row_index = comment_info['original_row_index']

        unique_id = str(uuid.uuid4()) # Unique ID for this comment item

        print(f"\n--- Processing item for Original Row: {original_row_index} (ID: {unique_id[:8]}...) ---")
        print(f"Comment text (raw): '{comment[:200]}{'...' if len(comment) > 200 else ''}'")

        # --- Add Safety Check for Empty/Whitespace Comments ---
        if not comment or not comment.strip():
             print(f"Comment at original row {original_row_index} is empty or whitespace-only. Skipping LLM analysis.")
             skipped_empty_comments += 1
             # Store a placeholder item in DDB indicating it was skipped
             ddb_item = {
                 'CommentID': unique_id,
                 'OriginalComment': comment, # Store the original value (might be empty string)
                 'ProcessingTimestamp': datetime.datetime.utcnow().isoformat(),
                 'OriginalCsvRowIndex': original_row_index,
                 'Sentiment': 'Skipped - Empty',
                 'Category': 'Skipped - Empty',
                 'Importance': 0, # Default numeric/boolean values
                 'IsHighRisk': False,
                 'LLMError': 'Comment was empty or whitespace-only',
                 'BedrockModelId': 'N/A' # No LLM call was made
             }
             try:
                 print(f"Writing skipped item {unique_id} to DynamoDB...")
                 dynamodb_table.put_item(Item=ddb_item)
                 print(f"Successfully wrote skipped item {unique_id}.")
             except Exception as ddb_e:
                 print(f"Error writing skipped item {unique_id} to DynamoDB: {ddb_e}")
                 failed_ddb_write += 1 # Count DDB write failure even for skipped items

             # failed_llm_analysis is *not* incremented here because the LLM was not called due to the check
             continue # Skip to the next comment in the loop
        # --- End Safety Check ---


        # --- Construct Bedrock Prompt ---
        bedrock_prompt = bedrock_prompt_template.format(comment_placeholder=comment)
        # Print a snippet of the full prompt
        print(f"Full Bedrock Prompt (snippet):\n---\n{bedrock_prompt[:500]}{'...' if len(bedrock_prompt) > 500 else ''}\n---")


        # --- Prepare Bedrock Request Body ---
        bedrock_request_body = {
            "inputText": bedrock_prompt,
            "textGenerationConfig": {
                "maxTokenCount": 500,
                "temperature": 0.1, # Low temp for deterministic/structured output
                "topP": 1,
                # Omit stopSequences entirely if not needed or causing issues
            }
        }

        # Convert the body dictionary to a JSON string bytes
        body_bytes = json.dumps(bedrock_request_body).encode('utf-8')

        # --- Call Bedrock API and Process Response ---
        sentiment_data = None # Initialize to None before the Bedrock/Parsing try block
        bedrock_api_error = None # Store Bedrock API error if it occurs
        raw_llm_response_text = None # Initialize raw text to None

        try: # This try block catches Bedrock API call errors
            print(f"Calling Bedrock API with model {BEDROCK_MODEL_ID}...")
            bedrock_response = bedrock_runtime_client.invoke_model(
                body=body_bytes,
                modelId=BEDROCK_MODEL_ID,
                contentType='application/json',
                accept='application/json'
            )
            print("Bedrock API call successful.")

            # --- Parse the Bedrock response body (specific to Titan Text models) ---
            response_body = bedrock_response['body'].read().decode('utf-8')
            bedrock_raw_response_body_str = response_body
            # print("Bedrock Response Body:", json.dumps(json.loads(response_body), indent=2)) # Uncomment for detailed debugging

            response_body_json = json.loads(response_body)

            if 'results' in response_body_json and len(response_body_json['results']) > 0:
                 raw_llm_response_text = response_body_json['results'][0].get('outputText')
                 if raw_llm_response_text is None:
                      print("Warning: Bedrock response 'results' found, but 'outputText' is missing or None.")
                      # raw_llm_response_text remains None, parsing block will handle it


                 print(f"Extracted outputText: '{raw_llm_response_text[:500]}{'...' if len(raw_llm_response_text) > 500 else ''}'")
            else:
                 print("Warning: Bedrock response did not contain expected 'results' or 'outputText' structure.")
                 # Set sentiment_data to indicate output structure issue immediately
                 sentiment_data = {'Error': 'Bedrock output structure unexpected', 'RawResponseSnippet': bedrock_raw_response_body_str[:500]}
                 failed_llm_analysis += 1 # Count as LLM analysis failure


        except bedrock_runtime_client.exceptions.ModelErrorException as model_err:
             error_message = model_err.message
             status_code = model_err.response['ResponseMetadata']['HTTPStatusCode']
             error_body = model_err.response.get('body', b'').decode('utf-8')

             print(f"Bedrock Model Error for comment '{comment[:50]}...': Status: {status_code}, Message: {error_message}, Body: {error_body[:200]}")
             # Store Bedrock API error details in bedrock_api_error, parsing won't happen
             bedrock_api_error = {
                 'Error': f'Bedrock Model Error: {error_message}',
                 'StatusCode': status_code,
                 'RawResponseSnippet': error_body[:500]
             }
             failed_llm_analysis += 1 # Count as LLM analysis failure (call failed)
        except Exception as e:
             print(f"An unexpected error occurred during Bedrock call setup or initial response read for comment '{comment[:50]}...': {e}")
             # Store general Bedrock call error details
             bedrock_api_error = {'Error': f'Unexpected Bedrock call error: {e}', 'RawResponseSnippet': None}
             failed_llm_analysis += 1 # Count as LLM analysis failure (call failed)


        # --- Attempt to parse the extracted text as JSON (ONLY if Bedrock call succeeded and no structural error) ---
        # This try block catches errors during parsing the outputText
        if raw_llm_response_text is not None and sentiment_data is None: # Only try parsing if we got outputText and no output structure error
             try:
                  text_to_parse = raw_llm_response_text.strip()
                  json_object_str = None # Variable to hold the string that should be JSON

                  # **Revised JSON extraction logic:** Find the first { and last }
                  first_brace = text_to_parse.find('{')
                  last_brace = text_to_parse.rfind('}')

                  if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                      # Extract the content between the first { and last } (inclusive)
                      json_object_str = text_to_parse[first_brace : last_brace + 1].strip()
                      print(f"Extracted potential JSON object using first {{ and last }}.")
                  else:
                      # If curly braces aren't found, it's not a valid JSON object output
                      print("Error: Could not find JSON object markers ({}) in Bedrock output.")
                      # Set sentiment_data to an error state to be stored in DDB
                      sentiment_data = {'Error': 'Could not find JSON object in output text', 'RawResponseSnippet': raw_llm_response_text[:500]}
                      failed_llm_analysis += 1 # Count as LLM analysis failure
                      # Skip the json.loads step below


                  # Now attempt to parse the extracted string (if extraction was successful)
                  if json_object_str and sentiment_data is None: # Check sentiment_data is still None (no extraction error)
                     parsed_json_data = json.loads(json_object_str)
                     print("Successfully parsed extracted JSON string.")

                     # --- Add logic to handle the {"rows": [...]} wrapping ---
                     if isinstance(parsed_json_data, dict) and 'rows' in parsed_json_data and isinstance(parsed_json_data['rows'], list) and len(parsed_json_data['rows']) > 0 and isinstance(parsed_json_data['rows'][0], dict):
                          # Found the expected wrapping, extract the inner dictionary
                          sentiment_data = parsed_json_data['rows'][0]
                          print("Unwrapped JSON from {'rows': [...]} structure.")
                     else:
                          # Assume the parsed data IS the expected sentiment_data structure
                          sentiment_data = parsed_json_data
                          print("Parsed JSON is the expected structure (or unwrapping not needed).")


                     # Basic validation of parsed JSON structure and types (using the potentially unwrapped data)
                     if sentiment_data: # Ensure sentiment_data is not None after unwrapping attempt
                         expected_keys = ['sentiment', 'category', 'importance', 'isHighRisk']
                         missing_keys = [key for key in expected_keys if key not in sentiment_data]
                         if missing_keys:
                             print(f"Warning: Parsed JSON response missing expected keys: {missing_keys}. Data: {sentiment_data}")
                             # We still count this as a successful analysis/parse, but log the warning.

                         # Optional: Validate value types/ranges if needed more strictly before DDB write
                         # e.g., Check if sentiment is one of the allowed strings, importance is 1-5, isHighRisk is bool

                     else: # This case means parsed_json_data was empty or did not contain the expected 'rows' structure correctly
                         print("Error: Parsed JSON data was unexpectedly empty or invalid after unwrapping attempt.")
                         sentiment_data = {'Error': 'Parsed JSON empty or invalid after unwrapping', 'RawResponseSnippet': json_object_str[:500]}
                         failed_llm_analysis += 1 # Count as LLM analysis failure


             except json.JSONDecodeError as j:
                  print(f"Error parsing extracted content as JSON: {j}")
                  print(f"Content that failed parsing: '{json_object_str}'") # Log the extracted content that failed
                  sentiment_data = {'Error': f'JSON parsing failed: {j}', 'RawResponseSnippet': json_object_str[:500]}
                  failed_llm_analysis += 1 # Count as LLM analysis failure
             except Exception as e: # Catch other potential errors during parsing/unwrapping
                  print(f"Unexpected error during Bedrock output parsing/unwrapping: {e}")
                  # Log the content that caused error if available, default to raw outputText
                  content_snippet = json_object_str[:500] if json_object_str else (raw_llm_response_text[:500] if raw_llm_response_text else None)
                  sentiment_data = {'Error': f'Bedrock content parsing/unwrapping error: {e}', 'RawResponseSnippet': content_snippet}
                  failed_llm_analysis += 1 # Count as LLM analysis failure

        # Note: If raw_llm_response_text was None initially, sentiment_data remains None or was set by the output structure check.
        # If Bedrock API failed, sentiment_data was set by the except block.
        # The logic below now correctly handles sentiment_data being None, an error dict, or a parsed result dict.


        # --- Prepare Data Item for DynamoDB ---
        ddb_item = {
            'CommentID': unique_id,
            'OriginalComment': comment,
            'ProcessingTimestamp': datetime.datetime.utcnow().isoformat(),
            'OriginalCsvRowIndex': original_row_index,
            'BedrockModelId': BEDROCK_MODEL_ID # Always record which model was attempted (even if analysis failed)
        }

        # Add analysis results or error info based on sentiment_data
        if sentiment_data and 'Error' not in sentiment_data:
            # Successfully parsed analysis results (after potential unwrapping)
            print(f"Mapping analysis results to DynamoDB item structure for {unique_id}.")
            # Use .get with a default in case the model misses a key or provides None/empty
            ddb_item['Sentiment'] = sentiment_data.get('sentiment', 'Unknown')
            ddb_item['Category'] = sentiment_data.get('category', 'Unknown')

            # Handle Importance (must be DynamoDB Number)
            # Get importance, defaulting to 0 if key is missing
            importance = sentiment_data.get('importance')
            try:
                # Ensure it's treated as a number; int() is fine for DynamoDB Number type
                # Handle cases where model might return importance as a string like "4" (as seen in logs)
                ddb_item['Importance'] = int(importance) if importance is not None and importance != '' else 0
            except (ValueError, TypeError):
                 print(f"Warning: Could not parse Importance '{importance}' as integer for item {unique_id}. Storing as 0.")
                 ddb_item['Importance'] = 0 # Default to 0 on parse failure

            # Handle IsHighRisk (must be DynamoDB Boolean)
            # Get risk, defaulting to False if key is missing
            risk = sentiment_data.get('isHighRisk')
            # Check explicitly for Python bool True/False or string representations ('true', 'false', 'yes', 'no')
            if isinstance(risk, bool):
                 ddb_item['IsHighRisk'] = risk
            elif isinstance(risk, str):
                 risk_lower = risk.lower()
                 if risk_lower in ['true', 'yes']:
                     ddb_item['IsHighRisk'] = True
                 elif risk_lower in ['false', 'no']:
                      ddb_item['IsHighRisk'] = False
                 else:
                      print(f"Warning: Could not parse IsHighRisk string '{risk}' as boolean for item {unique_id}. Storing as False.")
                      ddb_item['IsHighRisk'] = False # Default to False on unparseable string
            else:
                 print(f"Warning: Could not parse IsHighRisk value '{risk}' as boolean for item {unique_id}. Storing as False.")
                 ddb_item['IsHighRisk'] = False # Default to False for unexpected types

        elif sentiment_data and 'Error' in sentiment_data:
            # Bedrock call or parsing failed, add error details
            print(f"Storing error details for item {unique_id} (Original Row: {original_row_index}) due to LLM analysis/parsing failure.")
            ddb_item['LLMError'] = sentiment_data['Error']
            if sentiment_data.get('RawResponseSnippet') is not None:
                 ddb_item['LLMRawResponseSnippet'] = sentiment_data['RawResponseSnippet']
            if sentiment_data.get('StatusCode') is not None:
                 # Ensure StatusCode is stored as a Number if it's an int
                 try:
                      ddb_item['LLMStatusCode'] = int(sentiment_data['StatusCode'])
                 except (ValueError, TypeError):
                      ddb_item['LLMStatusCode'] = str(sentiment_data['StatusCode']) # Store as string if not int

            # Store 'Failed Analysis' status and default values for primary attributes
            ddb_item['Sentiment'] = 'Failed Analysis'
            ddb_item['Category'] = 'Failed Analysis'
            ddb_item['Importance'] = 0
            ddb_item['IsHighRisk'] = False
            # BedrockModelId is already added above


        # --- Put Item into DynamoDB ---
        try:
            print(f"Writing item {unique_id} (Original Row: {original_row_index}) to DynamoDB table {DYNAMODB_TABLE_NAME}...")
            # Boto3 `put_item` automatically handles Python data types (str, int, bool, list, dict, None)
            # None values mean the attribute is simply not included in the item.
            item_to_write = {k: v for k, v in ddb_item.items() if v is not None}

            response = dynamodb_table.put_item(
                Item=item_to_write
            )
            print(f"Successfully wrote item {unique_id} to DynamoDB. Status: {response.get('ResponseMetadata',{}).get('HTTPStatusCode')}")
            # Increment success counter only if LLM analysis succeeded AND DDB write succeeded
            if sentiment_data and 'Error' not in sentiment_data:
                 successfully_analyzed_and_stored += 1

        except Exception as e:
            print(f"Error writing item {unique_id} to DynamoDB: {e}")
            failed_ddb_write += 1


    print(f"\n--- Lambda function finished processing {len(comments)} original rows ---")
    total_rows_from_csv = len(comments)

    print(f"\n--- Final Summary ---")
    print(f"Total comments found in CSV: {total_rows_from_csv}")
    print(f"Comments skipped (empty/whitespace): {skipped_empty_comments}")
    print(f"LLM analysis failed or parsing response failed: {failed_llm_analysis}")
    print(f"Successfully analyzed by LLM and stored in DDB: {successfully_analyzed_and_stored}")
    print(f"DynamoDB write failed: {failed_ddb_write}")


    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'CSV processing complete. Total comments found: {total_rows_from_csv}.',
            'comments_skipped_empty': skipped_empty_comments,
            'llm_analysis_failed': failed_llm_analysis,
            'successfully_analyzed_and_stored': successfully_analyzed_and_stored,
            'dynamodb_write_failed': failed_ddb_write,
            'file_processed': f's3://{bucket_name}/{object_key}'
        })
    }