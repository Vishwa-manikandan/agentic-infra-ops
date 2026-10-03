import json
import unittest
from unittest.mock import MagicMock, patch
from agentic_sre import AgentState, build_graph

class TestReasoningLoop(unittest.TestCase):
    def setUp(self):
        self.app = build_graph()

    @patch('agentic_sre.requests.get')
    @patch('agentic_sre.log_tool')
    def test_reasoning_loop_flow(self, mock_log_tool, mock_get):
        """
        Verify the iterative reasoning loop.
        We test the la a la l l a la path to ensure the logic flow works.
        """
        # 1. Mock Prometheus: No alerts firing (forces Proactive Detection)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"alerts": []}}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        # 2. Mock LogQueryTool: Detect a "DB Timeout" anomaly
        mock_log_tool.detect_anomalies.return_value = {
            "pattern": "Connection timeout to database",
            "count": 15,
            "example": '{"level": "ERROR", "message": "Connection timeout to database"}'
        }

        # Mock evidence gathering
        mock_log_tool.query_structured_logs.return_value = [{"values": [["123", '{"message": "Connection timeout to database"}']]}]
        mock_log_tool.query_semantic_logs.return_value = ["Database connection pool exhausted"]

        # 3. CRITICAL: We must bypass the internal "mock" mode in detect_incidents
        # because that hardcodes trigger_type = "PROMETHEUS".
        # We invoke with mock=False but patch the internal Ollama calls within the nodes.

        with patch('ollama.chat') as mock_ollama:
            # Mock Hypothesis Generation
            mock_ollama.side_effect = [
                # 1st call: generate_hypothesis
                MagicMock(message={"content": json.dumps({
                    "hypothesis": "Database connection pool exhaustion",
                    "reasoning": "High latency and timeout logs",
                    "verification_steps": ["Connection timeout"]
                })}),
                # 2nd call: evaluate_hypothesis
                MagicMock(message={"content": "CONFIRMED"}),
                # 3rd call: propose_remediation
                MagicMock(message={"content": json.dumps({
                    "analysis": "Verified DB pool issue",
                    "recommended_action": "scale db",
                    "risk": "low",
                    "dry_run_command": "docker compose scale db=2"
                })})
            ]

            result = self.app.invoke({"mock": False}, config={"recursion_limit": 50})

        print("\n--- Back-test Results ---")
        print(f"Trigger: {result.get('trigger_type')}")
        print(f"Hypothesis: {result.get('hypothesis', {}).get('hypothesis')}")
        print(f"Evidence: {result.get('evidence')}")
        print(f"Final Action: {result.get('remediation', {}).get('recommended_action')}")

        self.assertEqual(result["trigger_type"], "LOG_ANOMALY")
        self.assertIn("hypothesis", result)
        self.assertIn("evidence", result)
        self.assertIn("remediation", result)

        print("\n[TEST SUCCESS] Iterative Reasoning Loop Verified!")

if __name__ == "__main__":
    unittest.main()
