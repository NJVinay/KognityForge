"""API routes for KognityForge workflow endpoints."""

import uuid
from fastapi import APIRouter, HTTPException

from schemas.kognity_models import (
    GenerateRequest,
    WorkflowRun,
)
from workflows.orchestrator import run_workflow

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])

# In-memory store for completed runs (sufficient for prototype)
_runs: dict[str, WorkflowRun] = {}


@router.post("/generate", response_model=WorkflowRun)
async def generate_content(payload: GenerateRequest):
    """Trigger the full lesson-generation workflow."""

    run_id = str(uuid.uuid4())

    try:
        state = await run_workflow(
            standard_id=payload.standard_id,
            five_e_phase=payload.five_e_phase.value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workflow error: {exc}")

    run = WorkflowRun(
        run_id=run_id,
        standard_id=payload.standard_id,
        five_e_phase=payload.five_e_phase,
        status="completed" if state.get("validation_passed") else "failed",
        steps=state.get("steps", []),
        output=state.get("lesson_content"),
        quality_report=state.get("quality_report"),
        total_tokens=state.get("total_tokens", 0),
        total_duration_seconds=state.get("total_duration_seconds", 0.0),
    )
    _runs[run_id] = run
    return run


@router.get("/runs/{run_id}", response_model=WorkflowRun)
async def get_run(run_id: str):
    """Retrieve the result of a previous workflow run."""

    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


@router.get("/standards")
async def list_standards():
    """Return available curriculum standards (for the Streamlit frontend)."""

    import json, pathlib

    path = pathlib.Path(__file__).resolve().parent.parent / "data" / "standards.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)
