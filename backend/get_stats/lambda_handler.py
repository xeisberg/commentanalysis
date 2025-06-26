import json
import boto3
import os
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


# --- Helper Function to Handle Decimal (from DynamoDB) for JSON ---
# ADDED this function back
def decimal_default(obj):
    """JSON serializer for objects not serializable by default (like Decimal)"""
    if isinstance(obj, Decimal):
        # Check if it's an integer-like Decimal (no fractional part)
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    # If it's not a type we know how to serialize, raise the default TypeError
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


# --- Helper Function to Map DynamoDB Item to Frontend-Friendly Dict ---
def map_comment_item(item):
    """Maps a raw DynamoDB item dict to a standard Python dict suitable for JSON."""
    mapped_item = {
        # Use .get() with defaults in case attributes are missing
        'CommentID': item.get('CommentID'),
        'OriginalComment': item.get('OriginalComment', 'No Comment Text'),
        'ProcessingTimestamp': item.get('ProcessingTimestamp'),
        # Safely convert OriginalCsvRowIndex to int
        'OriginalCsvRowIndex': int(item.get('OriginalCsvRowIndex', 0)) if item.get('OriginalCsvRowIndex') is not None else 0, # Handle None explicitly
        'BedrockModelId': item.get('BedrockModelId', 'N/A'),
        'Sentiment': item.get('Sentiment', 'Unknown'),
        'Category': item.get('Category', 'Unknown'),
        # Ensure Importance is an integer
        # Safely convert Importance to int, handling Decimal, None, or empty string
        'Importance': int(item.get('Importance', 0)) if item.get('Importance') is not None else 0,
        # Ensure IsHighRisk is a boolean
        # Safely convert IsHighRisk, handling bool, Decimal 0/1, or 'True'/'False'/'Yes'/'No' strings
        'IsHighRisk': False, # Default to False
        #'IsHighRisk_raw': item.get('IsHighRisk'), # Optional: Keep raw for debugging if needed
    }
    raw_is_high_risk = item.get('IsHighRisk')
    if isinstance(raw_is_high_risk, bool):
         mapped_item['IsHighRisk'] = raw_is_high_risk
    elif isinstance(raw_is_high_risk, Decimal):
         mapped_item['IsHighRisk'] = raw_is_high_risk == Decimal(1)
    elif isinstance(raw_is_high_risk, str):
         mapped_item['IsHighRisk'] = raw_is_high_risk.lower() in ['true', 'yes']


    # Include error details if present
    mapped_item['LLMError'] = item.get('LLMError')
    mapped_item['LLMRawResponseSnippet'] = item.get('LLMRawResponseSnippet')
    # Safely handle LLMStatusCode conversion to int if possible
    raw_status_code = item.get('LLMStatusCode')
    if raw_status_code is not None:
        try:
            mapped_item['LLMStatusCode'] = int(raw_status_code)
        except (ValueError, TypeError):
            mapped_item['LLMStatusCode'] = str(raw_status_code) # Store as string if not int


    # Filter out attributes with None values
    return {k: v for k, v in mapped_item.items() if v is not None}


# --- Helper Function to Return Empty Stats ---
def get_empty_stats():
    """Returns an empty stats dictionary matching the expected structure."""
    return {
        "total_comments": 0,
        "total_processable_comments": 0,
        "sentiment_counts": {},
        "sentiment_percentages": {},
        "category_counts": {},
        "category_percentages": {},
        "high_risk_count": 0,
        "recommended_actions": {},
        "top_important_comments": [],
        "high_risk_comments_list": []
    }


