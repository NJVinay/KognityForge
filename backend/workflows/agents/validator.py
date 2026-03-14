"""Validator agent – Pydantic + 12 business-rule quality checks with computable scoring.

Each rule has a severity (critical=0, major=5, minor=2 deduction from 100).
The validator produces a QualityReport with a 0-100 score and A-F grade.
"""

import json
import time
from pydantic import ValidationError

from utils.logger import logger
from schemas.kognity_models import (
    LessonContent,
    StepTrace,
    QualityReport,
    ValidationDetail,
)

# ── Severity weights (deducted from 100) ──────────────────────────────────
SEVERITY_PENALTY = {"critical": 0, "major": 8, "minor": 3}
# critical = instant fail (score set to 0), major/minor = point deductions


def _grade_from_score(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _run_quality_rules(
    lesson: LessonContent,
    standard_meta: dict,
    five_e_config: dict,
) -> QualityReport:
    """Run 12+ business rules and return a QualityReport."""

    details: list[ValidationDetail] = []
    phase_rules = five_e_config.get("content_rules", {})

    # ── 1. Content block count within 5E-phase range ──
    min_blocks = phase_rules.get("min_content_blocks", 2)
    max_blocks = phase_rules.get("max_content_blocks", 6)
    block_count = len(lesson.content_blocks)
    details.append(ValidationDetail(
        rule="content_block_count",
        passed=min_blocks <= block_count <= max_blocks,
        severity="major",
        message=(
            f"Expected {min_blocks}-{max_blocks} content blocks for "
            f"{lesson.five_e_phase.value} phase, got {block_count}."
        ),
    ))

    # ── 2. Knowledge-check count within 5E-phase range ──
    min_kc = phase_rules.get("min_knowledge_checks", 1)
    max_kc = phase_rules.get("max_knowledge_checks", 4)
    kc_count = len(lesson.knowledge_checks)
    details.append(ValidationDetail(
        rule="knowledge_check_count",
        passed=min_kc <= kc_count <= max_kc,
        severity="major",
        message=(
            f"Expected {min_kc}-{max_kc} knowledge checks for "
            f"{lesson.five_e_phase.value} phase, got {kc_count}."
        ),
    ))

    # ── 3. Exam marks within 5E-phase range ──
    marks_range = phase_rules.get("exam_question_marks_range", [1, 10])
    total_marks = lesson.exam_practice.total_marks
    details.append(ValidationDetail(
        rule="exam_marks_range",
        passed=marks_range[0] <= total_marks <= marks_range[1],
        severity="major",
        message=(
            f"Expected {marks_range[0]}-{marks_range[1]} total marks for "
            f"{lesson.five_e_phase.value} phase exam, got {total_marks}."
        ),
    ))

    # ── 4. Cognitive level matches 5E-phase expectations ──
    expected_levels = phase_rules.get("expected_cognitive_levels", [])
    cog_level = lesson.exam_practice.cognitive_level.value
    level_ok = cog_level in expected_levels if expected_levels else True
    details.append(ValidationDetail(
        rule="cognitive_level_alignment",
        passed=level_ok,
        severity="minor",
        message=(
            f"Exam cognitive level '{cog_level}' not in expected levels "
            f"{expected_levels} for {lesson.five_e_phase.value} phase."
        ),
    ))

    # ── 5. Mark scheme arithmetic ──
    marks_sum = sum(m.marks_awarded for m in lesson.exam_practice.mark_scheme)
    details.append(ValidationDetail(
        rule="mark_scheme_sum",
        passed=marks_sum == total_marks,
        severity="critical",
        message=(
            f"Mark scheme sums to {marks_sum} but total_marks is {total_marks}."
        ),
    ))

    # ── 6. Key vocabulary coverage ──
    key_vocab = [v.lower() for v in standard_meta.get("key_vocabulary", [])]
    if key_vocab:
        all_text = " ".join(lesson.content_blocks).lower()
        covered = [v for v in key_vocab if v in all_text]
        coverage = len(covered) / len(key_vocab)
        details.append(ValidationDetail(
            rule="vocabulary_coverage",
            passed=coverage >= 0.5,
            severity="major",
            message=(
                f"Key vocabulary coverage: {len(covered)}/{len(key_vocab)} "
                f"({coverage:.0%}). Missing: "
                f"{[v for v in key_vocab if v not in all_text][:5]}"
            ),
        ))
    else:
        details.append(ValidationDetail(
            rule="vocabulary_coverage",
            passed=True,
            severity="minor",
            message="No key vocabulary defined for this standard (skipped).",
        ))

    # ── 7. Learning objectives cover standard objectives ──
    std_objectives = standard_meta.get("objectives", [])
    if std_objectives:
        lesson_obj_text = " ".join(lesson.learning_objectives).lower()
        matched = sum(
            1
            for obj in std_objectives
            if any(
                word in lesson_obj_text
                for word in obj.lower().split()
                if len(word) > 4
            )
        )
        obj_coverage = matched / len(std_objectives)
        details.append(ValidationDetail(
            rule="objective_coverage",
            passed=obj_coverage >= 0.4,
            severity="major",
            message=(
                f"Standard objective alignment: {matched}/{len(std_objectives)} "
                f"objectives have keyword overlap ({obj_coverage:.0%})."
            ),
        ))
    else:
        details.append(ValidationDetail(
            rule="objective_coverage",
            passed=True,
            severity="minor",
            message="No standard objectives defined (skipped).",
        ))

    # ── 8. Misconception awareness ──
    misconceptions = standard_meta.get("misconceptions", [])
    all_text_lower = " ".join(lesson.content_blocks).lower()
    if misconceptions:
        bad_matches = []
        for mc in misconceptions:
            mc_lower = mc.lower()
            key_phrase = " ".join(mc_lower.split()[:6])
            if key_phrase in all_text_lower:
                idx = all_text_lower.index(key_phrase)
                context = all_text_lower[max(0, idx - 30) : idx + len(key_phrase)]
                negation_words = {"not", "don't", "doesn't", "isn't", "incorrect", "wrong", "false", "myth", "misconception"}
                if not any(neg in context for neg in negation_words):
                    bad_matches.append(mc[:60])
        details.append(ValidationDetail(
            rule="misconception_safety",
            passed=len(bad_matches) == 0,
            severity="major",
            message=(
                f"Content may inadvertently reinforce misconceptions: {bad_matches}"
                if bad_matches
                else "No known misconceptions detected in content (good)."
            ),
        ))
    else:
        details.append(ValidationDetail(
            rule="misconception_safety",
            passed=True,
            severity="minor",
            message="No misconceptions defined for this standard (skipped).",
        ))

    # ── 9. Content block minimum length ──
    short_blocks = [
        i for i, b in enumerate(lesson.content_blocks, 1)
        if len(b.strip()) < 100
    ]
    details.append(ValidationDetail(
        rule="content_depth",
        passed=len(short_blocks) == 0,
        severity="minor",
        message=(
            f"Content blocks {short_blocks} have fewer than 100 characters — "
            "consider adding more depth."
            if short_blocks
            else "All content blocks have sufficient depth (≥100 chars)."
        ),
    ))

    # ── 10. Question explanations have substance ──
    shallow_explanations = [
        i for i, kc in enumerate(lesson.knowledge_checks, 1)
        if len(kc.explanation.strip()) < 30
    ]
    details.append(ValidationDetail(
        rule="explanation_depth",
        passed=len(shallow_explanations) == 0,
        severity="minor",
        message=(
            f"Knowledge-check explanations {shallow_explanations} are too brief "
            "(< 30 chars). Students need substantive feedback."
            if shallow_explanations
            else "All explanations have sufficient detail."
        ),
    ))

    # ── 11. Title relevance to topic ──
    topic_words = set(
        w.lower()
        for w in standard_meta.get("topic", "").split()
        if len(w) > 3
    )
    title_words = set(lesson.title.lower().split())
    overlap = topic_words & title_words
    details.append(ValidationDetail(
        rule="title_relevance",
        passed=len(overlap) >= 1,
        severity="minor",
        message=(
            f"Title '{lesson.title}' shares {len(overlap)} keyword(s) with "
            f"topic '{standard_meta.get('topic', '')}': {overlap or '∅'}."
        ),
    ))

    # ── 12. No duplicate questions ──
    questions = [kc.question.strip().lower() for kc in lesson.knowledge_checks]
    has_dupes = len(questions) != len(set(questions))
    details.append(ValidationDetail(
        rule="no_duplicate_questions",
        passed=not has_dupes,
        severity="major",
        message=(
            "Duplicate knowledge-check questions detected."
            if has_dupes
            else "All knowledge-check questions are unique."
        ),
    ))

    # ── Compute score ──
    score = 100.0
    has_critical_fail = False
    rules_passed = 0

    for d in details:
        if d.passed:
            rules_passed += 1
        else:
            if d.severity == "critical":
                has_critical_fail = True
            else:
                score -= SEVERITY_PENALTY.get(d.severity, 5)

    if has_critical_fail:
        score = 0.0

    score = max(0.0, min(100.0, score))

    return QualityReport(
        total_score=round(score, 1),
        grade=_grade_from_score(score),
        rules_passed=rules_passed,
        rules_total=len(details),
        details=details,
    )


# ── Main validator entry point ────────────────────────────────────────────


async def run_validator(state: dict) -> dict:
    """Validate ``state['raw_json']`` against schema + 12 quality rules.

    Sets ``state['validation_passed']``, ``state['quality_report']``,
    and on failure ``state['validation_errors']``.
    """

    logger.info("▶  Validator Agent – started")
    start = time.perf_counter()

    # ── Parse JSON ──
    try:
        parsed = json.loads(state["raw_json"])
    except json.JSONDecodeError as exc:
        elapsed = round(time.perf_counter() - start, 3)
        state["validation_passed"] = False
        state["validation_errors"] = f"JSON parse error: {exc}"
        state["steps"].append(StepTrace(
            step_name="Validator Agent",
            status="failed",
            duration_seconds=elapsed,
            error=state["validation_errors"],
        ))
        logger.error("✗  Validator Agent – JSON parse error: %s", exc)
        return state

    # ── Pydantic schema validation ──
    try:
        lesson = LessonContent.model_validate(parsed)
    except ValidationError as exc:
        elapsed = round(time.perf_counter() - start, 3)
        state["validation_passed"] = False
        state["validation_errors"] = str(exc)
        state["steps"].append(StepTrace(
            step_name="Validator Agent",
            status="failed",
            duration_seconds=elapsed,
            error=state["validation_errors"],
        ))
        logger.error("✗  Validator Agent – Pydantic validation failed")
        return state

    # ── Business-rule quality scoring ──
    report = _run_quality_rules(
        lesson=lesson,
        standard_meta=state.get("standard_meta", {}),
        five_e_config=state.get("five_e_config", {}),
    )
    state["quality_report"] = report

    elapsed = round(time.perf_counter() - start, 3)

    # Pass if score ≥ 60 (grade C or above) and no critical failures
    if report.total_score >= 60:
        state["validation_passed"] = True
        state["lesson_content"] = lesson
        state["steps"].append(StepTrace(
            step_name="Validator Agent",
            status="success",
            duration_seconds=elapsed,
            output_snippet=(
                f"Quality score: {report.total_score}/100 ({report.grade}) — "
                f"{report.rules_passed}/{report.rules_total} rules passed ✓"
            ),
        ))
        logger.info(
            "✓  Validator Agent – %ss  Score: %s/100 (%s)",
            elapsed, report.total_score, report.grade
        )
    else:
        failed_rules = [
            d for d in report.details if not d.passed
        ]
        error_summary = "; ".join(
            f"[{d.severity.upper()}] {d.rule}: {d.message}"
            for d in failed_rules
        )
        state["validation_passed"] = False
        state["validation_errors"] = (
            f"Quality score {report.total_score}/100 ({report.grade}) "
            f"is below threshold (60). Failures: {error_summary}"
        )
        state["steps"].append(StepTrace(
            step_name="Validator Agent",
            status="failed",
            duration_seconds=elapsed,
            error=state["validation_errors"],
        ))
        logger.error(
            "✗  Validator Agent – %ss  Score: %s/100 (%s) – BELOW THRESHOLD",
            elapsed, report.total_score, report.grade
        )

    return state
