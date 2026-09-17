#!/usr/bin/env python3
"""deploy_heartbeat.py — Records a deployment heartbeat in DynamoDB.

Called at the end of a deployment step for the protected demo API.
The poller Lambda reads the Deployments table (timestamp > now - 900)
to determine whether recent traffic spikes correspond to a legitimate deploy.
"""

import argparse
import os
import sys
import time
import uuid
import boto3
from botocore.exceptions import ClientError


def record_heartbeat(
    resource: str = "guardrail-demo-api",
    note: str = "v1.0.0 initial deploy",
    table_name: str = "Deployments",
    region_name: str | None = None,
) -> dict:
    region = (
        region_name
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "ap-south-1"
    )

    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    item = {
        "deployment_id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "resource": resource,
        "note": note,
    }

    try:
        table.put_item(Item=item)
        print(f"[SUCCESS] Recorded deployment heartbeat in '{table_name}' ({region}):")
        print(f"  deployment_id : {item['deployment_id']}")
        print(f"  timestamp     : {item['timestamp']}")
        print(f"  resource      : {item['resource']}")
        print(f"  note          : {item['note']}")
        return item
    except ClientError as e:
        print(f"[ERROR] Failed to write to DynamoDB table '{table_name}': {e}", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description="Record deploy heartbeat to DynamoDB Deployments table")
    parser.add_argument(
        "--resource",
        default=os.environ.get("DEMO_RESOURCE_NAME", "guardrail-demo-api"),
        help="Target resource name (default: guardrail-demo-api)",
    )
    parser.add_argument(
        "--note",
        default="deploy heartbeat",
        help="Free text deployment note (default: 'deploy heartbeat')",
    )
    parser.add_argument(
        "--table",
        default=os.environ.get("DEPLOYMENTS_TABLE_NAME", "Deployments"),
        help="DynamoDB table name (default: Deployments)",
    )
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (default: ap-south-1 or AWS_REGION env var)",
    )

    args = parser.parse_args()
    record_heartbeat(
        resource=args.resource,
        note=args.note,
        table_name=args.table,
        region_name=args.region,
    )


if __name__ == "__main__":
    main()
