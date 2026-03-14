"""KognityForge – Streamlit Frontend Application.

Themed with Kognity's design tokens (#2D1B4E purple, #00E5A0 mint, #FAF8F4 off-white).
Four-tab layout: Output Preview · JSON Payload · Quality Report · Workflow Trace.
"""

import json
import pathlib
import streamlit as st
import httpx

# ── Page Config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KognityForge · AI Content Workflow",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject custom CSS ────────────────────────────────────────────────────
css_path = pathlib.Path(__file__).parent / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# ── Constants ────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"

# ── Helpers ──────────────────────────────────────────────────────────────


@st.cache_data(ttl=300)
def fetch_standards() -> dict:
    """Pull available standards from the backend."""
    try:
        resp = httpx.get(f"{API_BASE}/api/v1/workflows/standards", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        # Fallback to local file if backend is not running
        local = pathlib.Path(__file__).parent.parent / "backend" / "data" / "standards.json"
        if local.exists():
            return json.loads(local.read_text(encoding="utf-8"))
        return {}


def render_lesson_preview(output: dict):
    """Render the lesson in a student-facing format mimicking Kognity's book view."""
    
    with st.container():
        st.markdown(f"## 📘 {output['title']}")
        st.caption(f"**5E Phase:** {output['five_e_phase']}")
        st.write("")

        # Learning Objectives Card
        with st.container():
            st.markdown("### 🎯 Learning Objectives")
            for obj in output.get("learning_objectives", []):
                st.markdown(f"- {obj}")

        st.write("")

        # Content Blocks
        for i, block in enumerate(output.get("content_blocks", []), 1):
            st.markdown(block)
            if i < len(output.get("content_blocks", [])):
                st.markdown("")

        st.write("")

        # Knowledge Checks
        with st.container():
            st.markdown("### ✅ Test Your Knowledge")
            for idx, q in enumerate(output.get("knowledge_checks", []), 1):
                with st.expander(f"**Question {idx}:** {q['question'][:80]}…"):
                    for opt in q["options"]:
                        st.markdown(f"- {opt}")
                    st.success(f"**Answer:** {q['correct_answer']}")
                    st.info(f"💡 {q['explanation']}")

        st.write("")

        # Exam Practice
        with st.container():
            exam = output.get("exam_practice", {})
            st.markdown("### 📝 Exam Practice")
            st.markdown(f"**{exam.get('question_text', '')}**  ")
            st.caption(
                f"Total marks: **{exam.get('total_marks', '?')}** · "
                f"Cognitive Level: **{exam.get('cognitive_level', '?')}**"
            )
            with st.expander("View Mark Scheme"):
                for m in exam.get("mark_scheme", []):
                    st.markdown(f"- {m['point']} **[{m['marks_awarded']} mark(s)]**")


def render_quality_report(report: dict):
    """Render the computable quality report with rule-by-rule breakdown."""

    score = report.get("total_score", 0)
    grade = report.get("grade", "?")
    passed = report.get("rules_passed", 0)
    total = report.get("rules_total", 0)

    # Score header with color
    if score >= 90:
        color = "#00E5A0"
    elif score >= 75:
        color = "#4CAF50"
    elif score >= 60:
        color = "#FF9800"
    else:
        color = "#E74C3C"

    # Hero Quality Score
    st.markdown(
        f"""
        <div style="background: white; padding: 30px; border-radius: 16px; border: 1px solid #eaeaea; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.02); margin-bottom: 20px;">
            <p style="color: #718096; font-size: 1rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0;">Overall Quality</p>
            <h2 style='text-align:center; margin-top: 5px; margin-bottom: 5px;'>
                <span style='color:{color}; font-size:4.5rem; font-weight: 800;'>{score}</span>
                <span style='color:#a0aec0; font-size:2rem; font-weight: 500;'>/100</span>
            </h2>
            <div style="display: flex; justify-content: center; gap: 15px; margin-top: 10px;">
                <span style='background: {color}20; color: {color}; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 1.1rem;'>Grade {grade}</span>
                <span style='background: #f1f3f5; color: #4A5568; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 1.1rem;'>{passed}/{total} Rules Passed</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Rule-by-rule breakdown
    st.markdown("### 📋 Rule Processing Details")
    for detail in report.get("details", []):
        passed_icon = "✅" if detail["passed"] else "❌"
        severity_badge = {
            "critical": "🔴",
            "major": "🟠",
            "minor": "🟡",
        }.get(detail["severity"], "⚪")

        with st.expander(
            f"{passed_icon}  **{detail['rule'].replace('_', ' ').title()}**  ({severity_badge} {detail['severity'].upper()})",
            expanded=not detail["passed"],
        ):
            st.markdown(detail["message"])


def render_workflow_trace(steps: list):
    """Render the step-by-step execution trace."""
    st.markdown("### 🔍 Execution Trace")
    for step in steps:
        icon = "✅" if step["status"] == "success" else "❌"
        dur = f"{step['duration_seconds']:.2f}s"
        label = f"{icon}  **{step['step_name']}**  —  _took {dur}_"

        with st.expander(label, expanded=(step["status"] != "success")):
            if step.get("prompt_snippet"):
                st.markdown("**Prompt (truncated):**")
                st.code(step["prompt_snippet"], language="text")
            if step.get("output_snippet"):
                st.markdown("**Output (truncated):**")
                st.code(step["output_snippet"], language="text")
            if step.get("error"):
                st.error(step["error"])


def render_results(result: dict):
    """Render the full results dashboard."""

    # ── Metrics row ──
    qr = result.get("quality_report")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", result["status"].upper())
    col2.metric("Quality Score", f"{qr['total_score']} ({qr['grade']})" if qr else "N/A")
    col3.metric("Tokens Used", f"{result.get('total_tokens', 0):,}")
    col4.metric("Generation Time", f"{result.get('total_duration_seconds', 0):.1f}s")

    st.write("")

    # ── Tabs ──
    tab_preview, tab_json, tab_quality, tab_trace = st.tabs([
        "📖 Content Preview",
        "📦 JSON Payload",
        "📊 Quality Report",
        "⚙️ Trace Logs",
    ])

    with tab_preview:
        if result.get("output"):
            render_lesson_preview(result["output"])
        else:
            st.warning("No valid output was produced. Check the Trace Logs.")

    with tab_json:
        if result.get("output"):
            st.json(result["output"])
            # Provide download button for JSON
            json_str = json.dumps(result["output"], indent=2)
            st.download_button(
                label="⬇️ Download JSON",
                file_name=f"lesson_{result.get('standard_id', 'output')}.json",
                mime="application/json",
                data=json_str,
                use_container_width=True
            )
        else:
            st.code("No output available.", language="text")

    with tab_quality:
        if qr:
            render_quality_report(qr)
        else:
            st.info("Quality report not available for this run.")

    with tab_trace:
        render_workflow_trace(result.get("steps", []))


# ── Sidebar ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h1 style='font-size: 2.2rem;'>✨ KognityForge</h1>", unsafe_allow_html=True)
    st.caption("AI Content Workflow Engine")
    st.write("")

    standards = fetch_standards()
    if not standards:
        st.warning("Could not load standards. Is the backend running?")
        st.stop()

    # Build human-readable labels
    std_labels = {
        sid: f"{meta['framework']} · {meta['topic']}"
        for sid, meta in standards.items()
    }

    selected_label = st.selectbox(
        "📚 Curriculum Standard",
        options=list(std_labels.values()),
        index=0,
    )
    # Reverse-lookup the standard_id
    selected_id = next(
        sid for sid, lbl in std_labels.items() if lbl == selected_label
    )

    st.write("")

    selected_phase = st.selectbox(
        "🔬 5E Phase Target",
        options=["Engage", "Explore", "Explain", "Elaborate", "Evaluate"],
        index=2,  # default to Explain
    )

    st.markdown("---")

    # Show selected standard details
    meta = standards[selected_id]
    st.markdown(f"**Subject:** {meta['subject']}")
    st.markdown(f"**Level:** {meta.get('level', 'N/A')}")
    st.markdown(f"**Description:** {meta['description'][:200]}…" if len(meta['description']) > 200 else f"**Description:** {meta['description']}")
    
    with st.expander("📖 Objectives & Vocabulary"):
        st.markdown("**Objectives:**")
        for obj in meta["objectives"]:
            st.markdown(f"- {obj}")
        if meta.get("key_vocabulary"):
            st.markdown("**Key Vocabulary:**")
            st.markdown(", ".join(f"`{v}`" for v in meta["key_vocabulary"][:8]))

    if meta.get("misconceptions"):
        with st.expander("⚠️ Common Misconceptions"):
            for mc in meta["misconceptions"]:
                st.markdown(f"- {mc}")

    st.write("")
    generate_btn = st.button("🚀 Generate Content", use_container_width=True)


# ── Main Canvas ──────────────────────────────────────────────────────────
st.markdown("<h1 style='font-size: 3rem; margin-bottom: 0;'>Content Studio</h1>", unsafe_allow_html=True)
st.caption("Review generated content, inspect JSON structures, and analyze quality validation scores.")
st.write("")

if generate_btn:
    with st.status("Executing Cognitive Workflow…", expanded=True) as status_ui:
        st.write("⏳ `Planner` Generating structured lesson outline...")
        st.write("⏳ `Generator` Writing 5E-aligned educational content...")
        st.write("⏳ `Validator` Checking 12 quality and schema business rules...")

        try:
            resp = httpx.post(
                f"{API_BASE}/api/v1/workflows/generate",
                json={
                    "standard_id": selected_id,
                    "five_e_phase": selected_phase,
                },
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
        except httpx.ConnectError:
            st.error(
                "❌ Cannot reach the backend at `localhost:8000`. "
                "Start the FastAPI server first:\n\n"
                "```bash\ncd backend && uvicorn main:app --reload\n```"
            )
            st.stop()
        except Exception as exc:
            st.error(f"❌ API Request failed: {exc}")
            st.stop()

        if result["status"] == "completed":
            status_ui.update(label="✨ Workflow completed successfully!", state="complete")
        else:
            status_ui.update(label="⚠️ Workflow finished with errors flagged by Validator", state="error")

    render_results(result)
    st.session_state["last_run"] = result

elif "last_run" in st.session_state:
    render_results(st.session_state["last_run"])

else:
    with st.container():
        st.info(
            "👋 **Welcome to KognityForge!** \n\n"
            "Configure a **curriculum standard** and **5E phase** in the left sidebar, "
            "then click **Generate Content** to trigger the AI workflow pipeline."
        )
