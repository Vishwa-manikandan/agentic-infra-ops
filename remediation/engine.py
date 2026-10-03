import subprocess
import logging
import os
from typing import Dict, Optional, Tuple

logger = logging.getLogger("remediation-engine")

class RemediationEngine:
    """
    Handles the execution of remediation commands.
    Includes safety checks to prevent destructive operations.
    """
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        # List of forbidden keywords to prevent catastrophic failures
        self.forbidden_commands = ["rm -rf /", "mkfs", "shutdown", "reboot", "format"]

    def _is_safe(self, command: str) -> Tuple[bool, Optional[str]]:
        """Basic safety check for the command."""
        if not command:
            return False, "Command is empty"
        
        for forbidden in self.forbidden_commands:
            if forbidden in command:
                return False, f"Command contains forbidden keyword: {forbidden}"
        
        return True, None

    def execute(self, command: str) -> Dict:
        """Executes the command and returns the result."""
        is_safe, error = self._is_safe(command)
        if not is_safe:
            return {"success": False, "output": "", "error": error}

        if self.dry_run:
            logger.info(f"[DRY RUN] Would execute: {command}")
            return {"success": True, "output": f"Dry run: {command} would be executed", "error": None}

        try:
            logger.info(f"Executing remediation: {command}")
            # Using shell=True as the agent generates shell-like commands (e.g. docker compose ...)
            # In a production environment, we would use a more restrictive API (like Docker SDK)
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=60
            )
            
            if result.returncode == 0:
                return {"success": True, "output": result.stdout, "error": None}
            else:
                return {"success": False, "output": result.stdout, "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": "Command timed out after 60 seconds"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

# Global instance
engine = RemediationEngine()
