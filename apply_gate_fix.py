"""
Usage:  python apply_gate_fix.py agentic_sre.py

Fixes the evidence gate in agentic_sre.py:
  1. "UNCONFIRMED" contains "CONFIRMED", so the LLM verdict check never rejected anything.
  2. Empty evidence, hitting the iteration limit, or an evaluation error all went on
     to propose_remediation. They now route to a new "unverified" node that logs the
     incident and proposes no command.

Each replacement is checked. If a pattern is not found, nothing is written and the
script tells you which one failed.
"""
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "agentic_sre.py"
src = open(path, encoding="utf-8-sig").read()

edits = [
    (
        '    if count >= 3:\n        return "propose_remediation"\n',
        '    if count >= 3:\n        return "unverified"\n',
    ),
    (
        '        if count >= 1:\n             return "propose_remediation"',
        '        if count >= 1:\n             return "unverified"',
    ),
    (
        '        if "CONFIRMED" in decision:\n            return "propose_remediation"\n'
        '        return "generate_hypothesis"\n    except Exception as e:\n'
        '        logger.error(f"Evaluation failed: {e}")\n        return "propose_remediation"',
        '        if decision.startswith("CONFIRMED"):\n            return "propose_remediation"\n'
        '        return "generate_hypothesis"\n    except Exception as e:\n'
        '        logger.error(f"Evaluation failed: {e}")\n        return "unverified"',
    ),
    (
        "def no_action(state: AgentState) -> AgentState:",
        'def unverified_report(state: AgentState) -> AgentState:\n'
        '    """Evidence did not support the hypothesis: record that, propose nothing."""\n'
        '    state["remediation"] = {\n'
        '        "analysis": "Hypothesis could not be verified against logs. No remediation proposed.",\n'
        '        "recommended_action": "none - manual investigation required",\n'
        '        "risk": "n/a",\n'
        '        "dry_run_command": None,\n'
        '    }\n'
        '    return state\n\n'
        "def no_action(state: AgentState) -> AgentState:",
    ),
    (
        '    graph.add_node("no_action", no_action)\n',
        '    graph.add_node("unverified", unverified_report)\n    graph.add_node("no_action", no_action)\n',
    ),
    (
        '        "propose_remediation": "propose_remediation",\n'
        '        "generate_hypothesis": "generate_hypothesis"\n    })',
        '        "propose_remediation": "propose_remediation",\n'
        '        "generate_hypothesis": "generate_hypothesis",\n'
        '        "unverified": "unverified"\n    })\n'
        '    graph.add_edge("unverified", "log_decision")',
    ),
]

for i, (old, new) in enumerate(edits, 1):
    if old not in src:
        sys.exit(f"Edit {i} not applied: pattern not found. Nothing was written. "
                 f"Paste lines around evaluate_hypothesis / build_graph and I'll adjust.")
    src = src.replace(old, new, 1)

open(path, "w", encoding="utf-8").write(src)
print(f"Applied {len(edits)} edits to {path}")
