# KognityForge 🧬

AI-powered educational content generation workflow, aligned with the **5E instructional model** and styled with Kognity's design system.

## Overview

KognityForge is a proof-of-concept prototype demonstrating an AI workflow that generates structured, curriculum-aligned educational content (lessons, section questions, exam questions) using a multi-agent orchestration pipeline.

### Architecture

```
Streamlit UI  →  FastAPI  →  Planner Agent  →  Generator Agent  →  Validator Agent
                                                                        ↓
                                                              Corrector Loop (max 3)
                                                                        ↓
                                                              Validated JSON Output
```

### Key Features

- **Multi-agent orchestration**: Planner → Generator → Validator → Corrector self-healing loop
- **Strict schema enforcement**: Pydantic models with custom validators (mark-scheme arithmetic, answer validation)
- **Curriculum-aligned**: Supports IB DP Biology and NGSS standards via configurable metadata
- **5E Instructional Model**: Generates content for all five phases (Engage, Explore, Explain, Elaborate, Evaluate)
- **Kognity-themed UI**: Streamlit frontend styled with Kognity's design tokens (`#2D1B4E`, `#00E5A0`, `#FAF8F4`)
- **Full observability**: Step-by-step workflow trace with timings, token counts, and prompt/output snippets

## Quick Start

```bash
# 1. Clone & setup
git clone <repo-url> && cd KognityForge
python -m venv .venv && .venv\Scripts\activate
pip install -r backend/requirements.txt -r frontend/requirements.txt

# 2. Configure
copy .env.example .env
# Edit .env → add your OPENAI_API_KEY

# 3. Run backend
cd backend && uvicorn main:app --reload

# 4. Run frontend (new terminal)
cd frontend && streamlit run app.py

# 5. Run tests
pip install pytest pytest-asyncio
pytest tests/ -v
```

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.11+ |
| AI/LLM | OpenAI GPT-4o-mini via LangChain |
| Validation | Pydantic v2 |
| Frontend | Streamlit |
| Testing | Pytest + unittest.mock |

## Project Structure

```
KognityForge/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── api/routes.py              # REST endpoints
│   ├── schemas/kognity_models.py  # Pydantic output schemas
│   ├── workflows/
│   │   ├── orchestrator.py        # DAG state machine
│   │   ├── state.py               # TypedDict graph state
│   │   └── agents/                # Planner, Generator, Validator
│   ├── data/                      # Standards + 5E config JSON
│   └── utils/logger.py            # Structured step logger
├── frontend/
│   ├── app.py                     # Streamlit application
│   ├── style.css                  # Kognity design system CSS
│   └── .streamlit/config.toml     # Theme tokens
├── tests/
│   ├── test_schemas.py            # Pydantic validation tests
│   └── test_workflow.py           # Orchestrator integration tests
└── .env.example
```