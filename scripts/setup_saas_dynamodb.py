#!/usr/bin/env python3
"""setup_saas_dynamodb.py — Idempotently provisions the multi-tenant DynamoDB tables for Fuse SaaS.

Tables created:
1. Fuse_Tenants (PK: tenant_id [S])
   Stores customer AWS Account IDs, External IDs, subscription tiers, and registered APIs.
2. Fuse_Tenant_Incidents (PK: tenant_id [S], SK: timestamp_incident_id [S])
   Stores row-level isolated audit logs per tenant with GSI 'tenant-classification-index'.

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


def create_tenants_table(client):
    table_name = "Fuse_Tenants"
    if table_exists(client, table_name):
        print(f"[-] Table '{table_name}' already exists. Skipping.")
        return

    print(f"[+] Creating '{table_name}' table...")
    client.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "tenant_id", "KeyType": "HASH"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "tenant_id", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    waiter = client.get_waiter("table_exists")
    waiter.wait(TableName=table_name)
    print(f"[SUCCESS] Table '{table_name}' created and ACTIVE.")


def create_tenant_incidents_table(client):
    table_name = "Fuse_Tenant_Incidents"
    if table_exists(client, table_name):
        print(f"[-] Table '{table_name}' already exists. Skipping.")
        return

    print(f"[+] Creating '{table_name}' table with composite tenant partition...")
    client.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "tenant_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp_incident_id", "KeyType": "RANGE"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "tenant_id", "AttributeType": "S"},
            {"AttributeName": "timestamp_incident_id", "AttributeType": "S"},
            {"AttributeName": "classification", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "tenant-classification-index",
                "KeySchema": [
                    {"AttributeName": "tenant_id", "KeyType": "HASH"},
                    {"AttributeName": "classification", "KeyType": "RANGE"},
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


def main():
    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "ap-south-1"
    )
    print(f"Connecting to DynamoDB in region: {region}")
    client = get_dynamodb_client(region)

    try:
        create_tenants_table(client)
        create_tenant_incidents_table(client)
        print("\n[ALL COMPLETE] Multi-Tenant SaaS DynamoDB tables are verified.")
    except ClientError as e:
        print(f"\n[ERROR] AWS API call failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
