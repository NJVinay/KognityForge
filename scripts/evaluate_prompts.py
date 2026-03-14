"""Evaluation harness – runs the workflow across multiple standards × 5E phases
and produces a computable quality report with aggregate statistics.

Usage:
    python scripts/evaluate_prompts.py [--runs N] [--output results.json]
"""

import asyncio
import json
import sys
import pathlib
import time
import argparse

# Add backend to path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from workflows.orchestrator import run_workflow  # noqa: E402


# ── Test matrix: all standard × phase combinations to evaluate ────────────

EVAL_MATRIX = [
    ("IB_BIO_2.9", "Explain"),
    ("IB_BIO_2.9", "Engage"),
    ("IB_BIO_6.1", "Explain"),
    ("IB_BIO_2.1", "Explore"),
    ("NGSS_HS_LS1_5", "Explain"),
    ("NGSS_HS_LS1_5", "Elaborate"),
    ("NGSS_HS_LS1_6", "Evaluate"),
    ("IB_BIO_11.4", "Explain"),
    ("IB_BIO_8.2", "Explain"),
    ("NGSS_HS_LS2_3", "Engage"),
]


async def run_single_eval(standard_id: str, phase: str, run_idx: int) -> dict:
    """Execute one workflow and capture metrics."""

    print(f"\n{'='*60}")
    print(f"  Run {run_idx}: {standard_id} × {phase}")
    print(f"{'='*60}")

    start = time.perf_counter()
    try:
        state = await run_workflow(standard_id, phase)
        elapsed = round(time.perf_counter() - start, 2)

        quality_report = state.get("quality_report")

        return {
            "run_idx": run_idx,
            "standard_id": standard_id,
            "five_e_phase": phase,
            "success": state.get("validation_passed", False),
            "correction_attempts": state.get("correction_attempts", 0),
            "quality_score": quality_report.total_score if quality_report else 0,
            "quality_grade": quality_report.grade if quality_report else "F",
            "rules_passed": quality_report.rules_passed if quality_report else 0,
            "rules_total": quality_report.rules_total if quality_report else 0,
            "total_tokens": state.get("total_tokens", 0),
            "duration_seconds": elapsed,
            "failed_rules": [
                {"rule": d.rule, "severity": d.severity, "message": d.message}
                for d in (quality_report.details if quality_report else [])
                if not d.passed
            ],
            "error": None,
        }
    except Exception as exc:
        elapsed = round(time.perf_counter() - start, 2)
        return {
            "run_idx": run_idx,
            "standard_id": standard_id,
            "five_e_phase": phase,
            "success": False,
            "correction_attempts": 0,
            "quality_score": 0,
            "quality_grade": "F",
            "rules_passed": 0,
            "rules_total": 0,
            "total_tokens": 0,
            "duration_seconds": elapsed,
            "failed_rules": [],
            "error": str(exc),
        }


def compute_aggregate(results: list[dict]) -> dict:
    """Compute aggregate statistics from individual run results."""

    total = len(results)
    successes = [r for r in results if r["success"]]
    first_try = [r for r in successes if r["correction_attempts"] == 0]
    corrected = [r for r in successes if r["correction_attempts"] > 0]
    failures = [r for r in results if not r["success"]]

    scores = [r["quality_score"] for r in results if r["quality_score"] > 0]
    tokens = [r["total_tokens"] for r in results]
    durations = [r["duration_seconds"] for r in results]

    # Grade distribution
    grade_dist = {}
    for r in results:
        g = r["quality_grade"]
        grade_dist[g] = grade_dist.get(g, 0) + 1

    # Most common failed rules
    rule_failures: dict[str, int] = {}
    for r in results:
        for fr in r["failed_rules"]:
            key = fr["rule"]
            rule_failures[key] = rule_failures.get(key, 0) + 1
    top_failures = sorted(rule_failures.items(), key=lambda x: -x[1])[:5]

    return {
        "total_runs": total,
        "pass_rate_first_try": f"{len(first_try)/total:.0%}" if total else "N/A",
        "pass_rate_after_correction": f"{len(successes)/total:.0%}" if total else "N/A",
        "correction_success_rate": (
            f"{len(corrected)/(len(corrected)+len(failures)):.0%}"
            if (len(corrected) + len(failures)) > 0
            else "N/A"
        ),
        "failure_rate": f"{len(failures)/total:.0%}" if total else "N/A",
        "avg_quality_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "min_quality_score": min(scores) if scores else 0,
        "max_quality_score": max(scores) if scores else 0,
        "grade_distribution": grade_dist,
        "avg_tokens_per_run": round(sum(tokens) / len(tokens)) if tokens else 0,
        "avg_duration_seconds": round(sum(durations) / len(durations), 1) if durations else 0,
        "total_tokens": sum(tokens),
        "top_failed_rules": [
            {"rule": r, "failure_count": c} for r, c in top_failures
        ],
    }


async def main():
    parser = argparse.ArgumentParser(description="KognityForge Evaluation Harness")
    parser.add_argument("--runs", type=int, default=len(EVAL_MATRIX),
                        help="Number of evaluation runs (max = matrix size)")
    parser.add_argument("--output", type=str, default="eval_results.json",
                        help="Output file for results JSON")
    args = parser.parse_args()

    matrix = EVAL_MATRIX[: args.runs]

    print("╔══════════════════════════════════════════════════════╗")
    print("║       KognityForge · Evaluation Harness             ║")
    print(f"║       Running {len(matrix)} workflows across standards       ║")
    print("╚══════════════════════════════════════════════════════╝")

    results = []
    for idx, (std, phase) in enumerate(matrix, 1):
        result = await run_single_eval(std, phase, idx)
        results.append(result)
        status = "✅" if result["success"] else "❌"
        print(
            f"  {status}  Score: {result['quality_score']}/100 "
            f"({result['quality_grade']})  "
            f"Corrections: {result['correction_attempts']}  "
            f"Tokens: {result['total_tokens']:,}  "
            f"Time: {result['duration_seconds']}s"
        )

    aggregate = compute_aggregate(results)

    output_data = {
        "evaluation_summary": aggregate,
        "individual_runs": results,
    }

    output_path = pathlib.Path(args.output)
    output_path.write_text(json.dumps(output_data, indent=2), encoding="utf-8")

    print("\n")
    print("╔══════════════════════════════════════════════════════╗")
    print("║              EVALUATION SUMMARY                     ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Total Runs:           {aggregate['total_runs']:>5}                       ║")
    print(f"║  Pass (1st try):       {aggregate['pass_rate_first_try']:>5}                       ║")
    print(f"║  Pass (w/ correction): {aggregate['pass_rate_after_correction']:>5}                       ║")
    print(f"║  Correction Success:   {aggregate['correction_success_rate']:>5}                       ║")
    print(f"║  Avg Quality Score:    {aggregate['avg_quality_score']:>5}/100                    ║")
    print(f"║  Grade Distribution:   {aggregate['grade_distribution']}  ║")
    print(f"║  Avg Tokens/Run:       {aggregate['avg_tokens_per_run']:>5,}                       ║")
    print(f"║  Avg Duration:         {aggregate['avg_duration_seconds']:>5.1f}s                      ║")
    print("╠══════════════════════════════════════════════════════╣")
    if aggregate["top_failed_rules"]:
        print("║  Top Failed Rules:                                   ║")
        for rf in aggregate["top_failed_rules"]:
            print(f"║    - {rf['rule']:<30} ({rf['failure_count']}x)    ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"\nFull results saved to: {output_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
