import unittest
from unittest.mock import patch, MagicMock
from remediation.engine import RemediationEngine

class TestRemediationEngine(unittest.TestCase):
    def setUp(self):
        # Create engine with dry_run=False to test actual execution logic
        self.engine = RemediationEngine(dry_run=False)

    def test_forbidden_command(self):
        """Ensure forbidden commands are blocked."""
        result = self.engine.execute("rm -rf /")
        self.assertFalse(result["success"])
        self.assertIn("forbidden keyword", result["error"])

    def test_empty_command(self):
        """Ensure empty commands are blocked."""
        result = self.engine.execute("")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Command is empty")

    @patch('subprocess.run')
    def test_successful_execution(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Success output", stderr="")
        
        result = self.engine.execute("echo 'hello'")
        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "Success output")

    @patch('subprocess.run')
    def test_failed_execution(self, mock_run):
        """Test failed command execution."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Command failed")
        
        result = self.engine.execute("false")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Command failed")

    def test_dry_run(self):
        """Test dry run mode."""
        dry_engine = RemediationEngine(dry_run=True)
        result = dry_engine.execute("echo 'hello'")
        self.assertTrue(result["success"])
        self.assertIn("Dry run", result["output"])

if __name__ == "__main__":
    unittest.main()
