#!/usr/bin/env python3
"""test_reasoner.py — Unit test suite for Fuse Reasoner Lambda.

Uses moto and unittest.mock to test:
1. Mocked Bedrock Converse response parses to valid JSON and metrics_synthesis is written to Incidents DynamoDB.
2. Enrichment-only: Reasoner classifies but does not invoke Remediator or write to ApprovalQueue.
3. Fail-closed fallback: When Bedrock fails or times out, safely defaults to RUNAWAY.
"""

from decimal import Decimal
import json
import os
import sys
import unittest
from unittest.mock import MagicMock
import boto3
from moto import mock_aws

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lambdas.reasoner import handler as reasoner_handler


@mock_aws
class TestFuseReasoner(unittest.TestCase):

    def setUp(self):
        """Set up mocked AWS environment, DynamoDB tables, and mock Bedrock client."""
        self.region = "ap-south-1"

        # Configure environment variables in handler
        reasoner_handler.AWS_REGION = self.region
        reasoner_handler.BEDROCK_REGION = self.region
        reasoner_handler.DEFAULT_MODEL_ID = "apac.amazon.nova-micro-v1:0"
        reasoner_handler.INCIDENTS_TABLE_NAME = "Incidents"
        reasoner_handler.DEPLOYMENTS_TABLE_NAME = "Deployments"

        # Initialize mocked DynamoDB resource and tables
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        reasoner_handler.dynamodb_resource = self.dynamodb

        # 1. Incidents Table
        self.incidents_table = self.dynamodb.create_table(
            TableName="Incidents",
            KeySchema=[{"AttributeName": "incident_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "incident_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        reasoner_handler.incidents_table = self.incidents_table

        # 2. Deployments Table
        self.deployments_table = self.dynamodb.create_table(
            TableName="Deployments",
            KeySchema=[{"AttributeName": "deployment_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "deployment_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # ApprovalQueue no longer used by Reasoner (enrichment-only)

        # Mock Bedrock Runtime Client
        self.mock_bedrock = MagicMock()
        reasoner_handler.bedrock_client = self.mock_bedrock

        # Lambda client no longer used by Reasoner (enrichment-only)

    def _build_mock_converse_response(self, classification="RUNAWAY", confidence=0.96, diversity=0.0125, deployment=False, explanation="High spike from single caller"):
        """Constructs a deterministic mock Bedrock Converse toolConfig response."""
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tooluse_bedrock_001",
                                "name": "classify_anomaly",
                                "input": {
                                    "classification": classification,
                                    "confidence": confidence,
                                    "is_fallback": False,
                                    "metrics_synthesis": {
                                        "caller_diversity_score": diversity,
                                        "deployment_correlation": deployment,
                                    },
                                    "explanation": explanation,
                                },
                            }
                        }
                    ],
                }
            },
            "stopReason": "tool_use",
        }

    def test_bedrock_converse_response_parses_json_and_writes_metrics_synthesis(self):
        """Test that mocked Bedrock Converse response parses to valid JSON and metrics_synthesis is written to Incidents."""
        self.mock_bedrock.converse.return_value = self._build_mock_converse_response(
            classification="RUNAWAY",
            confidence=0.95,
            diversity=0.015,
            deployment=False,
            explanation="Single caller generating repeated requests without active deployment.",
        )

        payload = {
            "resource": "guardrail-demo-api",
            "stage": "prod",
            "current_count_per_min": 650,
            "baseline_count_per_min": 12.0,
            "delta": 638.0,
            "unique_caller_count": 1,
            "total_requests_in_window": 1950,
            "recent_deploy": False,
            "deploy_note": None,
            "sample_payloads": ['{"action":"retry_fetch","id":"x92"}'],
        }

        response = reasoner_handler.lambda_handler(payload, {})

        self.assertEqual(response["statusCode"], 200)
        body = response["body"]
        self.assertEqual(body["classification"], "RUNAWAY")
        self.assertEqual(body["confidence"], 0.95)
        self.assertFalse(body["is_fallback"])
        self.assertIn("Single caller", body["explanation"])

        # Verify metrics_synthesis in returned payload
        synthesis = body["metrics_synthesis"]
        self.assertEqual(synthesis["caller_diversity_score"], 0.015)
        self.assertFalse(synthesis["deployment_correlation"])

        self.assertEqual(body["action_taken"], "ENRICHMENT_ONLY")

        # Crucial verification: Check DynamoDB Incidents Table item
        incident_id = body["incident_id"]
        inc_item = self.incidents_table.get_item(Key={"incident_id": incident_id}).get("Item")
        self.assertIsNotNone(inc_item, "Incident record was not written to DynamoDB Incidents table!")
        self.assertEqual(inc_item["classification"], "RUNAWAY")
        self.assertEqual(inc_item["action_taken"], "ENRICHMENT_ONLY")
        self.assertIn("metrics_synthesis", inc_item)
        self.assertEqual(inc_item["metrics_synthesis"]["caller_diversity_score"], Decimal("0.015"))
        self.assertFalse(inc_item["metrics_synthesis"]["deployment_correlation"])

    def test_enrichment_updates_existing_incident(self):
        """Test that Reasoner enriches an existing incident when incident_id is provided."""
        self.mock_bedrock.converse.return_value = self._build_mock_converse_response(
            classification="RUNAWAY",
            confidence=0.98,
            explanation="Single caller generating recursive loop.",
        )

        # Pre-create an incident (as the Poller would)
        existing_id = "inc-existing-enrichment"
        self.incidents_table.put_item(
            Item={
                "incident_id": existing_id,
                "action_taken": "IP_BLOCKED",
                "resource": "guardrail-demo-api",
                "environment": "prod",
                "timestamp": 1700000000,
            }
        )

        payload = {
            "incident_id": existing_id,
            "resource": "guardrail-demo-api",
            "stage": "prod",
            "current_count_per_min": 800,
            "baseline_count_per_min": 5.0,
            "delta": 795.0,
            "unique_caller_count": 1,
            "total_requests_in_window": 2400,
            "recent_deploy": False,
        }

        response = reasoner_handler.lambda_handler(payload, {})

        self.assertEqual(response["statusCode"], 200)
        body = response["body"]
        self.assertEqual(body["classification"], "RUNAWAY")
        self.assertEqual(body["action_taken"], "ENRICHMENT_APPLIED")
        self.assertEqual(body["incident_id"], existing_id)

        # Verify the existing incident was enriched
        inc_item = self.incidents_table.get_item(Key={"incident_id": existing_id}).get("Item")
        self.assertIn("bedrock_explanation", inc_item)
        self.assertIn("enriched_at", inc_item)

    def test_bedrock_failure_triggers_fail_closed_fallback(self):
        """Test that Bedrock error/timeout triggers stochastic fail-closed fallback to RUNAWAY."""
        self.mock_bedrock.converse.side_effect = Exception("ThrottlingException: Rate exceeded")

        payload = {
            "resource": "guardrail-demo-api",
            "stage": "prod",
            "current_count_per_min": 500,
            "baseline_count_per_min": 10.0,
            "delta": 490.0,
            "unique_caller_count": 1,
            "total_requests_in_window": 1500,
        }

        response = reasoner_handler.lambda_handler(payload, {})

        self.assertEqual(response["statusCode"], 200)
        body = response["body"]
        self.assertTrue(body["is_fallback"])
        self.assertEqual(body["classification"], "RUNAWAY")
        self.assertEqual(body["confidence"], 0.0)
        self.assertIn("FAIL-CLOSED FALLBACK", body["explanation"])

        # Verify written to Incidents table with is_fallback=True
        incident_id = body["incident_id"]
        inc_item = self.incidents_table.get_item(Key={"incident_id": incident_id}).get("Item")
        self.assertIsNotNone(inc_item)
        self.assertTrue(inc_item["is_fallback"])
        self.assertEqual(inc_item["classification"], "RUNAWAY")


if __name__ == "__main__":
    unittest.main()
