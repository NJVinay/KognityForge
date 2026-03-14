"""Planner agent – creates a structured lesson outline from standard metadata."""

import os
import json
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from utils.logger import step_timer
from schemas.kognity_models import StepTrace

SYSTEM_PROMPT = (
    "You are a Senior Curriculum Specialist for Kognity. "
    "You design lessons that strictly follow the 5E instructional model. "
    "Given a curriculum standard and a 5E phase, outline the required learning "
    "objectives, key vocabulary, and a lesson structure with 3-5 content blocks. "
    "Return a clear, numbered outline – do NOT generate the full lesson text yet."
)


async def run_planner(state: dict) -> dict:
    """Generate a lesson plan outline and mutate *state* in-place."""

    llm = AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
        api_version=os.getenv("OPENAI_API_VERSION", "2024-02-15-preview"),
        temperature=0.3
    )

    human_msg = (
        f"Curriculum Framework: {state['standard_meta']['framework']}\n"
        f"Subject: {state['standard_meta']['subject']}\n"
        f"Topic: {state['standard_meta']['topic']}\n"
        f"Description: {state['standard_meta']['description']}\n"
        f"Objectives: {json.dumps(state['standard_meta']['objectives'])}\n\n"
        f"5E Phase: {state['five_e_phase']}\n"
        f"Phase guidance: {state['five_e_config'].get('instructions', '')}\n\n"
        "Produce a numbered lesson outline including learning objectives, "
        "key vocabulary, and 3-5 content block titles with brief descriptions."
    )

    with step_timer("Planner Agent") as ctx:
        response = await llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=human_msg),
        ])
        ctx["tokens"] = response.usage_metadata.get("total_tokens", 0) if response.usage_metadata else 0

    state["lesson_plan"] = response.content
    state["total_tokens"] = state.get("total_tokens", 0) + ctx["tokens"]
    state["steps"].append(
        StepTrace(
            step_name="Planner Agent",
            status="success",
            duration_seconds=ctx["duration"],
            prompt_snippet=human_msg[:300],
            output_snippet=response.content[:500],
        )
    )
    return state
