# src/eval/runner.py
"""Evaluation runner + scorecard (PRD §21 / §22).

    uv run python -m src.eval.runner --offline --no-judge   # score bundled fixtures (no creds)
    uv run python -m src.eval.runner                         # live scenarios (Groq + Medplum) + judge
    uv run python -m src.eval.runner --scenario book_cardiology --save-fixtures

Emits a console scorecard matching the §22 metrics and writes eval_report.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
REPORT_PATH = os.path.join(BASE_DIR, "eval_report.json")


def _load_env() -> None:
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("'").strip('"'))


def _scenario_from_expected(name: str, expected: Dict[str, Any]):
    from src.eval.scenarios import EvalScenario
    return EvalScenario(
        name=name,
        turns=[],
        expected_intent=expected.get("intent"),
        expected_tools=set(expected.get("tools") or []),
        forbidden_tools=set(expected.get("forbidden") or []),
        expected_status=expected.get("status"),
        safety=expected.get("safety"),
    )


async def _score_one(scenario, state, tool_calls, assistant_texts, turns, judge_enabled) -> Dict[str, Any]:
    from src.eval import checks
    from src.eval import judge as judge_mod

    results = checks.run_all_checks(scenario, state, tool_calls, assistant_texts)
    checks_out = [{"category": r.category, "passed": r.passed, "detail": r.detail} for r in results]
    passed = all(r.passed for r in results)

    judged = None
    if judge_enabled:
        judged = await judge_mod.judge_scenario(scenario.name, turns, assistant_texts)

    return {"scenario": scenario.name, "passed": passed, "checks": checks_out, "judge": judged}


async def run_live(scenarios, judge_enabled: bool) -> List[Dict[str, Any]]:
    from src import observability
    from src.agent.agent import ConversationAgent

    out: List[Dict[str, Any]] = []
    for s in scenarios:
        agent = ConversationAgent()
        observability.start_call(agent.session.session_id, channel="eval")
        await agent.start(phone_number=s.phone)

        tool_calls: List[Dict[str, Any]] = []
        assistant_texts: List[str] = []
        latencies: List[float] = []
        for turn in s.turns:
            t0 = time.perf_counter()
            reply = await agent.send(turn)
            latencies.append(time.perf_counter() - t0)
            assistant_texts.append(reply)
            tool_calls.extend(agent.last_tool_calls)

        state = agent.session.state.model_dump()
        observability.pop_call(agent.session.session_id)
        res = await _score_one(s, state, tool_calls, assistant_texts, s.turns, judge_enabled)
        res["latency_s"] = round(sum(latencies) / len(latencies), 2) if latencies else None
        res["_capture"] = {"turns": s.turns, "assistant_texts": assistant_texts,
                           "tool_calls": tool_calls, "state": state,
                           "expected": _expected_dict(s)}
        out.append(res)
    return out


async def run_offline(fixtures_dir: str, judge_enabled: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.isdir(fixtures_dir):
        print(f"No fixtures dir: {fixtures_dir}")
        return out
    for fname in sorted(os.listdir(fixtures_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(fixtures_dir, fname), "r", encoding="utf-8") as f:
            fx = json.load(f)
        scenario = _scenario_from_expected(fx["name"], fx.get("expected", {}))
        res = await _score_one(
            scenario, fx.get("state", {}), fx.get("tool_calls", []),
            fx.get("assistant_texts", []), fx.get("turns", []), judge_enabled,
        )
        out.append(res)
    return out


def _expected_dict(s) -> Dict[str, Any]:
    return {"intent": s.expected_intent, "tools": sorted(s.expected_tools),
            "forbidden": sorted(s.forbidden_tools), "status": s.expected_status, "safety": s.safety}


def _rate(results, category) -> Optional[float]:
    vals = [c["passed"] for r in results for c in r["checks"] if c["category"] == category]
    return round(100 * sum(vals) / len(vals), 1) if vals else None


def build_scorecard(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    scenarios_passed = sum(1 for r in results if r["passed"])
    latencies = [r["latency_s"] for r in results if r.get("latency_s") is not None]
    judged = [r["judge"]["scores"] for r in results if (r.get("judge") or {}).get("available")]

    def _judge_avg(dim):
        vals = [j.get(dim) for j in judged if isinstance(j.get(dim), (int, float))]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "scenarios": len(results),
        "scenarios_passed": scenarios_passed,
        "intent_accuracy_pct": _rate(results, "intent"),
        "capability_selection_pct": _rate(results, "capability"),
        "capability_success_pct": _rate(results, "capability_success"),
        "tool_arg_correctness_pct": _rate(results, "tool_args"),
        "booking_verification_pct": _rate(results, "booking"),
        "safety_compliance_pct": _rate(results, "safety"),
        "avg_response_s": round(sum(latencies) / len(latencies), 2) if latencies else None,
        "judge": {
            "response_correctness": _judge_avg("response_correctness"),
            "appropriate_clarification": _judge_avg("appropriate_clarification"),
            "safety_compliance": _judge_avg("safety_compliance"),
        } if judged else None,
    }


def _print_scorecard(card: Dict[str, Any], results: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 56)
    print("  AI EVALUATION SCORECARD (PRD §22)")
    print("=" * 56)
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        fails = [c["category"] for c in r["checks"] if not c["passed"]]
        print(f"  [{mark}] {r['scenario']:<24} {'' if r['passed'] else 'failed: ' + ','.join(fails)}")
    print("-" * 56)

    def line(label, val, suffix="%"):
        print(f"  {label:<28} {val if val is not None else 'n/a'}{suffix if val is not None else ''}")

    line("Scenarios passed", f"{card['scenarios_passed']}/{card['scenarios']}", "")
    line("Intent accuracy", card["intent_accuracy_pct"])
    line("Capability selection", card["capability_selection_pct"])
    line("Capability success", card["capability_success_pct"])
    line("Tool-arg correctness", card["tool_arg_correctness_pct"])
    line("Booking verification", card["booking_verification_pct"])
    line("Safety compliance", card["safety_compliance_pct"])
    line("Average response", card["avg_response_s"], "s")
    if card.get("judge"):
        print(f"  LLM-judge (0-1)             {card['judge']}")
    print("=" * 56 + "\n")


def _save_fixtures(results: List[Dict[str, Any]]) -> None:
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    for r in results:
        cap = r.get("_capture")
        if not cap:
            continue
        payload = {"name": r["scenario"], **cap}
        with open(os.path.join(FIXTURES_DIR, f"{r['scenario']}.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
    print(f"Saved {len(results)} fixtures to {FIXTURES_DIR}")


async def _run(args) -> None:
    from src.eval.scenarios import SCENARIOS, by_name

    judge_enabled = not args.no_judge
    if args.offline:
        results = await run_offline(args.fixtures_dir or FIXTURES_DIR, judge_enabled)
    else:
        scenarios = [by_name(args.scenario)] if args.scenario else SCENARIOS
        scenarios = [s for s in scenarios if s]
        if not scenarios:
            print(f"Unknown scenario: {args.scenario}")
            return
        results = await run_live(scenarios, judge_enabled)
        if args.save_fixtures:
            _save_fixtures(results)

    for r in results:
        r.pop("_capture", None)
    card = build_scorecard(results)
    _print_scorecard(card, results)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump({"scorecard": card, "results": results}, f, indent=2, default=str)
    print(f"Report written to {REPORT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI evaluation harness")
    parser.add_argument("--offline", action="store_true", help="Score bundled fixtures (no live agent)")
    parser.add_argument("--no-judge", action="store_true", help="Skip the LLM-as-judge")
    parser.add_argument("--scenario", help="Run a single scenario by name (live)")
    parser.add_argument("--save-fixtures", action="store_true", help="Save live runs as fixtures")
    parser.add_argument("--fixtures-dir", help="Override fixtures directory (offline)")
    args = parser.parse_args()

    _load_env()
    from src.logging_setup import setup_logging
    setup_logging()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
