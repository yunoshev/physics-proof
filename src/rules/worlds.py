"""R-Q1 (viewer's question) and R-W1 (one world)."""

from __future__ import annotations

PHYSICS_WORDS = ("gravity", "parabola", "acceleration", " m/s", "m/s²")


def check_rq1_question(*, question: str | None, summary: str | None = None):
    """R-Q1: the clip's own viewer question comes before measuring."""
    if not question:
        return ("QUESTION_MISSING", "first_look.question",
                "write first_look.question as the viewer's question in "
                "plain words")
    low = question.lower()
    if any(w in low for w in ("gravity", "parabola", "acceleration")):
        return ("QUESTION_PHYSICS_WORDING", "first_look.question",
                "not physics vocabulary ('does the ascent match Earth "
                "gravity'); ask what a viewer would doubt")
    if summary is None or not summary.strip():
        return ("QUESTION_SUMMARY_MISSING", "first_look.summary",
                "first_look.summary says what happens and which "
                "measurement answers the question")
    return None


def check_rw1_candidate_worlds(*, candidates, excluded, verdict_world=None):
    """R-W1: one scene world; fits only over candidates; no other-world verdict."""
    if verdict_world is not None and verdict_world not in (candidates or []):
        return ("WORLD_NOT_FROM_SCENE", "worlds",
                f"verdict names '{verdict_world}', not a candidate world; "
                "fits are computed only over candidate worlds")
    return None
