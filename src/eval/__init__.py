# src/eval/
"""AI evaluation harness (PRD 5.37 / 21 / 22).

Scores the agent systematically: intent, capability selection, tool-argument
correctness, booking verification, and safety — via deterministic rule checks
(`checks.py`) plus an optional LLM-as-judge (`judge.py`). `runner.py` runs a
scenario catalog live through the real ConversationAgent or scores recorded
fixtures offline, and emits the §22 scorecard (console + eval_report.json).
"""
