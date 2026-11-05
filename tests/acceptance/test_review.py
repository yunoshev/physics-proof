# generated from brief/15 · part 15 owns this file
"""Offline tests for the page rebuild + screenshot review (brief §§5–6).

Pure helpers are tested directly; `rebuild_and_review` runs with
stubbed builder/screenshotter/vision collaborators, so no browser,
model, or network call happens. Live runs stay behind
PHYSICS_PROOF_LIVE=1 via `dev_loop --pages`.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent


def _load_review():
    name = "acceptance_review_under_test"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    loader = importlib.machinery.SourceFileLoader(
        name, str(REPO / "tests" / "acceptance" / "review.py")
    )
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def review():
    return _load_review()


RESULT = {
    "verdict": {"world": "Moon", "g_measured": 1.7, "sigma_g": 0.2},
    "calculation_steps": [{"id": "fit"}, {"id": "mask_check"}],
}


def test_review_checklist_covers_named_historical_defects(review):
    checklist = " ".join(review.REVIEW_CHECKLIST).casefold()
    for defect in (
        "black video",
        "dot-only",
        "dark-on-dark",
        "absurd decimals",
        "disagreeing with the result file",
        "desync",
        "ghost",
    ):
        assert defect in checklist


def test_event_urls_cover_first_screen_and_every_event(review):
    urls = review.event_urls("file:///pages/a/index.html", RESULT)
    labels = [label for label, _ in urls]
    assert labels[0] == "first-screen"
    assert "event-fit" in labels
    assert "event-mask_check" in labels
    assert any("frame" in label for label in labels)
    assert any("event=fit" in url for _, url in urls)


def test_vision_reply_must_parse_or_fail_review(review):
    defects, problems = review.parse_vision_defects(
        '{"defects": [{"shot": "a", "defect": "black video"}]}'
    )
    assert len(defects) == 1 and problems == []
    # An unparseable or off-shape reply is itself a failure, never a pass.
    assert review.parse_vision_defects("not json")[1]
    assert review.parse_vision_defects('{"defects": "none"}')[1]
    assert review.parse_vision_defects('{"defects": [{"shot": "a"}]}')[1]


def test_page_weight_ignores_video_but_caps_the_rest(review, tmp_path):
    (tmp_path / "index.html").write_text("x" * 100, encoding="utf-8")
    (tmp_path / "clip.mp4").write_bytes(b"0" * 10_000_000)
    assert review.check_page_weight(tmp_path) == []
    (tmp_path / "big.json").write_bytes(b"0" * 1_000_001)
    assert review.check_page_weight(tmp_path)


def test_template_hash_must_match(review, tmp_path):
    (tmp_path / "index.html").write_text("hash abc123", encoding="utf-8")
    assert review.check_template_hash(tmp_path, "abc123") == []
    assert review.check_template_hash(tmp_path, "deadbeef")
    empty = tmp_path / "empty"
    empty.mkdir()
    assert review.check_template_hash(empty, "abc123")


def _run_dir(runs_base, name="run-a"):
    run_dir = runs_base / name
    (run_dir).mkdir(parents=True)
    (run_dir / "result.json").write_text(
        json.dumps(RESULT), encoding="utf-8"
    )
    return run_dir


def _stubs(review, vision_reply='{"defects": []}'):
    def builder(run_dir, page_dir):
        page_dir = Path(page_dir)
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text("hash abc123",
                                             encoding="utf-8")

    def screenshotter(url, width, height, dest):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"shot")

    def vision_caller(shots, prompt):
        assert shots
        for item in review.REVIEW_CHECKLIST:
            assert item.split(" ")[0] in prompt or item in prompt
        return vision_reply

    return builder, screenshotter, vision_caller


def test_clean_review_asks_for_approval_never_publishes(review, tmp_path):
    runs = tmp_path / "runs"
    _run_dir(runs)
    builder, screenshotter, vision = _stubs(review)
    code, report, summary = review.rebuild_and_review(
        tmp_path, runs_dir=str(runs), out_dir=str(tmp_path / "pages"),
        builder=builder, screenshotter=screenshotter, vision_caller=vision,
    )
    assert code == 0
    assert "owner approval" in report
    assert "publish" in report.casefold()
    assert "awaiting owner approval" in summary
    assert not hasattr(review, "publish")


def test_defect_fails_build_and_names_shot(review, tmp_path):
    runs = tmp_path / "runs"
    _run_dir(runs)
    reply = json.dumps({"defects": [
        {"shot": "1440x900-event-fit", "defect": "black video",
         "detail": "nothing rendered"}
    ]})
    builder, screenshotter, vision = _stubs(review, vision_reply=reply)
    code, report, summary = review.rebuild_and_review(
        tmp_path, runs_dir=str(runs), out_dir=str(tmp_path / "pages"),
        builder=builder, screenshotter=screenshotter, vision_caller=vision,
    )
    assert code == 1
    assert "black video" in report
    assert "1440x900-event-fit" in report
    assert "FAIL" in summary


def test_no_runs_fails_without_touching_vision(review, tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    called = []

    def vision_caller(shots, prompt):
        called.append(True)
        return '{"defects": []}'

    code, _, summary = review.rebuild_and_review(
        tmp_path, runs_dir=str(runs), out_dir=str(tmp_path / "pages"),
        builder=lambda r, p: None, screenshotter=lambda *a: None,
        vision_caller=vision_caller,
    )
    assert code == 1
    assert called == []
    assert "no runs" in summary


def test_publish_requires_owner_approval_record(review):
    """Pages are published only after the owner's explicit approval; the
    review itself never publishes — it earns a *request* for approval."""
    import inspect

    source = inspect.getsource(review.rebuild_and_review).casefold()
    assert "publish" not in source or "no auto-publish" in source
    assert "approval" in source
