#!/usr/bin/env python3
"""setup_dynamodb.py — Idempotently creates the three DynamoDB tables for AWS Cost Guardrail.

Tables created:
1. Deployments (PK: deployment_id [S])
2. Incidents (PK: incident_id [S], GSI: environment-timestamp-index [PK: environment (S), SK: timestamp (N)])
3. ApprovalQueue (PK: approval_id [S])

BillingMode: PAY_PER_REQUEST (On-Demand)
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError


def get_dynamodb_client(region: str):
    return boto3.client("dynamodb", region_name=region)


def table_exists(client, table_name: str) -> bool:
    try:
        client.describe_table(TableName=table_name)
        return True
    except client.exceptions.ResourceNotFoundException:
        return False


def create_deployments_table(client):
    table_name = "Deployments"
    if table_exists(client, table_name):
        print(f"[-] Table '{table_name}' already exists. Skipping.")
        return

    print(f"[+] Creating '{table_name}' table...")
    client.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "deployment_id", "KeyType": "HASH"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "deployment_id", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)
    print(f"[SUCCESS] Table '{table_name}' created and ACTIVE.")


def create_incidents_table(client):
    table_name = "Incidents"
    if table_exists(client, table_name):
        print(f"[-] Table '{table_name}' already exists. Skipping.")
        return

    print(f"[+] Creating '{table_name}' table with GSI 'environment-timestamp-index'...")
    client.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "incident_id", "KeyType": "HASH"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "incident_id", "AttributeType": "S"},
            {"AttributeName": "environment", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "N"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "environment-timestamp-index",
                "KeySchema": [
                    {"AttributeName": "environment", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {
                    "ProjectionType": "ALL"
                },
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)
    print(f"[SUCCESS] Table '{table_name}' created and ACTIVE.")


def create_approval_queue_table(client):
    table_name = "ApprovalQueue"
    if table_exists(client, table_name):
        print(f"[-] Table '{table_name}' already exists. Skipping.")
        return

    print(f"[+] Creating '{table_name}' table...")
    client.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "approval_id", "KeyType": "HASH"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "approval_id", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)
    print(f"[SUCCESS] Table '{table_name}' created and ACTIVE.")


def main():
    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "ap-south-1"
    )
    print(f"Connecting to DynamoDB in region: {region}")
    client = get_dynamodb_client(region)

    try:
        create_deployments_table(client)
        create_incidents_table(client)
        create_approval_queue_table(client)
        print("\n[ALL COMPLETE] All three DynamoDB tables are verified.")
    except ClientError as e:
        print(f"\n[ERROR] AWS API call failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
