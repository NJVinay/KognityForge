"""Workflow orchestrator – runs the Planner → Generator → Validator → Corrector loop."""

import json
import pathlib
import time

from workflows.agents.planner import run_planner
from workflows.agents.generator import run_generator
from workflows.agents.validator import run_validator
from utils.logger import logger

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
MAX_CORRECTIONS = 3


def _load_json(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def run_workflow(standard_id: str, five_e_phase: str) -> dict:
    """Execute the full content-generation workflow and return the final state."""

    standards = _load_json(DATA_DIR / "standards.json")
    five_e = _load_json(DATA_DIR / "five_e_model.json")

    if standard_id not in standards:
        raise ValueError(
            f"Unknown standard_id '{standard_id}'. "
            f"Available: {list(standards.keys())}"
        )
    if five_e_phase not in five_e:
        raise ValueError(
            f"Unknown 5E phase '{five_e_phase}'. "
            f"Available: {list(five_e.keys())}"
        )

    state: dict = {
        "standard_id": standard_id,
        "five_e_phase": five_e_phase,
        "standard_meta": standards[standard_id],
        "five_e_config": five_e[five_e_phase],
        "lesson_plan": "",
        "raw_json": "",
        "lesson_content": None,
        "quality_report": None,
        "validation_passed": False,
        "validation_errors": "",
        "correction_attempts": 0,
        "max_corrections": MAX_CORRECTIONS,
        "steps": [],
        "total_tokens": 0,
    }

    overall_start = time.perf_counter()

    # ── Step 1: Planner ──
    logger.info("━━━  STEP 1/3 – Planning  ━━━")
    state = await run_planner(state)

    # ── Step 2: Generator ──
    logger.info("━━━  STEP 2/3 – Generating  ━━━")
    state = await run_generator(state)

    # ── Step 3: Validate (with correction loop) ──
    logger.info("━━━  STEP 3/3 – Validating  ━━━")
    while state["correction_attempts"] <= MAX_CORRECTIONS:
        state = await run_validator(state)

        if state["validation_passed"]:
            qr = state.get("quality_report")
            score_info = f" (Score: {qr.total_score}/100 – {qr.grade})" if qr else ""
            logger.info("✅  Validation passed%s – workflow complete.", score_info)
            break

        state["correction_attempts"] += 1
        if state["correction_attempts"] > MAX_CORRECTIONS:
            logger.warning(
                "⚠️  Max correction attempts (%d) exceeded.", MAX_CORRECTIONS
            )
            break

        logger.info(
            "🔄  Correction attempt %d/%d",
            state["correction_attempts"],
            MAX_CORRECTIONS,
        )
        correction_ctx = (
            f"Previous output:\n{state['raw_json']}\n\n"
            f"Validation errors:\n{state['validation_errors']}"
        )
        state = await run_generator(state, correction_context=correction_ctx)

    state["total_duration_seconds"] = round(
        time.perf_counter() - overall_start, 3
    )
    return state
