# generated from brief/11 · part 11 owns this file
"""The real-run fixture (brief §§9.4, 11, 16.4)."""

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FIX = REPO / "fixtures" / "run-7"
SUFFIXES = (".png", ".jpg", ".jpeg", ".npz", ".json", ".jsonl",
            ".mp4")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _digest(root):
    out = {}
    root = Path(root)
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    return out


def _file_strings(node, found):
    if isinstance(node, dict):
        for value in node.values():
            _file_strings(value, found)
    elif isinstance(node, list):
        for value in node:
            _file_strings(value, found)
    elif (isinstance(node, str) and "://" not in node
            and node.lower().endswith(SUFFIXES)):
        found.append(node)


def test_fixture_rebuilds_identically(tmp_path):
    # Brief §22: the test builds into tmp_path and compares that build
    # file by file with the committed fixtures/run-7/. It never writes
    # under fixtures/.
    from src.validate.fixture import build_fixture

    before = _digest(FIX)
    out = build_fixture(tmp_path / "run-7")
    rebuilt = _digest(out)
    assert set(rebuilt) == set(before), (
        sorted(set(rebuilt) ^ set(before)))
    assert rebuilt == before
    # The committed fixture is untouched by the test build.
    assert _digest(FIX) == before


def test_fixture_verdict_and_numbers():
    from src.contract import validate_result, validate_summary

    result = _load(FIX / "result.json")
    assert validate_result(result) == []
    assert validate_summary(_load(FIX / "summary.json")) == []
    verdict = result["verdict"]
    assert verdict["kind"] == "undetermined"
    assert "cannot separate" in verdict["reason"]
    assert verdict["world"] is None
    fit = result["segments"][0]["fit"]
    assert abs(fit["g_app"] - 1.177) < 0.02
    assert fit["sigma_g"] > 0


def test_fixture_matches_part12_section16():
    result = _load(FIX / "result.json")
    duration = result["video"]["duration_s"]
    assert duration > 0
    for segment in result["segments"]:
        for row in segment["track"]:
            assert 0 <= row["t_s"] <= duration
        assert segment["track"][0]["t_s"] == \
            segment["times_s"]["start"]
        takeoff = [r for r in segment["track"]
                   if r["frame"] == segment["frames"]["start"]]
        assert takeoff and takeoff[0]["y_m"] == 0.0
        assert segment["apex_info"]["rise_m"] < 1.0
        assert segment["times_s"]["start"] <= \
            segment["times_s"]["apex"] <= segment["times_s"]["end"]


def test_fixture_copy_is_closed():
    for path in sorted(FIX.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in (".json", ".jsonl"):
            continue
        found: list = []
        if path.suffix == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    _file_strings(json.loads(line), found)
        else:
            _file_strings(
                json.loads(path.read_text(encoding="utf-8")), found)
        missing = [p for p in found if not (FIX / p).exists()]
        assert missing == [], (path, missing)
