import json
import boto3
import os
import csv
import io
from decimal import Decimal # Important for DynamoDB numbers

# --- Configuration ---
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')

# --- AWS Clients ---
# Use the resource for easier table interaction
dynamodb_resource = boto3.resource('dynamodb')
# Initialize table resource globally
table = None
if DYNAMODB_TABLE_NAME: # Only initialize if env var is set
    try:
        table = dynamodb_resource.Table(DYNAMODB_TABLE_NAME)
        print(f"Initialized DynamoDB table resource: {DYNAMODB_TABLE_NAME}")
    except Exception as e:
        print(f"Error initializing DynamoDB table resource '{DYNAMODB_TABLE_NAME}' globally: {e}")
        # Handle this error in the handler function


# --- Lambda Handler Function ---
# Handler name is lambda_handler (standard for API Gateway proxy)
def lambda_handler(event, context):
    """
    API endpoint to export analyzed comments as CSV.
    NOTE: Scanning DynamoDB for export is inefficient for large tables.
    """
    print("Executing ExportCsvLambda (renamed handler).")

    # Check if table resource was initialized
    if table is None:
         print("Error: DynamoDB table resource not initialized.")
         # Return error response with CORS headers
         return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*', # WARNING: Use a specific origin in production!
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            },
            'body': json.dumps({"error": f"Configuration error: DynamoDB table name not set or table resource initialization failed."}),
            'isBase64Encoded': False # Added
         }


    try:
        # You might add logic here to filter which comments to export
        # based on query parameters (e.g., specific category, sentiment)
        # For simplicity, let's export all processed comments.

        print(f"Scanning DynamoDB table '{DYNAMODB_TABLE_NAME}' for export...")
        response = table.scan()
        items = response.get('Items', []) # Use .get with default empty list

        # Handle pagination for large datasets
        while 'LastEvaluatedKey' in response:
            print("Scanning for more results...")
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        print(f"Retrieved {len(items)} items for export.")

        # Define CSV headers
        # Ensure order is consistent
        headers = [
            'CommentID',
            'OriginalComment',
            'ProcessingTimestamp',
            'OriginalCsvRowIndex',
            'Sentiment',
            'Category',
            'Importance',
            'IsHighRisk',
            'BedrockModelId',
            'LLMError', # Include error info if available
            'LLMRawResponseSnippet',
            'LLMStatusCode'
        ]

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, quoting=csv.QUOTE_ALL) # Use QUOTE_ALL for better handling of commas/quotes in text

        writer.writeheader()
        if not items:
            # Write a message row if no data, but still provide headers
             writer.writerow({header: "No data to export." if header == headers[0] else "" for header in headers})
             print("No items found in the table. Writing empty CSV with message row.")
        else:
            for item in items:
                # Process each item to ensure types are suitable for CSV
                row_to_write = {}
                for header in headers:
                    value = item.get(header)

                    # Convert Decimal values to standard types
                    if isinstance(value, Decimal):
                        # Attempt integer conversion if no decimal part, else float, else string
                        try:
                            if value % 1 == 0:
                                 row_to_write[header] = int(value)
                            else:
                                 row_to_write[header] = float(value)
                        except Exception:
                             row_to_write[header] = str(value) # Fallback

                    # Convert Boolean values to string representation ("True" or "False")
                    elif isinstance(value, bool):
                        row_to_write[header] = str(value)

                    # Handle potential string representations of boolean (as seen in past logs)
                    # Ensure these are also represented as "True" or "False" strings in CSV
                    elif header == 'IsHighRisk' and isinstance(value, str):
                         row_to_write[header] = str(value.lower() in ['true', 'yes']) # Convert 'True'/'False'/'Yes'/'No' strings to "True"/"False"

                    # Keep other types as is (string). DictWriter handles None by leaving field empty.
                    else:
                        row_to_write[header] = value # DictWriter will write None as empty string

                writer.writerow(row_to_write)

        csv_content = output.getvalue()
        status_code = 200 # Status is 200 even for empty data

        # --- Return Response ---
        # Return structure for API Gateway Lambda Proxy Integration for non-JSON body
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename="feedback_analysis.csv"',
                 # Add CORS headers for OPTIONS preflight request from frontend if necessary
                 # (Even though window.location.href doesn't send OPTIONS, it's good practice if this endpoint might be used by fetch/XHR later)
                'Access-Control-Allow-Origin': '*', # WARNING: Use a specific origin in production!
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            },
            'body': csv_content,
            'isBase64Encoded': False # <-- CRITICAL: Tell API Gateway the body is plain text
        }

    except Exception as e:
        print(f"Error in ExportCsvLambda: {e}")
        # Return error response with CORS headers
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json', # Error response is JSON
                'Access-Control-Allow-Origin': '*', # WARNING: Use a specific origin in production!
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            },
            'body': json.dumps({"error": f"Internal server error during export: {str(e)}"}),
            'isBase64Encoded': False # Added
        }