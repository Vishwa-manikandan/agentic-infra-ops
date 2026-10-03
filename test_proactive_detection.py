import json
import unittest
from unittest.mock import MagicMock, patch
from agent import AgentState, detect_incidents, build_graph

class TestProactiveDetection(unittest.TestCase):
    def setUp(self):
        # We build the graph to test the full flow
        self.app = build_graph()

    @patch('agent.requests.get')
    @patch('agent.get_log_tool')
    def test_log_anomaly_trigger(self, mock_get_log_tool, mock_get):
        """
        Test that the agent triggers a remediation flow when Prometheus is silent
        but a log anomaly is detected.
        """
        # 1. Mock Prometheus: No alerts firing
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {"alerts": []}}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        # 2. Mock LogQueryTool instance returned by get_log_tool()
        mock_tool_instance = MagicMock()
        mock_tool_instance.detect_anomalies.return_value = {
            "pattern": "Connection timeout to database",
            "count": 15,
            "example": '{"level": "ERROR", "message": "Connection timeout to database"}'
        }
        mock_get_log_tool.return_value = mock_tool_instance

        # 3. Invoke the graph in mock mode (to avoid actual Ollama calls)
        result = self.app.invoke({"mock": True})

        # 4. Assertions
        self.assertEqual(result["trigger_type"], "LOG_ANOMALY")
        self.assertEqual(result["alerts"][0]["labels"]["alertname"], "LogAnomalyDetected")
        self.assertIn("Connection timeout to database", result["alerts"][0]["annotations"]["summary"])

        # Verify the final remediation was generated
        self.assertIn("remediation", result)
        print("\n[TEST SUCCESS] Proactive Detection Triggered!")
        print(f"Trigger: {result['trigger_type']}")
        print(f"Analysis: {result['remediation']['analysis']}")
        print(f"Action: {result['remediation']['recommended_action']}")

if __name__ == "__main__":
    unittest.main()
