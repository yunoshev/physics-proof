"""The prompt states every coded rule; code is the guarantee."""

from pathlib import Path

PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "measuring_rules.md"


def _text():
    return PROMPT.read_text()


def test_prompt_states_every_coded_rule():
    text = _text()
    for code in ("R-T1", "R-T2", "R-S1", "R-S2", "R-S3", "R-S4", "R-S6",
                 "R-S6a", "R-S6b", "R-S7", "R-S8", "R-S9", "R-S10", "R-S11",
                 "R-S12", "R-S13", "R-S14", "R-S15", "R-S16", "R-S17",
                 "R-M1", "R-M2", "R-M3", "R-M4", "R-M5", "R-M6", "R-M7",
                 "R-C2", "R-C3", "R-C4", "R-W1", "R-E1", "R-E2", "R-E3",
                 "R-Q1", "R-R1", "R-R5", "R-G"):
        assert code in text, code


def test_prompt_has_no_person_dependent_rule():
    text = _text()
    for banned in ("SECOND_REFERENCE_REQUIRED_PERSON", "SUBJECT_KIND",
                   "subject.kind", "REQUIRED_PERSON"):
        assert banned not in text, banned
    low = text.lower()
    assert "when the subject is a person" not in low
    assert "if the subject is a person" not in low


def test_prompt_carries_question_first_and_one_world():
    text = _text()
    assert "the viewer's question" in text
    assert "Do not test, list, search or mention other worlds" in text


def test_prompt_carries_range_checks():
    text = _text()
    assert "the same quantity of the same kind of thing" in text
    assert "Prefer ratios" in text


def test_prompt_carries_size_as_quoted_rules():
    text = _text()
    assert "within 5 % of the median" in text
    for token in ("mode: single", "mode: sum", "mode: mean"):
        assert token in text, token


def test_prompt_carries_trajectory_decision_rules():
    text = _text()
    for token in ("R-M6", "R-M7", "R-S11", "R-S12"):
        assert token in text, token


def test_prompt_carries_moving_thing_and_line_check_rules():
    text = _text()
    assert "R-S16" in text and "R-S17" in text
    assert "check_line" in text


def test_prompt_has_dry_run_pushes():
    text = _text()
    for code in ("SECOND_REFERENCE_REQUIRED", "CLOCK_REQUIRED",
                 "MOTIONS_SCAN_MISSING"):
        assert code in text, code


def test_prompt_records_identification_and_phase_rules():
    text = _text()
    assert "scene_card" in text
    assert "R-M5" in text


def test_prompt_carries_one_thing_one_reference_words():
    text = _text()
    assert "R-S6b" in text
    assert "One thing is one reference" in text
    assert "A dry run without a reference on the moving thing returns a push" in text
    for word in ("measured", "not_a_flight", "not_measurable"):
        assert word in text, word
    assert "not_measured" not in text
    assert "When the reference's own mask is present on frames within 2 s " \
        "before the first-check takeoff, it is measured there." in text
    assert "along the reference's own line, not only as height" in text
