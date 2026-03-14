"""Tests for the workflow orchestrator routing logic (LLM calls mocked)."""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))


def _make_usage_metadata(total_tokens: int = 100):
    return {"total_tokens": total_tokens}


def _valid_lesson_json():
    """Return a JSON string that passes ALL Pydantic validators and quality rules."""
    return json.dumps({
        "title": "Photosynthesis – Explain Phase",
        "five_e_phase": "Explain",
        "learning_objectives": [
            "Explain the process of photosynthesis including the light-dependent reactions.",
            "Identify the main photosynthetic pigments and their absorption spectra.",
        ],
        "content_blocks": [
            "Photosynthesis is the process by which green plants and certain other organisms "
            "transform light energy into chemical energy. During photosynthesis in green plants, "
            "light energy is captured and used to convert water, carbon dioxide, and minerals into "
            "oxygen and energy-rich organic compounds such as glucose.",
            "The light-dependent reactions take place in the thylakoid membranes of the chloroplast. "
            "Here, chlorophyll and other pigments absorb light energy and use it to drive the "
            "synthesis of ATP and NADPH, while splitting water molecules to release oxygen as a "
            "by-product of the reaction.",
            "The Calvin cycle (light-independent reactions) occurs in the stroma. Carbon dioxide is "
            "fixed by the enzyme RuBisCO and reduced using the ATP and NADPH produced in the "
            "light-dependent reactions. The end product is glyceraldehyde-3-phosphate (G3P), which "
            "can be used to synthesise glucose and other organic molecules.",
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
            },
            {
                "question": "What is the primary role of chlorophyll in photosynthesis?",
                "options": [
                    "To absorb light energy for the reactions",
                    "To transport water through the plant",
                    "To store glucose in the leaves",
                ],
                "correct_answer": "To absorb light energy for the reactions",
                "explanation": "Chlorophyll is the main photosynthetic pigment that absorbs red and blue wavelengths of light to power the reactions.",
            },
        ],
        "exam_practice": {
            "question_text": "Describe the process of photosynthesis, including the roles of light-dependent and light-independent reactions.",
            "total_marks": 3,
            "mark_scheme": [
                {"point": "Light-dependent reactions produce ATP and NADPH in the thylakoid membranes", "marks_awarded": 1},
                {"point": "Light-independent reactions (Calvin cycle) fix CO2 into G3P in the stroma", "marks_awarded": 1},
                {"point": "Chlorophyll absorbs light energy which is converted to chemical energy in ATP", "marks_awarded": 1},
            ],
            "cognitive_level": "Apply",
        },
    })


def _mock_llm_response(content: str):
    resp = MagicMock()
    resp.content = content
    resp.usage_metadata = _make_usage_metadata()
    return resp


def test_workflow_happy_path():
    """Valid LLM output should pass validation on the first try."""

    with patch("workflows.agents.planner.AzureChatOpenAI") as MockLLM:
        planner_resp = _mock_llm_response("Lesson outline: 1. Intro 2. Body 3. Summary")
        instance = MockLLM.return_value
        instance.ainvoke = AsyncMock(return_value=planner_resp)

        with patch("workflows.agents.generator.AzureChatOpenAI") as MockGenLLM:
            gen_resp = _mock_llm_response(_valid_lesson_json())
            gen_instance = MockGenLLM.return_value
            gen_instance.ainvoke = AsyncMock(return_value=gen_resp)

            from workflows.orchestrator import run_workflow

            state = asyncio.run(run_workflow("IB_BIO_2.9", "Explain"))
            assert state["validation_passed"] is True
            assert state["lesson_content"] is not None
            assert state["correction_attempts"] == 0


def test_workflow_correction_loop_triggers():
    """Invalid LLM output should trigger the correction loop then succeed."""

    bad_json = json.dumps({"title": "Bad"})  # Missing required fields

    call_count = 0

    async def smart_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_llm_response("Lesson outline text")
        elif call_count == 2:
            return _mock_llm_response(bad_json)  # First attempt: invalid
        else:
            return _mock_llm_response(_valid_lesson_json())  # Correction: valid

    with patch("workflows.agents.planner.AzureChatOpenAI") as MockP:
        MockP.return_value.ainvoke = AsyncMock(side_effect=smart_generate)

        with patch("workflows.agents.generator.AzureChatOpenAI") as MockG:
            MockG.return_value.ainvoke = AsyncMock(side_effect=smart_generate)

            from workflows.orchestrator import run_workflow

            state = asyncio.run(run_workflow("IB_BIO_2.9", "Explain"))
            assert state["validation_passed"] is True
            assert state["correction_attempts"] >= 1


def test_workflow_unknown_standard_raises():
    """Requesting an unknown standard_id should raise ValueError."""

    from workflows.orchestrator import run_workflow

    with pytest.raises(ValueError, match="Unknown standard_id"):
        asyncio.run(run_workflow("FAKE_STANDARD", "Explain"))
