#!/usr/bin/env python3
"""test_prefilter_gate.py - Automated validation suite for the statistical pre-filter gate.

Tests all three operational execution paths inside guardrail-poller:
1. Low-Volume Guard: Volume below floor (12 req) -> SKIPPED (Zero Bedrock cost).
2. Normal Baseline Variance: High volume with realistic variance (Z < 2.5) -> DETERMINISTIC_PASS (Zero Bedrock cost).
3. Runaway Anomaly: Severe traffic spike (Z >= 2.5) -> ANOMALY_EVALUATED (Invokes Bedrock).
"""

import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock

# Append the lambda directory paths to the system environment path matrix
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../lambdas/poller")))

import handler


class TestFusePreFilterGate(unittest.TestCase):

    def setUp(self):
        """Reset mock parameters and initialize base config metrics variables."""
        handler.cw_client = MagicMock()
        handler.lambda_client = MagicMock()
        handler.logs_client = MagicMock()
        handler.deployments_table = MagicMock()

        # Mock deploy heartbeat to return no recent deploy
        handler.deployments_table.scan.return_value = {"Items": []}

        # Mock CloudWatch logs filter for unique callers
        handler.logs_client.filter_log_events.return_value = {
            "events": [
                {"message": 'DEMO_API_REQUEST {"caller":"192.168.1.10","body":{"action":"test"}}'}
            ]
        }

        # Configure test environment variable expectations
        handler.MINIMUM_VOLUME_FLOOR = 50
        handler.Z_SCORE_THRESHOLD = 2.5
        handler.REASONER_FUNCTION_NAME = "mock-guardrail-reasoner"
        handler.REMEDIATOR_FUNCTION_NAME = "mock-guardrail-remediator"
        handler.RECOVERY_WINDOW_MINUTES = 15
        handler.BEDROCK_ENRICHMENT_ENABLED = False  # disable for unit tests
        handler.INCIDENTS_TABLE = "Incidents"
        handler.CALLER_DOMINANCE_THRESHOLD = 0.85

        # Mock ddb_client for auto-recovery (Incidents table scan)
        mock_ddb = MagicMock()
        mock_incidents_tbl = MagicMock()
        mock_incidents_tbl.scan.return_value = {"Items": []}
        mock_ddb.Table.return_value = mock_incidents_tbl
        handler.ddb_client = mock_ddb

    def mock_cloudwatch_response(self, values):
        """Helper to generate standard structural CloudWatch metric data matrices."""
        return {
            "MetricDataResults": [
                {
                    "Id": "m1",
                    "Timestamps": [f"2026-09-28T04:{i:02d}:00Z" for i in range(len(values))],
                    "Values": [float(v) for v in values],
                }
            ]
        }

    def test_low_volume_safety_floor_bypass(self):
        """Path 1: Volume below floor (12 req) -> Must return SKIPPED with zero Bedrock invocation."""
        mock_metrics = [12, 2, 4, 3, 1, 5, 2]
        handler.cw_client.get_metric_data.return_value = self.mock_cloudwatch_response(mock_metrics)

        mock_event = {"api_id": "test-api-123", "stage": "prod"}
        response = handler.lambda_handler(mock_event, None)
        body = response.get("body", {})

        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(body.get("status"), "SKIPPED")
        self.assertFalse(body.get("bedrock_invoked"))
        self.assertIn("Volume below safety floor", body.get("reason", ""))
        handler.lambda_client.invoke.assert_not_called()
        print("[PASS] Path 1: Low-volume safety floor successfully bypassed Bedrock.")

    def test_normal_baseline_variance_bypass(self):
        """Path 2: Traffic is high with normal organic spread (Z < 2.5) -> Must return DETERMINISTIC_PASS."""
        # Mean of history is ~116, std_dev is ~5.5. Current of 120 gives Z ~ 0.72 < 2.5
        mock_metrics = [120, 110, 125, 115, 120, 118, 112, 122]
        handler.cw_client.get_metric_data.return_value = self.mock_cloudwatch_response(mock_metrics)

        mock_event = {"api_id": "test-api-123", "stage": "prod"}
        response = handler.lambda_handler(mock_event, None)
        body = response.get("body", {})

        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(body.get("status"), "DETERMINISTIC_PASS")
        self.assertFalse(body.get("bedrock_invoked"))
        self.assertIn("Within normal statistical variance", body.get("reason", ""))
        handler.lambda_client.invoke.assert_not_called()
        print("[PASS] Path 2: Normal variance traffic successfully bypassed Bedrock layer.")

    def test_runaway_anomaly_handoff_trigger(self):
        """Path 3: Severe traffic spike (Z >= 2.5) with single caller -> RUNAWAY classification with IP block."""
        # Baseline ~60, current jumps to 850 (Z >> 2.5)
        mock_metrics = [850, 62, 58, 65, 60, 57, 61, 59, 63]
        handler.cw_client.get_metric_data.return_value = self.mock_cloudwatch_response(mock_metrics)

        # Mock remediator response
        import io
        rem_payload = json.dumps({
            "statusCode": 200,
            "body": {"status": "IP_BLOCKED", "action": "BLOCK"},
        }).encode("utf-8")
        handler.lambda_client.invoke.return_value = {"Payload": io.BytesIO(rem_payload)}

        mock_event = {"api_id": "test-api-123", "stage": "prod"}
        response = handler.lambda_handler(mock_event, None)
        body = response.get("body", {})

        self.assertEqual(response.get("statusCode"), 200)
        self.assertEqual(body.get("status"), "ANOMALY_EVALUATED")
        self.assertEqual(body.get("classification"), "RUNAWAY")
        decision_str = body.get("decision_reason", "").lower()
        self.assertTrue("dominant" in decision_str or "dominance" in decision_str)
        # Remediator should have been invoked to block
        handler.lambda_client.invoke.assert_called()
        print("[PASS] Path 3: Critical anomaly correctly classified as RUNAWAY with IP block.")

    def test_compute_baseline_and_delta_math(self):
        """Mathematical Verification: Check mean, standard deviation, and Z-score calculations."""
        values = [200, 100, 100, 100, 100]
        current_count, baseline, std_dev, z_score, delta, total = handler.compute_baseline_and_delta(values)

        self.assertEqual(current_count, 200)
        self.assertEqual(baseline, 100.0)
        self.assertEqual(std_dev, 0.0)
        self.assertEqual(delta, 100.0)
        # When std_dev is 0 and current > baseline, z_score defaults to 999.0 to indicate infinite deviation
        self.assertEqual(z_score, 999.0)
        print("[PASS] Mathematical Verification: compute_baseline_and_delta logic validated.")


if __name__ == "__main__":
    unittest.main()