# --- Lambda Handler Function ---
# Handler name is lambda_handler
def lambda_handler(event, context):
    """
    API endpoint to get aggregated statistics (counts, percentages) from DynamoDB.
    """
    print("Executing GetStatsLambda (renamed handler).")

    # Check if table resource was initialized
    # This also implicitly checks if DYNAMODB_TABLE_NAME was set
    if table is None:
         print("Error: DynamoDB table resource not initialized. DYNAMODB_TABLE_NAME environment variable might be missing.")
         # Return error response with CORS headers
         return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'},
            'body': json.dumps({"error": f"Configuration error: DynamoDB table resource initialization failed. Is DYNAMODB_TABLE_NAME environment variable set correctly?"})
         }


    try:
        # --- 1. Retrieve all items from DynamoDB ---
        print(f"Scanning DynamoDB table '{DYNAMODB_TABLE_NAME}' for stats...")
        response = table.scan()
        items = response.get('Items', []) # Use .get with default empty list

        # Handle pagination
        while 'LastEvaluatedKey' in response:
            print("Scanning for more results...")
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        print(f"Retrieved {len(items)} items from DynamoDB.")

        # --- 2. Handle Case with No Items ---
        if not items:
             print("No items found in the table. Returning empty stats.")
             # Add CORS headers here as well
             return {
                 'statusCode': 200,
                 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'},
                 'body': json.dumps(get_empty_stats()) # Return the standard empty structure
             }

        # --- 3. Aggregate Data ---
        total_comments = len(items) # This is the total number of rows in the table
        sentiment_counts = {}
        category_counts = {}
        high_risk_count = 0
        processable_comments = [] # Store comments that were successfully analyzed or had LLM errors

        for item in items:
            # Map the item to a cleaner structure early in the loop
            mapped_item = map_comment_item(item)

            # Only count stats for items that were NOT explicitly skipped as empty
            if mapped_item.get('Sentiment') != 'Skipped - Empty':
                 sentiment = mapped_item.get('Sentiment', 'Unknown')
                 category = mapped_item.get('Category', 'Unknown')
                 is_high_risk = mapped_item.get('IsHighRisk', False) # Already boolean from map_comment_item
                 importance = mapped_item.get('Importance', 0)     # Already int from map_comment_item

                 sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
                 category_counts[category] = category_counts.get(category, 0) + 1

                 if is_high_risk:
                     high_risk_count += 1

                 # Add items that weren't just skips to a list for filtering/sorting
                 # The item is already mapped and clean
                 processable_comments.append(mapped_item)


        # Recalculate total comments for percentage base, excluding explicit skips
        total_processable_comments = len(processable_comments) # Count of items in the processable_comments list
        # Handle case where all items might have been skips, resulting in processable_comments being empty
        if total_processable_comments == 0:
             print("No processable comments found for stats aggregation. Returning empty stats.")
             # Add CORS headers here as well
             return {
                 'statusCode': 200,
                 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'},
                 'body': json.dumps(get_empty_stats())
             }


        # Calculate percentages based on the total number of *processable* comments
        sentiment_percentages = {k: (v / total_processable_comments) * 100 for k, v in sentiment_counts.items()}
        category_percentages = {k: (v / total_processable_comments) * 100 for k, v in category_counts.items()}


        # Determine Recommended Action flags (example logic, based on processed comments)
        recommended_actions = {}
        # Base recommendation logic on the *percentages* calculated from processable comments
        # You might also add a recommended action if high_risk_count > 0 regardless of category percentage
        # Example: Recommend action if percentage for a category is significant (e.g., > 5%) OR if there's at least one high risk item in that category (requires filtering processable_comments by category and checking IsHighRisk)
        # For simplicity, using percentage only as before:
        for category, percentage in category_percentages.items():
             if percentage > 5: # Example threshold
                 recommended_actions[category] = True
             else:
                 recommended_actions[category] = False


        # --- 4. Prepare Filtered/Sorted Lists ---

        # Sort processable comments by Importance (high to low)
        # Use the already mapped items which have integer Importance
        sorted_processable_comments = sorted(processable_comments, key=lambda x: x.get('Importance', 0), reverse=True)

        # Identify top important comments (e.g., all with Importance >= 4)
        top_important_comments_list = [
            item for item in sorted_processable_comments
            if item.get('Importance', 0) >= 4
        ]
        # Optional: Limit the list length if needed for the frontend display
        # top_important_comments_list = top_important_comments_list[:20]


        # Identify high-risk comments list (filtered from processable_comments)
        high_risk_comments_list = [
            item for item in processable_comments
            if item.get('IsHighRisk', False) is True # Check the boolean field from mapped item
        ]


        # --- 5. Construct Final Stats Dictionary ---
        # --- 5. Construct Final Stats Dictionary ---
        stats = {
            "total_comments": total_comments,
            "total_processable_comments": total_processable_comments,
            "sentiment_counts": sentiment_counts,
            "sentiment_percentages": sentiment_percentages,
            "category_counts": category_counts,
            "category_percentages": category_percentages,
            "high_risk_count": high_risk_count,
            "recommended_actions": recommended_actions,
            "top_important_comments": top_important_comments_list,
            "high_risk_comments_list": high_risk_comments_list,
            # ADD THIS LINE to return the full list of processable comments
            "all_mapped_comments_list": processable_comments
        }

        print("Stats generated:", json.dumps(stats, default=decimal_default))


        # --- 6. Return Response ---
        # Use the helper function 'decimal_default' to handle any Decimal types that might still be present
        # although most should be handled by map_comment_item
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                 # Add CORS headers if the frontend is on a different domain/port
                'Access-Control-Allow-Origin': '*', # WARNING: Use a specific origin in production!
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            },
            'body': json.dumps(stats, default=decimal_default)
        }

    except Exception as e:
        print(f"Error in GetStatsLambda: {e}")
        # Return error response with CORS headers too
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json', # Error response is JSON
                'Access-Control-Allow-Origin': '*', # WARNING: Use a specific origin in production!
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            },
            'body': json.dumps({"error": f"Internal server error during stats retrieval: {str(e)}"})
        }