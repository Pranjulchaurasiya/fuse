#!/usr/bin/env python3
"""test_enterprise_security.py — Unit test suite for Enterprise Multi-Tenant Isolation & Audit Trail.

Tests:
1. Tenant Query Isolation: get_incidents queries TenantIndex when tenant_id is in JWT claims or query parameters.
2. Cross-Tenant Protection: approve_action returns 403 Forbidden if caller tenant does not match incident tenant.
3. SOC-2 Structured Audit Trail: approve_action appends cryptographic caller identity to incident audit_trail list.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import boto3
from moto import mock_aws

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lambdas.get_incidents import handler as get_incidents_handler
from lambdas.approve_action import handler as approve_action_handler


@mock_aws
class TestEnterpriseSecurity(unittest.TestCase):

    def setUp(self):
        self.region = "ap-south-1"
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)

        # Configure get_incidents handler
        get_incidents_handler.dynamodb_resource = self.dynamodb
        get_incidents_handler.INCIDENTS_TABLE = "Incidents"

        # Configure approve_action handler
        approve_action_handler.dynamodb_resource = self.dynamodb
        approve_action_handler.INCIDENTS_TABLE = "Incidents"
        approve_action_handler.APPROVAL_QUEUE_TABLE = "ApprovalQueue"
        approve_action_handler.REMEDIATOR_FUNCTION_NAME = "guardrail-remediator"

        # Mock Remediator invoke in approve_action
        self.mock_lambda = MagicMock()
        self.mock_lambda.invoke.return_value = {
            "Payload": MagicMock(read=lambda: json.dumps({"status": "IP_BLOCKED"}).encode("utf-8"))
        }
        approve_action_handler.lambda_client = self.mock_lambda

        # Create Incidents table with GSI TenantIndex
        self.incidents_table = self.dynamodb.create_table(
            TableName="Incidents",
            KeySchema=[{"AttributeName": "incident_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "incident_id", "AttributeType": "S"},
                {"AttributeName": "tenant_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "N"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "TenantIndex",
                    "KeySchema": [
                        {"AttributeName": "tenant_id", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create ApprovalQueue table
        self.approval_table = self.dynamodb.create_table(
            TableName="ApprovalQueue",
            KeySchema=[{"AttributeName": "approval_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "approval_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Wire handlers to mocked tables
        get_incidents_handler.table = self.incidents_table
        approve_action_handler.incidents_table = self.incidents_table
        approve_action_handler.approval_table = self.approval_table

        # Pre-seed items for two different tenants
        self.incidents_table.put_item(
            Item={
                "incident_id": "inc-tenant-alpha-001",
                "tenant_id": "tenant-alpha",
                "timestamp": 1700000100,
                "resource": "api-alpha",
                "classification": "RUNAWAY",
                "action_taken": "PENDING_APPROVAL",
                "source_ips": ["198.51.100.1"],
                "audit_trail": [],
            }
        )
        self.incidents_table.put_item(
            Item={
                "incident_id": "inc-tenant-beta-002",
                "tenant_id": "tenant-beta",
                "timestamp": 1700000200,
                "resource": "api-beta",
                "classification": "RUNAWAY",
                "action_taken": "PENDING_APPROVAL",
                "source_ips": ["203.0.113.5"],
                "audit_trail": [],
            }
        )

    def test_get_incidents_tenant_query_isolation(self):
        """Test that get_incidents with custom:tenant_id returns only that tenant's incidents."""
        event = {
            "httpMethod": "GET",
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "email": "user@tenant-alpha.com",
                        "custom:tenant_id": "tenant-alpha",
                    }
                }
            },
        }

        resp = get_incidents_handler.lambda_handler(event, None)
        self.assertEqual(resp["statusCode"], 200)

        body = json.loads(resp["body"])
        incidents = body.get("incidents", [])
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["incident_id"], "inc-tenant-alpha-001")
        self.assertEqual(incidents[0]["tenant_id"], "tenant-alpha")

    def test_approve_action_cross_tenant_forbidden(self):
        """Test that an operator from tenant-alpha CANNOT approve tenant-beta's incident."""
        event = {
            "httpMethod": "POST",
            "pathParameters": {"incident_id": "inc-tenant-beta-002"},
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "email": "attacker@tenant-alpha.com",
                        "sub": "user-uuid-111",
                        "custom:tenant_id": "tenant-alpha",
                    }
                },
                "identity": {"sourceIp": "198.51.100.99"},
            },
            "body": json.dumps({"decision": "APPROVED", "resolved_by": "Tenant Alpha Operator"}),
        }

        resp = approve_action_handler.lambda_handler(event, None)
        self.assertEqual(resp["statusCode"], 403)
        body = json.loads(resp["body"])
        self.assertIn("another tenant", body.get("message", "").lower())

    def test_approve_action_audit_trail_recorded(self):
        """Test that authorized approval appends cryptographic actor identity into audit_trail."""
        event = {
            "httpMethod": "POST",
            "pathParameters": {"incident_id": "inc-tenant-alpha-001"},
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "email": "ciso@tenant-alpha.com",
                        "sub": "cognito-sub-uuid-999",
                        "custom:tenant_id": "tenant-alpha",
                    }
                },
                "identity": {"sourceIp": "103.21.244.2"},
            },
            "body": json.dumps({"decision": "APPROVED", "resolved_by": "Alpha Security Lead"}),
        }

        resp = approve_action_handler.lambda_handler(event, None)
        self.assertEqual(resp["statusCode"], 200)

        # Verify DynamoDB record updated with structured audit trail
        db_item = self.incidents_table.get_item(Key={"incident_id": "inc-tenant-alpha-001"}).get("Item")
        self.assertEqual(db_item["action_taken"], "APPROVED_AND_BLOCKED")

        audit_trail = db_item.get("audit_trail", [])
        self.assertEqual(len(audit_trail), 1)
        entry = audit_trail[0]
        self.assertEqual(entry["action"], "APPROVAL_APPROVED")
        self.assertEqual(entry["actor_identity"], "ciso@tenant-alpha.com")
        self.assertEqual(entry["actor_sub"], "cognito-sub-uuid-999")
        self.assertEqual(entry["client_ip"], "103.21.244.2")
        self.assertEqual(entry["decision"], "APPROVED")


if __name__ == "__main__":
    unittest.main()
