"""Tests for Pydantic validation schemas."""

import pytest
from pydantic import ValidationError

# Add backend to path
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))

from schemas.kognity_models import (
    ExamQuestion,
    SectionQuestion,
    LessonContent,
    MarkSchemeItem,
)


# ── ExamQuestion tests ────────────────────────────────────────────────────


def test_exam_question_valid():
    q = ExamQuestion(
        question_text="Explain the role of chlorophyll in absorbing light energy for photosynthesis.",
        total_marks=3,
        mark_scheme=[
            MarkSchemeItem(point="Absorbs red and blue light wavelengths effectively", marks_awarded=1),
            MarkSchemeItem(point="Located in thylakoid membranes of chloroplasts", marks_awarded=1),
            MarkSchemeItem(point="Transfers light energy to chemical energy via excited electrons", marks_awarded=1),
        ],
        cognitive_level="Recall",
    )
    assert q.total_marks == 3


def test_exam_question_negative_marks_rejected():
    with pytest.raises(ValidationError):
        ExamQuestion(
            question_text="This question has invalid negative marks assigned to it.",
            total_marks=-1,
            mark_scheme=[],
            cognitive_level="Recall",
        )


def test_exam_question_marks_mismatch():
    with pytest.raises(ValidationError, match="sum to"):
        ExamQuestion(
            question_text="Marks on this question do not sum correctly to the total.",
            total_marks=5,
            mark_scheme=[
                MarkSchemeItem(point="Point A discusses cell membrane structure", marks_awarded=2),
                MarkSchemeItem(point="Point B discusses protein synthesis steps", marks_awarded=1),
            ],
            cognitive_level="Apply",
        )


def test_exam_question_short_text_rejected():
    """Question text must be ≥20 characters."""
    with pytest.raises(ValidationError):
        ExamQuestion(
            question_text="Short?",
            total_marks=1,
            mark_scheme=[
                MarkSchemeItem(point="A valid marking point with sufficient detail", marks_awarded=1),
            ],
            cognitive_level="Recall",
        )


def test_mark_scheme_item_short_point_rejected():
    """Mark scheme point must be ≥10 characters."""
    with pytest.raises(ValidationError):
        MarkSchemeItem(point="Short", marks_awarded=1)


# ── SectionQuestion tests ────────────────────────────────────────────────


def test_section_question_valid():
    q = SectionQuestion(
        question="What is the full name of ATP in biochemistry?",
        options=["Adenosine Triphosphate", "A transport protein", "A type of lipid"],
        correct_answer="Adenosine Triphosphate",
        explanation="ATP stands for Adenosine Triphosphate, the cell's primary energy currency.",
    )
    assert q.correct_answer in q.options


def test_section_question_answer_not_in_options():
    with pytest.raises(ValidationError, match="not among the provided options"):
        SectionQuestion(
            question="What is the full name of ATP in biochemistry?",
            options=["A transport protein", "A type of lipid", "A carbohydrate molecule"],
            correct_answer="Adenosine Triphosphate",
            explanation="Should fail because the answer is missing from options.",
        )


def test_section_question_too_few_options():
    with pytest.raises(ValidationError):
        SectionQuestion(
            question="Bad question with too few options provided",
            options=["Option A", "Option B"],
            correct_answer="Option A",
            explanation="Only 2 options, need minimum 3.",
        )


def test_section_question_duplicate_options_rejected():
    """Options must be unique."""
    with pytest.raises(ValidationError, match="unique"):
        SectionQuestion(
            question="What is the main function of mitochondria in the cell?",
            options=["Energy production", "Energy production", "Protein synthesis"],
            correct_answer="Energy production",
            explanation="Mitochondria are the powerhouse of the cell.",
        )


def test_section_question_short_explanation_rejected():
    """Explanation must be ≥15 characters."""
    with pytest.raises(ValidationError):
        SectionQuestion(
            question="A valid question about cellular biology processes",
            options=["Option A", "Option B", "Option C"],
            correct_answer="Option A",
            explanation="Too short",
        )


# ── LessonContent tests ──────────────────────────────────────────────────


def _valid_lesson_dict():
    return {
        "title": "Photosynthesis – Explain Phase",
        "five_e_phase": "Explain",
        "learning_objectives": [
            "Explain the process of photosynthesis including light-dependent reactions.",
            "Identify the main photosynthetic pigments and their roles.",
        ],
        "content_blocks": [
            "Photosynthesis is the process by which green plants and certain other organisms transform light energy into chemical energy. During photosynthesis in green plants, light energy is captured and used to convert water, carbon dioxide, and minerals into oxygen and energy-rich organic compounds.",
            "The light-dependent reactions take place in the thylakoid membranes of the chloroplast. Here, chlorophyll and other pigments absorb light energy and use it to drive the synthesis of ATP and NADPH, while splitting water molecules to release oxygen as a by-product of the reaction.",
        ],
        "knowledge_checks": [
            {
                "question": "Where do the light-dependent reactions of photosynthesis take place?",
                "options": [
                    "In the thylakoid membranes",
                    "In the stroma of the chloroplast",
                    "In the cell cytoplasm",
                ],
                "correct_answer": "In the thylakoid membranes",
                "explanation": "The light-dependent reactions occur in the thylakoid membranes where chlorophyll absorbs light energy.",
            }
        ],
        "exam_practice": {
            "question_text": "Describe the process of photosynthesis, including the roles of light-dependent and light-independent reactions.",
            "total_marks": 2,
            "mark_scheme": [
                {"point": "Light-dependent reactions produce ATP and NADPH in thylakoids", "marks_awarded": 1},
                {"point": "Light-independent reactions (Calvin cycle) fix CO2 into G3P in stroma", "marks_awarded": 1},
            ],
            "cognitive_level": "Apply",
        },
    }


def test_lesson_content_valid():
    lesson = LessonContent.model_validate(_valid_lesson_dict())
    assert lesson.title.startswith("Photosynthesis")


def test_lesson_content_missing_objectives():
    data = _valid_lesson_dict()
    data["learning_objectives"] = []
    with pytest.raises(ValidationError):
        LessonContent.model_validate(data)


def test_lesson_content_short_block_rejected():
    """Content blocks must be ≥50 characters."""
    data = _valid_lesson_dict()
    data["content_blocks"] = ["Too short", "Also too short"]
    with pytest.raises(ValidationError, match="too short"):
        LessonContent.model_validate(data)


def test_lesson_content_noaction_objective_rejected():
    """Learning objectives must start with an action verb."""
    data = _valid_lesson_dict()
    data["learning_objectives"] = ["The student will learn about cells."]
    with pytest.raises(ValidationError, match="action verb"):
        LessonContent.model_validate(data)
