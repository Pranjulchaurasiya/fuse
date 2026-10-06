#!/usr/bin/env python3
"""test_remediator.py — Unit test suite for Fuse Remediator Lambda (WAF-based).

Tests:
1. BLOCK action: Adds IPs to WAF IP Set and records action in Incidents table.
2. Idempotency: Blocking already-blocked IPs returns ALREADY_BLOCKED without WAF update.
3. UNBLOCK action: Removes IPs from WAF IP Set.
4. Missing action field returns error.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import boto3
from moto import mock_aws

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lambdas.remediator import handler as remediator_handler


@mock_aws
class TestFuseRemediator(unittest.TestCase):

    def setUp(self):
        self.region = "ap-south-1"
        self.ip_set_id = "test-ip-set-id-123"
        self.ip_set_name = "fuse-blocked-ips"

        # Configure handler env vars
        remediator_handler.AWS_REGION = self.region
        remediator_handler.WAF_IP_SET_ID = self.ip_set_id
        remediator_handler.WAF_IP_SET_NAME = self.ip_set_name
        remediator_handler.INCIDENTS_TABLE = "Incidents"
        remediator_handler.TARGET_API_NAME = "guardrail-demo-api"

        # Initialize mocked DynamoDB
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        remediator_handler.dynamodb = self.dynamodb

        self.incidents_table = self.dynamodb.create_table(
            TableName="Incidents",
            KeySchema=[{"AttributeName": "incident_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "incident_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Pre-populate an incident for updates
        self.incidents_table.put_item(
            Item={"incident_id": "inc-block-001", "action_taken": "PENDING"}
        )
        self.incidents_table.put_item(
            Item={"incident_id": "inc-unblock-001", "action_taken": "IP_BLOCKED"}
        )

        # Mock WAFv2 client
        self.mock_waf = MagicMock()
        remediator_handler.wafv2_client = self.mock_waf

    def test_block_action_adds_ips_to_waf(self):
        """Test that BLOCK action adds IPs to WAF IP Set and updates Incidents."""
        # Mock IP Set currently empty
        self.mock_waf.get_ip_set.return_value = {
            "LockToken": "lock-token-1",
            "IPSet": {
                "Addresses": [],
                "Description": "Fuse IP Set",
            },
        }
        self.mock_waf.update_ip_set.return_value = {}

        payload = {
            "action": "BLOCK",
            "incident_id": "inc-block-001",
            "source_ips": ["10.0.0.1", "10.0.0.2"],
            "resource": "guardrail-demo-api",
            "stage": "prod",
            "trigger_source": "auto_detection",
        }

        response = remediator_handler.lambda_handler(payload, {})

        self.assertEqual(response["statusCode"], 200)
        body = response["body"]
        self.assertEqual(body["status"], "IP_BLOCKED")
        self.assertEqual(body["action"], "BLOCK")

        # Verify WAF update_ip_set was called
        self.mock_waf.update_ip_set.assert_called_once()
        call_kwargs = self.mock_waf.update_ip_set.call_args[1]
        addresses = call_kwargs["Addresses"]
        self.assertIn("10.0.0.1/32", addresses)
        self.assertIn("10.0.0.2/32", addresses)

        # Verify Incidents table was updated
        db_item = self.incidents_table.get_item(Key={"incident_id": "inc-block-001"}).get("Item")
        self.assertEqual(db_item["action_taken"], "IP_BLOCKED")

    def test_idempotency_already_blocked(self):
        """Test that blocking already-blocked IPs returns ALREADY_BLOCKED without WAF update."""
        self.mock_waf.get_ip_set.return_value = {
            "LockToken": "lock-token-2",
            "IPSet": {
                "Addresses": ["10.0.0.1/32", "10.0.0.2/32"],
                "Description": "Fuse IP Set",
            },
        }

        payload = {
            "action": "BLOCK",
            "incident_id": "inc-block-001",
            "source_ips": ["10.0.0.1", "10.0.0.2"],
            "resource": "guardrail-demo-api",
            "stage": "prod",
        }

        response = remediator_handler.lambda_handler(payload, {})

        self.assertEqual(response["statusCode"], 200)
        body = response["body"]
        self.assertEqual(body["status"], "ALREADY_BLOCKED")

        # WAF update should NOT be called
        self.mock_waf.update_ip_set.assert_not_called()

    def test_unblock_action_removes_ips_from_waf(self):
        """Test that UNBLOCK removes IPs from WAF IP Set."""
        self.mock_waf.get_ip_set.return_value = {
            "LockToken": "lock-token-3",
            "IPSet": {
                "Addresses": ["10.0.0.1/32", "10.0.0.2/32", "10.0.0.3/32"],
                "Description": "Fuse IP Set",
            },
        }
        self.mock_waf.update_ip_set.return_value = {}

        payload = {
            "action": "UNBLOCK",
            "incident_id": "inc-unblock-001",
            "source_ips": ["10.0.0.1", "10.0.0.2"],
            "resource": "guardrail-demo-api",
            "stage": "prod",
            "trigger_source": "auto_recovery",
        }

        response = remediator_handler.lambda_handler(payload, {})

        self.assertEqual(response["statusCode"], 200)
        body = response["body"]
        self.assertEqual(body["status"], "IP_UNBLOCKED")

        # Verify only 10.0.0.3/32 remains
        call_kwargs = self.mock_waf.update_ip_set.call_args[1]
        self.assertEqual(call_kwargs["Addresses"], ["10.0.0.3/32"])

    def test_missing_action_returns_error(self):
        """Test that missing 'action' field returns 500 error."""
        payload = {
            "incident_id": "inc-no-action",
            "source_ips": ["10.0.0.1"],
        }

        response = remediator_handler.lambda_handler(payload, {})
        self.assertEqual(response["statusCode"], 500)


if __name__ == "__main__":
    unittest.main()
