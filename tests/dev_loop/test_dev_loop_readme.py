# generated from brief/15 · part 15 owns this file
"""Tests for the publish-ready repository (brief part 15 §14).

Offline: `tools/make_readme` is exercised against fixture trees and the
real repo with local reads only. No model calls, no network, no money.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent

VIDEO_SUFFIXES = {
    ".mp4", ".mov", ".mpg", ".mpeg", ".avi", ".mkv", ".webm", ".m4v",
}


def _load_make_readme():
    name = "make_readme_under_test"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    loader = importlib.machinery.SourceFileLoader(
        name, str(REPO / "tools" / "make_readme")
    )
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def readme():
    return _load_make_readme()


@pytest.fixture
def mini_repo(tmp_path):
    """A tiny repo with two parts, two briefs and three costed runs."""
    (tmp_path / "tools").mkdir()
    (tmp_path / "brief").mkdir()
    (tmp_path / "brief" / "03-fake.md").write_text(
        "# 03 — Fake Clips\n", encoding="utf-8"
    )
    (tmp_path / "brief" / "04-fake.md").write_text(
        "# 04 — Fake Architecture\n", encoding="utf-8"
    )
    parts = {
        "03": {"spec": "brief/03-fake.md"},
        "04": {"spec": "brief/04-fake.md"},
    }
    (tmp_path / "tools" / "parts.json").write_text(
        json.dumps({"parts": parts}), encoding="utf-8"
    )
    (tmp_path / "ITERATIONS.md").write_text(
        "2026-10-27 | part 03 | x | generated after 1 attempt(s) "
        "| cost $0.0200 over 1 attempt ($0.0200) (m: in 1 cached 0 out 1) "
        "| tests pass | acceptance not-run | pages not-run\n"
        "2026-10-27 | part 04 | x | generated after 1 attempt(s) "
        "| cost $0.0100 over 1 attempt ($0.0100) (m: in 1 cached 0 out 1) "
        "| tests pass | acceptance not-run | pages not-run\n"
        "2026-10-28 | part 03 | x | generated after 2 attempt(s) "
        "| cost $0.0500 over 2 attempts ($0.0200 + $0.0300) "
        "(m: in 2 cached 0 out 2) | tests pass | acceptance not-run "
        "| pages not-run\n",
        encoding="utf-8",
    )
    return tmp_path


def test_parts_table_lists_every_part_and_total_sums(readme, mini_repo):
    text = readme.build_readme(mini_repo)
    assert "| 03 | Fake Clips | $0.0500 |" in text
    assert "| 04 | Fake Architecture | $0.0100 |" in text
    assert "| Total | 2 parts | $0.0600 |" in text
    assert "All generations so far: $0.0800 across 3 recorded runs." in text


def test_last_line_without_cost_keeps_earlier_cost(readme, mini_repo):
    with (mini_repo / "ITERATIONS.md").open("a", encoding="utf-8") as handle:
        handle.write(
            "2026-10-28 | part 04 | REFUSED hand-edited generated file: x "
            "| tests not-run | acceptance not-run | pages not-run\n"
        )
    text = readme.build_readme(mini_repo)
    assert "| 04 | Fake Architecture | $0.0100 |" in text


def test_results_clip_appears_with_its_cost(readme, tmp_path):
    clip = tmp_path / "results" / "clip-x"
    clip.mkdir(parents=True)
    (clip / "result.json").write_text(
        json.dumps({
            "verdict": {
                "kind": "world", "world": "Moon",
                "g_measured": 1.7, "sigma_g": 0.2,
            },
            "sentence": "The measured g of 1.70 +/- 0.20 m/s2 fits Moon.",
        }),
        encoding="utf-8",
    )
    (clip / "summary.json").write_text(
        json.dumps({
            "cost_usd": {"total": 0.1234},
            "turns": 25,
            "wall_time_s": 420.0,
        }),
        encoding="utf-8",
    )
    (clip / "source.txt").write_text(
        "Clip X | https://example.com/x | Example footage, linked only\n",
        encoding="utf-8",
    )
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "parts.json").write_text(
        json.dumps({"parts": {}}), encoding="utf-8"
    )
    (tmp_path / "ITERATIONS.md").write_text("", encoding="utf-8")
    text = readme.build_readme(tmp_path)
    assert "Clip X" in text
    assert "$0.1234" in text
    assert "25" in text
    assert "7.0 min" in text
    assert "1.70 ± 0.20 m/s²" in text
    assert "[source](https://example.com/x)" in text


def test_make_readme_twice_is_byte_identical(readme):
    first = readme.build_readme(REPO)
    second = readme.build_readme(REPO)
    assert first.encode("utf-8") == second.encode("utf-8")


def test_readme_matches_make_readme_output(readme):
    fresh = readme.build_readme(REPO)
    assert (REPO / "README.md").read_text(encoding="utf-8") == fresh


def test_every_part_has_a_cost_row(readme):
    parts = json.loads(
        (REPO / "tools" / "parts.json").read_text(encoding="utf-8")
    )["parts"]
    text = readme.build_readme(REPO)
    for number in sorted(parts, key=int):
        title = readme.part_title(REPO / parts[number]["spec"])
        assert f"| {number} | {title} | $" in text
    rows_total = sum(
        readme.last_cost_per_part(
            readme.iteration_costs(
                (REPO / "ITERATIONS.md").read_text(encoding="utf-8")
            )
        ).values()
    )
    assert f"| Total | {len(parts)} parts | ${rows_total:.4f} |" in text


def test_every_results_clip_appears_with_its_cost(readme):
    text = readme.build_readme(REPO)
    for clip_dir in sorted((REPO / "results").iterdir()):
        if not clip_dir.is_dir():
            continue
        summary = json.loads(
            (clip_dir / "summary.json").read_text(encoding="utf-8")
        )
        total = float(summary["cost_usd"]["total"])
        assert f"${total:.4f}" in text


def test_results_has_no_video_files():
    found = [
        path.as_posix()
        for path in (REPO / "results").rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    ]
    assert found == []


def test_readme_sections_in_order_and_within_line_cap():
    lines = (REPO / "README.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 160
    headings = [
        "## 1. What it is",
        "## 2. How it was built",
        "## 3. Run one video",
        "## 4. Regenerate the code",
        "## 5. Results",
        "## 6. Meta tools used",
        "## 7. Clips and rights",
        "## 8. License",
    ]
    positions = [lines.index(heading) for heading in headings]
    assert positions == sorted(positions)


def test_readme_states_run_and_regenerate_commands():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert "uv run python -m src.cli <video> --runs-dir runs" in text
    assert "META_API_KEY" in text
    assert "src.pagebuild.build_page" in text
    assert "tools/dev_loop --part NN" in text
    assert "tools/parts.json" in text
    assert "all generations so far" in text.lower()


def test_readme_names_three_verdict_states():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    section = text.split("## 2. How it was built")[0]
    lowered = section.lower()
    assert "native speed" in lowered
    assert "retiming" in lowered
    assert "undetermined" in lowered


def test_license_is_mit():
    text = (REPO / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "Copyright (c) 2026 Andrey Yunoshev" in text


def test_gitignore_covers_runs_devloop_venv():
    names = {
        line.strip().rstrip("/")
        for line in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    assert {"runs", ".dev_loop", ".venv"} <= names


def test_source_txt_is_one_piped_line():
    for clip_dir in sorted((REPO / "results").iterdir()):
        if not clip_dir.is_dir():
            continue
        raw = (clip_dir / "source.txt").read_text(encoding="utf-8")
        assert raw.strip().count("\n") == 0
        fields = [field.strip() for field in raw.strip().split("|")]
        assert len(fields) == 3
        assert all(fields)
        assert fields[1].startswith("http")


def _write_fixture_clip(root, dirname, title, verdict, slug="clipslug"):
    clip = root / "results" / dirname
    clip.mkdir(parents=True)
    (clip / "result.json").write_text(
        json.dumps({
            "verdict": verdict,
            "sentence": f"{title} sentence.",
        }),
        encoding="utf-8",
    )
    (clip / "summary.json").write_text(
        json.dumps({
            "cost_usd": {"total": 0.25},
            "turns": 10,
            "wall_time_s": 600.0,
        }),
        encoding="utf-8",
    )
    (clip / "source.txt").write_text(
        f"{title} | https://example.com/{dirname} | Example footage\n",
        encoding="utf-8",
    )
    (clip / "page.txt").write_text(f"{slug}\n", encoding="utf-8")
    return clip


@pytest.fixture
def costed_repo(tmp_path):
    """A repo tree with costs.json, one clip and one ITERATIONS.md line."""
    (tmp_path / "tools").mkdir()
    (tmp_path / "brief").mkdir()
    (tmp_path / "brief" / "03-fake.md").write_text(
        "# 03 — Fake Clips\n", encoding="utf-8"
    )
    (tmp_path / "tools" / "parts.json").write_text(
        json.dumps({"parts": {"03": {"spec": "brief/03-fake.md"}}}),
        encoding="utf-8",
    )
    (tmp_path / "ITERATIONS.md").write_text(
        "2026-11-03 | part 03 | x | generated after 1 attempt(s) "
        "| cost $0.0200 over 1 attempt ($0.0200) (m: in 1 cached 0 out 1) "
        "| tests pass | acceptance not-run | pages not-run\n",
        encoding="utf-8",
    )
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "costs.json").write_text(
        json.dumps({
            "runs": 53,
            "dates": "1–3 November 2026",
            "spark_usd": 0.24,
            "sam_usd": 0.11,
            "search_usd": 0.01,
            "total_usd": 0.36,
        }),
        encoding="utf-8",
    )
    _write_fixture_clip(
        tmp_path, "moon", "Moon Hop",
        {"kind": "world", "world": "Moon",
         "g_measured": 1.65, "sigma_g": 0.10},
        slug="moon",
    )
    return tmp_path


def test_readme_top_starts_with_title_tagline_live_and_blocks(
    readme, costed_repo
):
    text = readme.build_readme(costed_repo)
    lines = text.splitlines()
    assert lines[0] == "# Physics Proof"
    tagline = lines.index(
        "**Drop in any video; it asks what is worth proving, measures it, "
        "and shows every step on the footage.**"
    )
    live = next(
        i for i, line in enumerate(lines) if line.startswith("Live: ")
    )
    assert "https://yunoshev.github.io/physics-proof/" in lines[live]
    assert "Play" in lines[live]
    see = next(
        i for i, line in enumerate(lines) if line.startswith("See it work: ")
    )
    one_system = next(
        i for i, line in enumerate(lines)
        if line.startswith("**One system for any clip")
    )
    rebuilt = next(
        i for i, line in enumerate(lines)
        if line.startswith("**Rebuilt from text")
    )
    section1 = lines.index("## 1. What it is")
    assert tagline < live < see < one_system < rebuilt < section1
    assert lines[one_system] == "**One system for any clip — $0.36 per clip**"
    assert "$0.0200" in lines[rebuilt]
    assert any(
        "**$0.0200**" in line and "full rebuild" in line for line in lines
    )


def test_readme_top_cost_figures_match_sources(readme, costed_repo):
    text = readme.build_readme(costed_repo)
    assert (
        "Average cost per clip: **$0.36** = Muse Spark $0.24 + SAM 3.1 $0.11 "
        "+ web search $0.01 (average of 53 live runs, 1–3 November 2026)."
    ) in text


def test_readme_top_without_costs_file_omits_average_line(readme, tmp_path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "parts.json").write_text(
        json.dumps({"parts": {}}), encoding="utf-8"
    )
    (tmp_path / "ITERATIONS.md").write_text("", encoding="utf-8")
    text = readme.build_readme(tmp_path)
    assert "**One system for any clip — … per clip**" in text
    assert "Average cost per clip" not in text
    assert "See it work:" not in text
    assert "Demo video:" not in text


def test_readme_top_demo_line_only_with_demo_txt(readme, costed_repo):
    assert "Demo video:" not in readme.build_readme(costed_repo)
    (costed_repo / "results" / "demo.txt").write_text(
        "https://example.com/demo\n", encoding="utf-8"
    )
    text = readme.build_readme(costed_repo)
    demo = next(
        i for i, line in enumerate(text.splitlines())
        if line.startswith("Demo video: ")
    )
    assert "[watch](https://example.com/demo)" in text.splitlines()[demo]
    section1 = text.splitlines().index("## 1. What it is")
    assert demo < section1


def test_readme_limits_line_after_one_system_block(readme, costed_repo):
    paragraph = (
        "On a handheld street-jump clip, four runs ended "
        "without a correct verdict."
    )
    (costed_repo / "results" / "limits.md").write_text(
        paragraph + "\n", encoding="utf-8"
    )
    lines = readme.build_readme(costed_repo).splitlines()
    one_system = next(
        i for i, line in enumerate(lines)
        if line.startswith("**One system for any clip")
    )
    rebuilt = next(
        i for i, line in enumerate(lines)
        if line.startswith("**Rebuilt from text")
    )
    limits = next(
        i for i, line in enumerate(lines)
        if line.startswith("**Limits.** ")
    )
    assert lines[limits] == f"**Limits.** {paragraph}"
    assert one_system < limits < rebuilt


def test_readme_no_limits_line_without_file(readme, costed_repo):
    assert not (costed_repo / "results" / "limits.md").exists()
    text = readme.build_readme(costed_repo)
    assert "**Limits.** " not in text
    assert "Limits." not in text


def test_readme_see_it_work_links_use_page_slugs(readme, costed_repo):
    _write_fixture_clip(
        costed_repo, "fast", "Fast Hop",
        {"kind": "retimed", "world": "Moon", "direction": "sped",
         "factor": 2.43, "g_measured": 9.58, "sigma_g": 0.65},
        slug="fast",
    )
    text = readme.build_readme(costed_repo)
    see = next(
        line for line in text.splitlines()
        if line.startswith("See it work: ")
    )
    assert (
        "[Moon Hop — Moon, g = 1.65 ± 0.10 m/s²]"
        "(https://yunoshev.github.io/physics-proof/moon/)" in see
    )
    assert (
        "[Fast Hop — retimed ×2.43, g = 9.58 ± 0.65 m/s²]"
        "(https://yunoshev.github.io/physics-proof/fast/)" in see
    )


def test_readme_sections_two_and_six_name_wonder(readme):
    text = readme.build_readme(REPO)
    section2 = text.split("## 2. How it was built")[1].split("## 3.")[0]
    flat2 = section2.replace("\n", " ")
    assert "Muse Wonder" in flat2
    assert "turned into briefs by Muse Wonder" in flat2
    section6 = text.split("## 6. Meta tools used")[1].split("## 7.")[0]
    flat6 = section6.replace("\n", " ")
    assert (
        "Muse Wonder (wrote the briefs from the owner's requests)" in flat6
    )


def test_verdict_short_covers_kinds(readme):
    assert readme.verdict_short(
        {"verdict": {"kind": "world", "world": "Moon",
                     "g_measured": 1.65, "sigma_g": 0.10}}
    ) == "Moon, g = 1.65 ± 0.10 m/s²"
    assert readme.verdict_short(
        {"verdict": {"kind": "retimed", "factor": 2.43,
                     "g_measured": 9.58, "sigma_g": 0.65}}
    ) == "retimed ×2.43, g = 9.58 ± 0.65 m/s²"
    assert readme.verdict_short(
        {"verdict": {"kind": "impossible"}}
    ) == "physically impossible"
    assert readme.verdict_short(
        {"verdict": {"kind": "undetermined", "reason": "budget ran out"}}
    ) == "undetermined (budget ran out)"
