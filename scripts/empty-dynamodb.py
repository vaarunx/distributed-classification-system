#!/usr/bin/env python3
"""Empty DynamoDB table by scanning and deleting all items"""
import boto3
import sys
import subprocess
import json
from pathlib import Path

# Try to get table name from Terraform, fallback to default
def get_table_name():
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    terraform_dir = project_dir / "terraform"
    
    if terraform_dir.exists():
        # Try direct output first
        try:
            result = subprocess.run(
                ["terraform", "output", "-raw", "dynamodb_table"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True
            )
            table_name = result.stdout.strip()
            if table_name:
                return table_name
        except Exception:
            pass
        
        # Try aws_resources nested output
        try:
            result = subprocess.run(
                ["terraform", "output", "-json", "aws_resources"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                check=True
            )
            resources = json.loads(result.stdout)
            table_name = resources.get("dynamodb_table", "")
            if table_name:
                return table_name
        except Exception:
            pass
    
    # Fallback to default
    print("Using default table name: distributed-classifier-jobs")
    return "distributed-classifier-jobs"

TABLE_NAME = get_table_name()

def main():
    dynamodb = boto3.client('dynamodb')
    
    print(f"Scanning and deleting all items from {TABLE_NAME}...")
    
    items_to_delete = []
    last_evaluated_key = None
    total_scanned = 0
    
    while True:
        if last_evaluated_key:
            response = dynamodb.scan(
                TableName=TABLE_NAME,
                ExclusiveStartKey=last_evaluated_key
            )
        else:
            response = dynamodb.scan(TableName=TABLE_NAME)
        
        items = response.get('Items', [])
        total_scanned += len(items)
        
        for item in items:
            items_to_delete.append({
                'job_id': item['job_id']
            })
        
        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key:
            break
        
        print(f"  Scanned {total_scanned} items...")
    
    print(f"Found {len(items_to_delete)} items. Deleting...")
    
    if len(items_to_delete) == 0:
        print("Table is already empty")
        return 0
    
    # Delete in batches of 25 (DynamoDB batch write limit)
    deleted = 0
    for i in range(0, len(items_to_delete), 25):
        batch = items_to_delete[i:i+25]
        
        delete_requests = [{'DeleteRequest': {'Key': item}} for item in batch]
        
        dynamodb.batch_write_item(
            RequestItems={
                TABLE_NAME: delete_requests
            }
        )
        
        deleted += len(batch)
        if deleted % 1000 == 0 or deleted == len(items_to_delete):
            print(f"  Deleted {deleted}/{len(items_to_delete)} items...")
    
    print(f"Successfully deleted {deleted} items from {TABLE_NAME}")
    return 0

if __name__ == '__main__':
    sys.exit(main())

