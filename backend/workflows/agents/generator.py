"""Generator agent – produces a full LessonContent JSON payload from the lesson plan."""

import os
import json
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from utils.logger import step_timer
from schemas.kognity_models import LessonContent, StepTrace

SYSTEM_PROMPT = (
    "You are an AI Educational Content Writer for Kognity. "
    "Generate a lesson for the given 5E phase. Constraints:\n"
    "- Tone must be accessible for 16-18 year old students.\n"
    "- Include interactive 'Big Picture' hooks where applicable.\n"
    "- Output MUST be a single valid JSON object that exactly matches "
    "the schema provided.\n"
    "- Do NOT include any text outside the JSON object."
)

SCHEMA_HINT = json.dumps(LessonContent.model_json_schema(), indent=2)


async def run_generator(state: dict, *, correction_context: str | None = None) -> dict:
    """Generate (or re-generate) lesson content and mutate *state* in-place.

    When called during a correction loop, *correction_context* carries the
    validation errors and the previous bad output so the LLM can fix them.
    """

    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
        api_version=os.getenv("OPENAI_API_VERSION", "2024-02-15-preview"),
        temperature=0.4
    )

    human_parts = [
        f"5E Phase: {state['five_e_phase']}",
        f"Lesson Plan:\n{state['lesson_plan']}",
        f"\nJSON Schema to follow:\n```json\n{SCHEMA_HINT}\n```",
    ]

    if correction_context:
        human_parts.append(
            f"\n⚠️ CORRECTION REQUEST:\n{correction_context}\n"
            "Fix the JSON payload to resolve the errors while maintaining "
            "educational integrity. Return ONLY the corrected JSON."
        )

    human_msg = "\n\n".join(human_parts)
    step_label = "Corrector Agent" if correction_context else "Generator Agent"

    with step_timer(step_label) as ctx:
        response = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=human_msg),
        ])
        ctx["tokens"] = response.usage_metadata.get("total_tokens", 0) if response.usage_metadata else 0

    raw = response.content.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    state["raw_json"] = raw
    state["total_tokens"] = state.get("total_tokens", 0) + ctx["tokens"]
    state["steps"].append(
        StepTrace(
            step_name=step_label,
            status="success",
            duration_seconds=ctx["duration"],
            prompt_snippet=human_msg[:300],
            output_snippet=raw[:500],
        )
    )
    return state
