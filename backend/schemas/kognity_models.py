"""Pydantic models for strict LLM output enforcement and validation."""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any
from enum import Enum


class FiveEPhase(str, Enum):
    ENGAGE = "Engage"
    EXPLORE = "Explore"
    EXPLAIN = "Explain"
    ELABORATE = "Elaborate"
    EVALUATE = "Evaluate"


class CognitiveLevel(str, Enum):
    RECALL = "Recall"
    APPLY = "Apply"
    ANALYZE = "Analyze"


# ── Output Schemas (LLM targets) ──────────────────────────────────────────


class MarkSchemeItem(BaseModel):
    """A single marking-point in an exam question."""
    point: str = Field(
        min_length=10,
        description="The marking point or expected student response (≥10 chars).",
    )
    marks_awarded: int = Field(ge=1, description="Marks for this point (≥1).")


class ExamQuestion(BaseModel):
    """An exam-style question with a mark scheme."""
    question_text: str = Field(min_length=20)
    total_marks: int = Field(ge=1)
    mark_scheme: List[MarkSchemeItem] = Field(min_length=1)
    cognitive_level: CognitiveLevel = Field(
        description="Bloom's level: Recall, Apply, or Analyze."
    )

    @field_validator("mark_scheme")
    @classmethod
    def marks_must_sum(cls, v, info):
        total = sum(item.marks_awarded for item in v)
        expected = info.data.get("total_marks")
        if expected is not None and total != expected:
            raise ValueError(
                f"Mark scheme points sum to {total}, but total_marks is {expected}."
            )
        return v


class SectionQuestion(BaseModel):
    """A multiple-choice knowledge-check question."""
    question: str = Field(min_length=10)
    options: List[str] = Field(min_length=3, max_length=5)
    correct_answer: str
    explanation: str = Field(min_length=15)

    @field_validator("correct_answer")
    @classmethod
    def answer_in_options(cls, v, info):
        opts = info.data.get("options", [])
        if opts and v not in opts:
            raise ValueError(
                f"correct_answer '{v}' is not among the provided options."
            )
        return v

    @field_validator("options")
    @classmethod
    def options_are_unique(cls, v):
        if len(set(v)) != len(v):
            raise ValueError("Options must be unique — no duplicate choices.")
        return v


class LessonContent(BaseModel):
    """Complete generated lesson payload."""
    title: str = Field(min_length=5)
    five_e_phase: FiveEPhase
    learning_objectives: List[str] = Field(min_length=1)
    content_blocks: List[str] = Field(min_length=1)
    knowledge_checks: List[SectionQuestion] = Field(min_length=1)
    exam_practice: ExamQuestion

    @field_validator("content_blocks")
    @classmethod
    def blocks_have_substance(cls, v):
        for i, block in enumerate(v, 1):
            if len(block.strip()) < 50:
                raise ValueError(
                    f"content_blocks[{i}] is too short ({len(block)} chars). "
                    "Each block must contain ≥50 characters of substantive text."
                )
        return v

    @field_validator("learning_objectives")
    @classmethod
    def objectives_are_actionable(cls, v):
        action_verbs = {
            "explain", "describe", "identify", "outline", "compare",
            "distinguish", "draw", "annotate", "state", "discuss",
            "analyze", "evaluate", "model", "construct", "apply",
            "define", "list", "classify", "summarize", "predict",
            "calculate", "design", "justify", "assess", "illustrate",
            "use", "highlight",
        }
        for obj in v:
            first_word = obj.strip().split()[0].lower().rstrip("s")
            if first_word not in action_verbs:
                raise ValueError(
                    f"Learning objective '{obj[:50]}…' should start with an "
                    f"action verb (e.g. Explain, Describe, Identify). "
                    f"Got: '{first_word}'."
                )
        return v


# ── Quality Score (computed by validator, not by LLM) ─────────────────────


class ValidationDetail(BaseModel):
    """One rule result in the quality report."""
    rule: str
    passed: bool
    severity: str  # "critical" | "major" | "minor"
    message: str


class QualityReport(BaseModel):
    """Computed quality report attached to every workflow run."""
    total_score: float = Field(ge=0, le=100, description="0-100 quality score")
    grade: str = Field(description="A/B/C/D/F quality grade")
    rules_passed: int
    rules_total: int
    details: List[ValidationDetail] = []


# ── Request / Response Models ─────────────────────────────────────────────


class GenerateRequest(BaseModel):
    """Payload for POST /api/v1/workflows/generate."""
    standard_id: str = Field(examples=["IB_BIO_2.9"])
    five_e_phase: FiveEPhase = Field(default=FiveEPhase.EXPLAIN)


class StepTrace(BaseModel):
    """One step in the workflow execution trace."""
    step_name: str
    status: str  # "success" | "failed" | "corrected"
    duration_seconds: float
    prompt_snippet: Optional[str] = None
    output_snippet: Optional[str] = None
    error: Optional[str] = None


class WorkflowRun(BaseModel):
    """Full record of a generation run."""
    run_id: str
    standard_id: str
    five_e_phase: FiveEPhase
    status: str  # "processing" | "completed" | "failed"
    steps: List[StepTrace] = []
    output: Optional[LessonContent] = None
    quality_report: Optional[QualityReport] = None
    total_tokens: int = 0
    total_duration_seconds: float = 0.0
