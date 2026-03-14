"""Workflow graph state definition."""

from typing import TypedDict, Optional, List
from schemas.kognity_models import LessonContent, StepTrace


class WorkflowState(TypedDict, total=False):
    """Mutable state passed between nodes in the workflow graph."""

    # ── Inputs ──
    standard_id: str
    five_e_phase: str
    standard_meta: dict          # resolved from standards.json
    five_e_config: dict          # resolved from five_e_model.json

    # ── Planner outputs ──
    lesson_plan: str             # free-text outline from the Planner agent

    # ── Generator outputs ──
    raw_json: str                # raw LLM JSON string
    lesson_content: Optional[LessonContent]  # parsed & validated lesson

    # ── Validation loop ──
    validation_passed: bool
    validation_errors: str
    correction_attempts: int
    max_corrections: int

    # ── Observability ──
    steps: List[StepTrace]
    total_tokens: int
