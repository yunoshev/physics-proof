"""M8. Agent loop: Spark watches the clip and drives the tools to analysis.json.

Message 0 is the system prompt in ``config/prompts/agent_system.md`` plus
parts assembled at run time (evidence rules verbatim from SPEC.md section 4,
the tools and their budgets, the ``blocks`` API from docstrings, the schema
description, and the measured probe of the clip). The clip itself travels as
the first user message, anonymised to ``workspace/clip.mp4``.

Each turn Spark makes exactly one tool call (native tool calling through
``MetaClient.respond`` with ``tool_choice`` auto). The full conversation is
kept as an input list (never ``previous_response_id``) with old tool images
pruned; one ``Budget`` object guards every billable call, including the
sub-calls tools make. ``finish`` validates, checks the mask-check gate,
recomputes the verdicts, and writes ``run_dir/analysis.json``.
"""

from __future__ import annotations

import inspect
import json
import math
import shutil
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import blocks, video
from .blocks import load_masks
from .config import REPO_ROOT, Settings
from .ledger import Ledger
from .mask_check import MaskCheck
from .meta_client import MetaClient
from .sam_tool import SamTool
from .sandbox import SandboxResult, run_python
from .schema import combine, schema_doc, validate
from .search_tool import SearchTool
from .toolbox import Toolbox

#: Code runner for the ``python`` tool: the sandbox by default, swappable in tests.
#: Plain runners take (code, workspace); runners with tool support also
#: accept an ``extra_imports`` keyword of registered tool names.
PythonRunner = Callable[..., SandboxResult]


def _call_runner(
    runner: PythonRunner, code: str, workspace: Path, extra: Collection[str]
) -> SandboxResult:
    """Run code, passing extra_imports only when tools are registered.

    Plain two-argument runners never see the keyword; runs without tools
    call them exactly as before.
    """
    names = tuple(sorted(set(extra)))
    if names:
        return runner(code, workspace, extra_imports=names)
    return runner(code, workspace)

__all__ = [
    "BUDGET_STATUS",
    "OK_STATUS",
    "RunSummary",
    "TOOLS",
    "assemble_system_prompt",
    "clip_probe_text",
    "run_analysis",
]

#: Terminal status of a finished run.
OK_STATUS = "ok"
#: Terminal status when any budget runs out first.
BUDGET_STATUS = "undetermined: budget"

#: Tier name to Spark model.
TIER_MODELS = {
    "contributor": "muse-spark-1.3-contributor",
    "standard": "muse-spark-1.3",
}

#: Long tool texts are cut for the conversation (turn files keep the full text).
TEXT_TRUNC = 4000
#: Only the last two tool results keep their images in context.
IMAGE_MSGS_KEPT = 2

#: Words that must never appear in the assembled prompt (SPEC principle 7).
FORBIDDEN_WORDS = (
    "apollo",
    "lunar module",
    "singapore",
    "red bull",
    "marina bay",
    "tiktok",
    "salute",
    "stunt",
)

SYSTEM_PROMPT_PATH = REPO_ROOT / "config" / "prompts" / "agent_system.md"


def _tool(
    name: str, description: str, properties: dict[str, Any]
) -> dict[str, Any]:
    """One strict native-tool definition for the Responses API."""
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": sorted(properties),
            "additionalProperties": False,
        },
        "strict": True,
    }


_INT_ARRAY = {"type": "array", "items": {"type": "integer"}}

TOOLS: list[dict[str, Any]] = [
    _tool("video_info", "Measured facts about the clip: size, frame rate, frame count, duplicates.", {}),
    _tool(
        "frames",
        "A labelled contact sheet of up to 24 frames (crop in original pixels, empty for none).",
        {
            "frames": {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 24},
            "crop": {"type": "array", "items": {"type": "integer"}, "minItems": 0, "maxItems": 4},
            "label": {"type": "string"},
        },
    ),
    _tool(
        "sam",
        "Segment one short noun phrase over frames start..stop-1; returns per-object stats and an overlay sheet.",
        {
            "phrase": {"type": "string"},
            "start": {"type": "integer"},
            "stop": {"type": "integer"},
        },
    ),
    _tool(
        "mask_check",
        "Ask an independent checker what a mask really covers (file in the workspace, integer object id, 1-4 frames, claim sentence).",
        {
            "file": {"type": "string"},
            "object": {"type": "integer"},
            "frames": {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": 4},
            "claim": {"type": "string"},
        },
    ),
    _tool(
        "search",
        "Look up a reference fact (sizes, constants, equipment). Event questions are refused.",
        {"query": {"type": "string"}},
    ),
    _tool(
        "python",
        "Run Python code in the workspace sandbox (import blocks available); returns stdout, stderr and new images.",
        {"code": {"type": "string"}},
    ),
    _tool(
        "make_tool",
        "Write a small measurement module plus a probe on synthetic data; registered only if the probe passes.",
        {
            "name": {"type": "string"},
            "code": {"type": "string"},
            "probe": {"type": "string"},
        },
    ),
    _tool(
        "finish",
        "Validate the analysis file from the workspace and end the run. page_texts is a JSON object string, empty for none.",
        {
            "analysis_file": {"type": "string"},
            "page_texts": {"type": "string"},
        },
    ),
]


class BudgetExhausted(RuntimeError):
    """The dollar cap was reached before a billable call. No call was made."""


@dataclass
class Budget:
    """One shared dollar cap; every billable call checks it first."""

    cap_usd: float
    spent: float = 0.0

    def check(self) -> None:
        """Raise BudgetExhausted when the cap is already reached."""
        if self.spent >= self.cap_usd:
            raise BudgetExhausted(
                "dollar cap reached: spent %.6f of %.6f" % (self.spent, self.cap_usd)
            )

    def add(self, cost: float) -> None:
        """Record the cost of one finished call."""
        self.spent += float(cost)


class GuardClient:
    """Wrap a Spark/SAM client so one Budget guards every billable call.

    The cap is checked up front and before every retry attempt inside the
    client (passed as ``budget_check``); a retry never spends past the cap.
    """

    def __init__(self, inner: Any, budget: Budget) -> None:
        self._inner = inner
        self._budget = budget

    def respond(self, *args: Any, **kwargs: Any) -> Any:
        """Check the cap, delegate, then record the turn cost."""
        self._budget.check()
        kwargs.setdefault("budget_check", self._budget.check)
        response = self._inner.respond(*args, **kwargs)
        self._budget.add(float(getattr(response, "cost_usd", 0.0) or 0.0))
        return response

    def sam_video(self, *args: Any, **kwargs: Any) -> Any:
        """Check the cap, delegate, then record the SAM cost."""
        self._budget.check()
        kwargs.setdefault("budget_check", self._budget.check)
        result = self._inner.sam_video(*args, **kwargs)
        self._budget.add(float(getattr(result, "cost_usd", 0.0) or 0.0))
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def evidence_rules() -> str:
    """SPEC.md section 4, verbatim, for the system prompt."""
    text = (REPO_ROOT / "SPEC.md").read_text(encoding="utf-8")
    start = text.index("## 4. Rules of evidence")
    end = text.index("## 5. Acceptance")
    return text[start:end].strip()


def blocks_doc() -> str:
    """Full signature plus docstring of every public blocks function.

    Generated with inspect at run time, so the prompt cannot drift from
    the verified library; nothing here is hand-copied.
    """
    lines = []
    for name in sorted(blocks.__all__):
        func = getattr(blocks, name)
        try:
            sig = str(inspect.signature(func))
        except (TypeError, ValueError):
            sig = "(...)"
        doc = inspect.getdoc(func) or name
        lines.append("blocks." + name + sig + "\n" + doc)
    return "\n\n".join(lines)


def tools_doc(
    *,
    max_turns: int,
    sam_frames: int,
    searches: int,
    mask_checks: int,
    cap_usd: float,
    max_tools: int = 4,
    tool_attempts: int = 3,
) -> str:
    """The tools, their argument shapes, and the enforced budgets."""
    return (
        "Tools (exactly one call per turn):\n"
        "- video_info(): no arguments.\n"
        "- frames(frames, crop, label): frames holds 1..24 frame indices; "
        "crop is [] or [x1, y1, x2, y2] in original pixels; label is a note string.\n"
        "- sam(phrase, start, stop): phrase is 1..4 words; frames start..stop-1.\n"
        "- mask_check(file, object, frames, claim): file is a workspace .npz path; "
        "object is the integer object id; frames holds 1..4 frame numbers; "
        "claim is one sentence about what the mask covers.\n"
        "- search(query): one reference question per call.\n"
        "- python(code): code runs in the workspace sandbox with import blocks; "
        "write analysis files with relative paths.\n"
        "- make_tool(name, code, probe): name is a snake_case module name; "
        "code is the module source (functions with docstrings stating "
        "argument shapes and units); probe is test code that imports the "
        "module, builds synthetic data with a known answer, checks it with "
        "explicit tolerances and prints PASS. Both pass the same static "
        "review as python. The module is written to workspace/tools and "
        "registered only if the probe exits 0 and prints PASS; then later "
        "python calls can import it. A failed probe returns its output and "
        "the module stays unregistered and not importable. Re-registering a "
        "name replaces it (every version stays on disk).\n"
        "- finish(analysis_file, page_texts): analysis_file is a workspace path; "
        "page_texts is a JSON object string (or empty). finish computes "
        "flights[i].decide, verdict and overall itself from your accel/g/g_err "
        "measurements, worlds, worlds_tested (only the worlds the scene "
        "allows) and worlds_ruled_out (each ruled-out world with its visible "
        "cue) — supply only the measurements plus page_texts "
        "and notes prose, never hand-written decide/verdict/overall texts.\n"
        "Workspace layout (all tool paths are relative to the workspace): "
        "sam/ holds sam/<phrase>.<start>-<stop>.npz masks plus its overlay "
        "sheet sam/<phrase>.<start>-<stop>.png; sheets/ holds frames contact "
        "sheets; mask_checks/ holds mask-check sheets; scripts/ holds each "
        "python call as scripts/NNN.py; images your code writes land next to "
        "it. Every tool result names the files it produced. There is no shell "
        "and no os/glob: use pathlib (for example sorted(Path('.').rglob('*'))) "
        "in python to list the workspace.\n"
        "Budgets enforced in code: at most "
        + str(max_turns) + " turns, "
        + str(sam_frames) + " SAM frames, "
        + str(searches) + " searches, "
        + str(mask_checks) + " mask checks, $"
        + ("%.2f" % cap_usd) + " total, "
        + str(max_tools) + " registered tools, "
        + str(tool_attempts) + " attempts per tool name. "
        "When a budget note warns a limit is near, call finish with what you have."
    )


def clip_probe_text(info: Any, dup_runs: list[tuple[int, int]]) -> str:
    """One blind paragraph about the clip: measurements only, no names."""
    if dup_runs:
        dup_note = "duplicate runs (a, b) at " + repr(dup_runs)
    else:
        dup_note = "no duplicate frames"
    return (
        "The clip: " + str(info.width) + "x" + str(info.height) + " px, "
        "fps " + str(info.fps.numerator) + "/" + str(info.fps.denominator)
        + " (" + ("%.3f" % float(info.fps)) + "), "
        + str(info.frame_count) + " frames, "
        + ("%.3f" % info.duration) + " s, codec " + str(info.codec) + ". "
        + dup_note + "."
    )


def assemble_system_prompt(
    *,
    max_turns: int,
    sam_frames: int,
    searches: int,
    mask_checks: int,
    cap_usd: float,
    probe_text: str,
    max_tools: int = 4,
    tool_attempts: int = 3,
) -> str:
    """Build message 0: the prompt file plus generated parts, then the probe."""
    base = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    parts = [
        base,
        "## Rules of evidence (from the project spec, binding)",
        evidence_rules(),
        "## " + tools_doc(
            max_turns=max_turns,
            sam_frames=sam_frames,
            searches=searches,
            mask_checks=mask_checks,
            cap_usd=cap_usd,
            max_tools=max_tools,
            tool_attempts=tool_attempts,
        ),
        "## Verified blocks (generated from docstrings)",
        blocks_doc(),
        "## Analysis schema",
        schema_doc(),
        "## The clip",
        probe_text,
    ]
    return "\n\n".join(parts)


@dataclass
class RunSummary:
    """The outcome of one agent run, mirrored to summary.json."""

    status: str
    turns: int = 0
    sam_calls: int = 0
    sam_frames: int = 0
    searches: int = 0
    mask_checks: int = 0
    tools_made: int = 0
    cost_usd: float = 0.0
    wall_s: float = 0.0
    analysis_path: Path | None = None
    tier: str = "contributor"
    model: str = ""
    effort: str = "high"

    def to_json(self) -> dict[str, Any]:
        """Plain-JSON form for summary.json."""
        return {
            "status": self.status,
            "turns": self.turns,
            "sam_calls": self.sam_calls,
            "sam_frames": self.sam_frames,
            "searches": self.searches,
            "mask_checks": self.mask_checks,
            "tools_made": self.tools_made,
            "cost_usd": self.cost_usd,
            "wall_s": self.wall_s,
            "analysis_path": str(self.analysis_path) if self.analysis_path else None,
            "tier": self.tier,
            "model": self.model,
            "effort": self.effort,
        }


def _compact_text(text: str) -> str:
    """Cap a tool text for the conversation; turn files keep the full text."""
    if len(text) <= TEXT_TRUNC:
        return text
    rest = len(text) - TEXT_TRUNC
    return text[:TEXT_TRUNC] + "\n[... truncated " + str(rest) + " more characters]"


def _prune(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy messages with old tool images replaced by a one-line note."""
    image_idx = [
        i
        for i, item in enumerate(messages)
        if isinstance(item, dict)
        and item.get("role") == "user"
        and isinstance(item.get("content"), list)
        and any(
            isinstance(part, dict) and part.get("type") == "input_image"
            for part in item["content"]
        )
    ]
    drop = set(image_idx[:-IMAGE_MSGS_KEPT]) if len(image_idx) > IMAGE_MSGS_KEPT else set()
    out: list[dict[str, Any]] = []
    for i, item in enumerate(messages):
        if i in drop:
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "[earlier tool image omitted to save context]",
                        }
                    ],
                }
            )
            continue
        if isinstance(item, dict) and isinstance(item.get("content"), list):
            copied = dict(item)
            content: list[Any] = []
            for part in item["content"]:
                if isinstance(part, dict) and part.get("type") == "input_text":
                    text = str(part.get("text", ""))
                    if len(text) > TEXT_TRUNC:
                        part = dict(part, text=_compact_text(text))
                content.append(part)
            copied["content"] = content
            out.append(copied)
        else:
            out.append(item)
    return out


@dataclass
class _Tools:
    """The bound tool entry points for one run."""

    sam: SamTool
    search: SearchTool
    mask: MaskCheck
    workspace: Path
    clip: Path
    client: Any
    python_runner: PythonRunner
    toolbox: Toolbox


def _run_video_info(tools: _Tools) -> tuple[str, list[Path]]:
    """Measured probe facts plus duplicate runs, no cost."""
    info = video.probe(tools.clip)
    diffs = video.frame_diffs(tools.clip)
    runs = video.duplicate_runs(diffs)
    return clip_probe_text(info, runs), []


def _run_frames(tools: _Tools, args: dict[str, Any], turn: int) -> tuple[str, list[Path]]:
    """Build a contact sheet of up to 24 frames in the workspace."""
    info = video.probe(tools.clip)
    wanted = args.get("frames")
    if not isinstance(wanted, list) or not 1 <= len(wanted) <= 24:
        raise ValueError("frames needs 1..24 frame indices, got " + repr(wanted))
    indices: list[int] = []
    for value in wanted:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("frames indices must be ints, got " + repr(value))
        if not 0 <= value < info.frame_count:
            raise ValueError(
                "frame " + str(value) + " is outside 0.." + str(info.frame_count - 1)
            )
        indices.append(value)
    crop_raw = args.get("crop", [])
    crop: tuple[int, int, int, int] | None = None
    if crop_raw:
        if (
            not isinstance(crop_raw, list)
            or len(crop_raw) != 4
            or any(isinstance(v, bool) or not isinstance(v, int) for v in crop_raw)
        ):
            raise ValueError("crop must be [] or [x1, y1, x2, y2], got " + repr(crop_raw))
        crop = (crop_raw[0], crop_raw[1], crop_raw[2], crop_raw[3])
    label = args.get("label", "")
    if not isinstance(label, str):
        raise ValueError("label must be a string, got " + repr(label))
    out = tools.workspace / "sheets" / ("turn%02d.png" % turn)
    video.contact_sheet(tools.clip, sorted(set(indices)), out=out, crop=crop)
    rel = out.relative_to(tools.workspace).as_posix()
    text = "contact sheet of frames " + repr(sorted(set(indices))) + " at " + rel
    if crop is not None:
        text += " with crop " + repr(list(crop))
    if label.strip():
        text += " (" + " ".join(label.split()) + ")"
    text += "."
    return text, [out]


def _run_sam(tools: _Tools, args: dict[str, Any]) -> tuple[str, list[Path]]:
    """Segment a phrase over frames; SAM errors come back as readable text."""
    phrase = args.get("phrase")
    start = args.get("start")
    stop = args.get("stop")
    if not isinstance(phrase, str):
        raise ValueError("sam phrase must be a string, got " + repr(phrase))
    result = tools.sam.run(phrase, start, stop)
    npz_rel = result.npz.relative_to(tools.workspace).as_posix()
    sheet_rel = result.sheet.relative_to(tools.workspace).as_posix()
    return result.text() + "\nfiles: " + npz_rel + ", " + sheet_rel, [result.sheet]


def _run_mask_check(tools: _Tools, args: dict[str, Any]) -> tuple[str, list[Path]]:
    """Check one mask claim with the context-free checker."""
    claimed = args.get("file")
    if not isinstance(claimed, str) or not claimed.strip():
        raise ValueError("mask_check file must be a workspace path, got " + repr(claimed))
    npz = tools.workspace / claimed.strip()
    result = tools.mask.run(npz, args.get("object"), args.get("frames"), args.get("claim"))
    sheet_rel = result.sheet.relative_to(tools.workspace).as_posix()
    npz_rel = npz.relative_to(tools.workspace).as_posix()
    return result.text() + " [mask file " + npz_rel + ", sheet " + sheet_rel + "]", [result.sheet]


def _run_search(tools: _Tools, args: dict[str, Any]) -> tuple[str, list[Path]]:
    """One blindness-filtered web search; refusals are readable results."""
    query = args.get("query")
    if not isinstance(query, str):
        raise ValueError("search query must be a string, got " + repr(query))
    return tools.search.run(query).text(), []


def _run_python(tools: _Tools, args: dict[str, Any]) -> tuple[str, list[Path]]:
    """Run code with the bound runner; refusals and failures are readable results."""
    code = args.get("code")
    if not isinstance(code, str):
        raise ValueError("python code must be a string, got " + repr(code))
    result = _call_runner(
        tools.python_runner, code, tools.workspace, tools.toolbox.registered_names()
    )
    if result.refused:
        lines = ["python refused:"]
        for problem in result.problems:
            lines.append("- line " + str(problem.line) + " [" + problem.rule + "] " + problem.message)
        return "\n".join(lines), []
    body = "python: exit " + str(result.exit_code) + " in " + ("%.1f" % result.seconds) + "s."
    if result.script is not None:
        try:
            body += " script: " + result.script.relative_to(tools.workspace).as_posix() + "."
        except ValueError:
            body += " script: " + result.script.name + "."
    if result.stdout.strip():
        body += "\n-- stdout --\n" + result.stdout.strip()
    if result.stderr.strip():
        body += "\n-- stderr --\n" + result.stderr.strip()
    if result.images:
        rels = []
        for path in result.images:
            try:
                rels.append(path.relative_to(tools.workspace).as_posix())
            except ValueError:
                rels.append(path.name)
        body += "\nimages: " + ", ".join(rels)
    return body, list(result.images)


def _run_make_tool(tools: _Tools, args: dict[str, Any], turn: int) -> tuple[str, list[Path]]:
    """Build and probe one tool; the attempt counts as this turn either way."""
    _, message = tools.toolbox.make_tool(
        args.get("name"), args.get("code"), args.get("probe"), turn=turn
    )
    return message, []


def _parse_page_texts(raw: Any) -> tuple[dict[str, str], str | None]:
    """Parse the finish page_texts JSON string; empty means no overrides."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return {}, None
    if not isinstance(raw, str):
        return {}, "page_texts must be a JSON object string, got " + repr(raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, "page_texts is not valid JSON: " + str(exc)
    if not isinstance(parsed, dict):
        return {}, "page_texts must be a JSON object, got " + repr(raw)[:120]
    for key, value in parsed.items():
        if not isinstance(value, str):
            return {}, "page_texts[" + str(key) + "] must be a string"
    return {str(k): str(v) for k, v in parsed.items()}, None


def _mask_log_entries(workspace: Path) -> list[dict[str, Any]]:
    """Read the mask-check log; corrupt lines are skipped."""
    log_path = workspace / "mask_checks.jsonl"
    if not log_path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            entries.append(record)
    return entries


def _reference_checked(entries: list[dict[str, Any]], mask_file: Any, obj: Any) -> bool:
    """True when the log holds a check on this reference mask.

    The mask file matches by file name; when the reference object parses
    as an int it must match the checked object id, otherwise any check on
    the same file counts.
    """
    want = Path(str(mask_file)).name
    oid: int | None = None
    if isinstance(obj, int) and not isinstance(obj, bool):
        oid = obj
    elif isinstance(obj, str):
        try:
            oid = int(obj)
        except ValueError:
            oid = None
    for entry in entries:
        if Path(str(entry.get("npz", ""))).name != want:
            continue
        if oid is None or int(entry.get("object", -1)) == oid:
            return True
    return False


def _num(value: Any) -> float | None:
    """Finite float of a real number or a numeric string, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _int_like(value: Any) -> int | None:
    """Int of an int, an integral float, or a digit string, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _coerce_analysis(analysis: dict[str, Any]) -> list[str]:
    """Fix harmless type slips in place; returns one note per fix.

    Covered slips: clip.duplicates_found as a bool or a list (a list
    counts its entries) or an int-like value; reference mask.object as
    an int; accel as a one- or two-number list (two numbers with no
    accel_err split into accel and accel_err); accel_err as a
    one-number list; scale.second as [] (null) or [object]; integral
    floats or digit strings where an int frame/count belongs. Anything
    else is left for the validator to reject with a path.
    """
    notes: list[str] = []

    def note(path: str, before: Any, after: Any) -> None:
        notes.append("coerced " + path + ": " + repr(before) + " -> " + repr(after))

    clip = analysis.get("clip")
    if isinstance(clip, dict) and "duplicates_found" in clip:
        raw = clip["duplicates_found"]
        if isinstance(raw, bool):
            clip["duplicates_found"] = int(raw)
            note("/clip/duplicates_found", raw, clip["duplicates_found"])
        elif isinstance(raw, list):
            clip["duplicates_found"] = len(raw)
            note("/clip/duplicates_found", raw, len(raw))
        elif not isinstance(raw, int):
            fixed = _int_like(raw)
            if fixed is not None and fixed >= 0:
                clip["duplicates_found"] = fixed
                note("/clip/duplicates_found", raw, fixed)

    refs = analysis.get("reference")
    if isinstance(refs, list):
        for pos, ref in enumerate(refs):
            if not isinstance(ref, dict):
                continue
            mask = ref.get("mask")
            if isinstance(mask, dict) and "object" in mask:
                raw = mask["object"]
                if isinstance(raw, bool):
                    continue
                if isinstance(raw, int):
                    mask["object"] = str(raw)
                    note("/reference/" + str(pos) + "/mask/object", raw, mask["object"])
                elif isinstance(raw, float) and raw.is_integer():
                    mask["object"] = str(int(raw))
                    note("/reference/" + str(pos) + "/mask/object", raw, mask["object"])

    flights = analysis.get("flights")
    if isinstance(flights, list):
        for pos, flight in enumerate(flights):
            if not isinstance(flight, dict):
                continue
            base = "/flights/" + str(pos)
            raw_accel = flight.get("accel")
            if isinstance(raw_accel, list):
                nums = [_num(v) for v in raw_accel]
                if len(raw_accel) == 1 and nums[0] is not None:
                    flight["accel"] = nums[0]
                    note(base + "/accel", raw_accel, nums[0])
                elif (
                    len(raw_accel) == 2
                    and all(v is not None for v in nums)
                    and _num(flight.get("accel_err")) is None
                ):
                    assert nums[0] is not None and nums[1] is not None
                    flight["accel"], flight["accel_err"] = nums[0], nums[1]
                    note(base + "/accel", raw_accel, [nums[0], nums[1]])
            raw_err = flight.get("accel_err")
            if isinstance(raw_err, list) and len(raw_err) == 1 and _num(raw_err[0]) is not None:
                fixed = _num(raw_err[0])
                assert fixed is not None
                flight["accel_err"] = fixed
                note(base + "/accel_err", raw_err, fixed)
            for key in ("start", "apex", "end"):
                if key in flight and flight[key] is not None and not isinstance(flight[key], int):
                    raw = flight[key]
                    fixed = _int_like(raw)
                    if fixed is not None:
                        flight[key] = fixed
                        note(base + "/" + key, raw, fixed)
            fit = flight.get("fit")
            if isinstance(fit, dict):
                if "n" in fit and not isinstance(fit["n"], int):
                    raw = fit["n"]
                    fixed = _int_like(raw)
                    if fixed is not None:
                        fit["n"] = fixed
                        note(base + "/fit/n", raw, fixed)
                window = fit.get("window")
                if isinstance(window, dict):
                    for key in ("first", "last"):
                        if key in window and not isinstance(window[key], int):
                            raw = window[key]
                            fixed = _int_like(raw)
                            if fixed is not None:
                                window[key] = fixed
                                note(base + "/fit/window/" + key, raw, fixed)
            ghost = flight.get("ghost")
            if isinstance(ghost, list):
                for j, point in enumerate(ghost):
                    if isinstance(point, dict) and "frame" in point and not isinstance(
                        point["frame"], int
                    ):
                        raw = point["frame"]
                        fixed = _int_like(raw)
                        if fixed is not None:
                            point["frame"] = fixed
                            note(base + "/ghost/" + str(j) + "/frame", raw, fixed)

    track = analysis.get("track")
    if isinstance(track, dict) and isinstance(track.get("points"), list):
        for j, point in enumerate(track["points"]):
            if isinstance(point, dict) and "frame" in point and not isinstance(
                point["frame"], int
            ):
                raw = point["frame"]
                fixed = _int_like(raw)
                if fixed is not None:
                    point["frame"] = fixed
                    note("/track/points/" + str(j) + "/frame", raw, fixed)

    scale = analysis.get("scale")
    if isinstance(scale, dict) and "second" in scale:
        raw = scale["second"]
        if isinstance(raw, list) and len(raw) == 0:
            scale["second"] = None
            note("/scale/second", raw, None)
        elif isinstance(raw, list) and len(raw) == 1:
            scale["second"] = raw[0]
            note("/scale/second", raw, raw[0])
    if isinstance(scale, dict) and isinstance(scale.get("second"), dict):
        raw_idx = scale["second"].get("reference_index")
        if isinstance(raw_idx, str):
            fixed_idx = _int_like(raw_idx)
            if fixed_idx is not None and fixed_idx >= 0:
                scale["second"]["reference_index"] = fixed_idx
                note("/scale/second/reference_index", raw_idx, fixed_idx)

    verdict = analysis.get("verdict")
    if isinstance(verdict, dict):
        for key in ("g", "g_err"):
            if key in verdict and isinstance(verdict[key], list) and len(verdict[key]) == 1:
                raw = verdict[key]
                fixed = _num(raw[0])
                if fixed is not None:
                    verdict[key] = fixed
                    note("/verdict/" + key, raw, fixed)
    return notes


def _k_sigma_of(stored: Any) -> float:
    """Agent's k_sigma when it is a positive number, else the default 2.0."""
    if isinstance(stored, dict):
        raw = _num(stored.get("k_sigma"))
        if raw is not None and raw > 0:
            return raw
    return 2.0


def _fill_computed(analysis: dict[str, Any]) -> None:
    """Compute and write flights[i].decide, verdict and overall in place.

    The agent supplies only measurements (accel/accel_err plus the
    hypothesis, verdict g/g_err plus worlds) and prose; the verified
    blocks.decide and combine supply every state/label/k/text. Inputs
    that are missing or unusable are left alone so the validator can
    reject them with a path.
    """
    flights = analysis.get("flights")
    if isinstance(flights, list):
        for flight in flights:
            if not isinstance(flight, dict):
                continue
            accel, accel_err = _num(flight.get("accel")), _num(flight.get("accel_err"))
            hypo = flight.get("hypothesis")
            hypo_value = _num(hypo.get("value")) if isinstance(hypo, dict) else None
            if accel is None or accel_err is None or accel_err <= 0:
                continue
            if (
                not isinstance(hypo, dict)
                or not isinstance(hypo.get("name"), str)
                or hypo_value is None
                or hypo_value <= 0
            ):
                continue
            try:
                flight["decide"] = blocks.decide(
                    accel,
                    accel_err,
                    {hypo["name"]: hypo_value},
                    k_sigma=_k_sigma_of(flight.get("decide")),
                )
            except ValueError:
                continue
    verdict = analysis.get("verdict")
    if isinstance(verdict, dict):
        g, g_err = _num(verdict.get("g")), _num(verdict.get("g_err"))
        raw_worlds = verdict.get("worlds")
        worlds: dict[str, float] | None = None
        if isinstance(raw_worlds, dict) and raw_worlds:
            worlds = {}
            for name, value in raw_worlds.items():
                fixed = _num(value)
                if not isinstance(name, str) or fixed is None or fixed <= 0:
                    worlds = None
                    break
                worlds[name] = fixed
        raw_tested = verdict.get("worlds_tested")
        if isinstance(raw_tested, list) and worlds:
            if not raw_tested or any(
                not isinstance(name, str) or name not in worlds for name in raw_tested
            ):
                worlds = None
            else:
                worlds = {name: worlds[name] for name in raw_tested}
        if g is not None and g_err is not None and g_err > 0 and worlds:
            try:
                got = blocks.decide(g, g_err, worlds, k_sigma=_k_sigma_of(verdict))
            except ValueError:
                got = None
            if got is not None:
                for key in (
                    "state", "world", "consistent", "sigmas", "nearest",
                    "k", "text", "g", "g_err", "k_sigma",
                ):
                    verdict[key] = got[key]
                verdict["worlds"] = worlds
    if isinstance(verdict, dict) and isinstance(verdict.get("state"), str):
        try:
            analysis["overall"] = combine(verdict, analysis.get("timescale"))
        except (TypeError, ValueError):
            pass


#: Two extents of one mask are not independent (SPEC section 4 rule 2).
#: Above this IoU on any shared frame the references count as one object.
SAME_OBJECT_IOU = 0.5


def _object_id(value: Any) -> int | None:
    """Int object id of a reference mask object, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _reference_masks(
    workspace: Path, mask: Any
) -> tuple[list[int], Any] | None:
    """Frame numbers plus the bool track of one reference mask, else None.

    Returns None when the mask entry is unusable (unknown file, unknown
    object id, unreadable archive) so the caller skips the comparison.
    """
    if not isinstance(mask, dict):
        return None
    claimed = mask.get("file")
    if not isinstance(claimed, str) or not claimed.strip():
        return None
    oid = _object_id(mask.get("object"))
    if oid is None:
        return None
    try:
        mask_set = load_masks(workspace / claimed.strip())
        track = mask_set.of(oid)
    except (OSError, ValueError, KeyError):
        return None
    return [int(v) for v in mask_set.frames], track


def _resolve_second_reference(second: dict[str, Any], references: Any) -> Any:
    """The reference entry scale.second uses, else None (skip the check).

    New analyses name it with reference_index; old analyses lack it, so
    fall back to matching second.name against the reference names.
    """
    if not isinstance(references, list) or not references:
        return None
    idx = second.get("reference_index")
    if isinstance(idx, bool):
        idx = None
    if isinstance(idx, int) and 0 <= idx < len(references):
        cand = references[idx]
        return cand if isinstance(cand, dict) else None
    if isinstance(idx, int):
        return None
    name = second.get("name")
    if isinstance(name, str):
        for ref in references:
            if isinstance(ref, dict) and ref.get("name") == name:
                return ref
    return None


def _second_independence_error(
    workspace: Path, scale: Any, references: Any
) -> str | None:
    """Refusal text when scale.second reuses the primary reference mask.

    Compares the primary reference (reference[0], the size reference the
    scale is built on) with the reference scale.second names, on frames
    both masks cover. IoU above SAME_OBJECT_IOU on any shared frame, or
    both entries pointing at the same file and object, means the second
    reference is the same object, not an independent check. Returns None
    when the pair is independent or cannot be compared (no shared frame,
    old analysis without a matching name, unreadable masks).
    """
    if not isinstance(scale, dict):
        return None
    second = scale.get("second")
    if second is None or not isinstance(second, dict):
        return None
    if not isinstance(references, list) or not references:
        return None
    primary = references[0]
    if not isinstance(primary, dict):
        return None
    other = _resolve_second_reference(second, references)
    if not isinstance(other, dict):
        return None
    prim_mask = primary.get("mask")
    other_mask = other.get("mask")
    if not isinstance(prim_mask, dict) or not isinstance(other_mask, dict):
        return None
    prim_file = prim_mask.get("file")
    other_file = other_mask.get("file")
    prim_obj = prim_mask.get("object")
    other_obj = other_mask.get("object")
    same_pointer = (
        isinstance(prim_file, str)
        and isinstance(other_file, str)
        and prim_file == other_file
        and isinstance(prim_obj, str)
        and isinstance(other_obj, str)
        and prim_obj == other_obj
    )
    best: tuple[float, int | None] | None = None
    prim = _reference_masks(workspace, prim_mask)
    other_pair = _reference_masks(workspace, other_mask)
    if prim is not None and other_pair is not None:
        prim_frames, prim_track = prim
        other_frames, other_track = other_pair
        if prim_track.shape[1:] == other_track.shape[1:]:
            prim_index = {frame: pos for pos, frame in enumerate(prim_frames)}
            other_index = {frame: pos for pos, frame in enumerate(other_frames)}
            for frame in sorted(set(prim_index) & set(other_index)):
                first = prim_track[prim_index[frame]].astype(bool)
                again = other_track[other_index[frame]].astype(bool)
                union = int((first | again).sum())
                if union == 0:
                    continue
                iou = float((first & again).sum()) / union
                if best is None or iou > best[0]:
                    best = (iou, frame)
    if best is None and same_pointer:
        best = (1.0, None)
    if best is None:
        return None
    iou, frame = best
    if iou <= SAME_OBJECT_IOU:
        return None
    where = "frame " + str(frame) if frame is not None else "the shared mask"
    return (
        "finish refused: the second reference is the same object as the "
        "first (IoU %.2f on %s); use a different object or body, or set "
        "scale.second to null and give scale.second_missing (why no "
        "independent reference exists)." % (iou, where)
    )


def _run_finish(tools: _Tools, args: dict[str, Any], run_dir: Path) -> tuple[bool, str, Path | None]:
    """Finish: coerce slips, compute decide/verdict/overall, validate, gate, write.

    Returns (ok, message, analysis path); only ok ends the run.
    """
    raw_name = args.get("analysis_file")
    if not isinstance(raw_name, str) or not raw_name.strip():
        return False, "finish needs an analysis_file path in the workspace.", None
    page_texts, error = _parse_page_texts(args.get("page_texts", ""))
    if error is not None:
        return False, "finish: " + error, None
    source = tools.workspace / raw_name.strip()
    try:
        analysis = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, "finish: no such file in the workspace: " + raw_name.strip(), None
    except (OSError, json.JSONDecodeError) as exc:
        return False, "finish: cannot read " + raw_name.strip() + ": " + str(exc), None
    if not isinstance(analysis, dict):
        return False, "finish: the analysis file must hold a JSON object.", None
    if page_texts:
        merged = dict(analysis.get("page_texts", {}) or {})
        merged.update(page_texts)
        analysis["page_texts"] = merged
    coerced = _coerce_analysis(analysis)
    _fill_computed(analysis)
    section = tools.toolbox.tools_section()
    if section:
        analysis["tools"] = section
    else:
        analysis.pop("tools", None)
    info = video.probe(tools.clip)
    issues = [
        issue.path + ": " + issue.message
        for issue in validate(analysis, clip_frames=info.frame_count, fps=float(info.fps))
    ]
    if issues:
        shown = "\n".join("- " + line for line in issues[:20])
        if len(issues) > 20:
            shown += "\n- ... and " + str(len(issues) - 20) + " more"
        return False, "finish: schema errors, fix the file and call finish again:\n" + shown, None
    entries = _mask_log_entries(tools.workspace)
    refs = analysis.get("reference", [])
    checked = any(
        isinstance(ref, dict)
        and _reference_checked(entries, ref.get("mask", {}).get("file"), ref.get("mask", {}).get("object"))
        for ref in refs
    ) if isinstance(refs, list) else False
    if not checked:
        return (
            False,
            "finish refused: no mask check covers the size-reference mask. "
            "Run mask_check on the reference mask file first.",
            None,
        )
    same_object = _second_independence_error(
        tools.workspace, analysis.get("scale"), analysis.get("reference")
    )
    if same_object is not None:
        return False, same_object, None
    dest = run_dir / "analysis.json"
    dest.write_text(json.dumps(analysis, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tail = ""
    if coerced:
        tail = " Coercions: " + "; ".join(coerced[:10])
        if len(coerced) > 10:
            tail += "; and " + str(len(coerced) - 10) + " more"
    return True, "finish: analysis written to " + dest.name + " and valid." + tail, dest


def _dispatch(
    tools: _Tools, name: str, args: Any, turn: int, run_dir: Path
) -> tuple[bool, str, list[Path], Path | None]:
    """Run one tool call; returns (finish_ok, text, images, analysis path)."""
    if not isinstance(args, dict):
        return False, "tool " + name + " needs an object of arguments.", [], None
    try:
        if name == "video_info":
            text, images = _run_video_info(tools)
            return False, text, images, None
        if name == "frames":
            text, images = _run_frames(tools, args, turn)
            return False, text, images, None
        if name == "sam":
            text, images = _run_sam(tools, args)
            return False, text, images, None
        if name == "mask_check":
            text, images = _run_mask_check(tools, args)
            return False, text, images, None
        if name == "search":
            text, images = _run_search(tools, args)
            return False, text, images, None
        if name == "python":
            text, images = _run_python(tools, args)
            return False, text, images, None
        if name == "make_tool":
            text, images = _run_make_tool(tools, args, turn)
            return False, text, images, None
        if name == "finish":
            ok, text, dest = _run_finish(tools, args, run_dir)
            return ok, text, [], dest
    except BudgetExhausted:
        raise
    except Exception as exc:
        detail = " ".join(str(exc).split())
        return False, "tool " + name + " failed: " + detail, [], None
    known = sorted(item["name"] for item in TOOLS)
    return False, "unknown tool " + repr(name) + "; available tools: " + ", ".join(known), [], None


def _low_note(
    *, turn: int, max_turns: int, sam: SamTool, sam_frames: int,
    search: SearchTool, searches: int, mask: MaskCheck, mask_checks: int,
    budget: Budget, toolbox: Toolbox | None = None,
) -> str:
    """Warn Spark when any budget is close to its limit, else empty."""
    notes = []
    if max_turns - turn <= 2:
        notes.append("only " + str(max_turns - turn) + " turns left")
    if sam_frames - sam.frames_used <= 100:
        notes.append("only " + str(sam_frames - sam.frames_used) + " SAM frames left")
    if searches - search.searches_made <= 1:
        notes.append("searches nearly exhausted")
    if mask_checks - mask.checks_made <= 1:
        notes.append("mask checks nearly exhausted")
    if toolbox is not None and toolbox.max_tools - toolbox.count() <= 1:
        notes.append("tool slots nearly exhausted")
    if budget.cap_usd > 0 and budget.spent >= 0.8 * budget.cap_usd:
        notes.append("only $%.4f of the cap left" % (budget.cap_usd - budget.spent))
    if not notes:
        return ""
    return (
        " [budget note: " + "; ".join(notes)
        + " - wrap up: write the analysis and call finish]"
    )


def _image_message(client: Any, images: list[Path]) -> dict[str, Any] | None:
    """A user message showing tool images, or None when there are none."""
    if not images:
        return None
    content: list[dict[str, Any]] = [
        {"type": "input_text", "text": "Images from the tool call:"}
    ]
    for path in images:
        content.append(dict(client.image_part(path)))
    return {"role": "user", "content": content}


def _rebuild_images(
    client: Any, message: dict[str, Any]
) -> dict[str, Any]:
    """Restore image parts stored as file markers (resume path)."""
    if not isinstance(message, dict) or not isinstance(message.get("content"), list):
        return message
    content: list[Any] = []
    for part in message["content"]:
        if isinstance(part, dict) and part.get("type") == "__image_file__":
            content.append(dict(client.image_part(Path(str(part["path"])))))
        else:
            content.append(part)
    return dict(message, content=content)


def _store_images(message: dict[str, Any], images: list[Path]) -> dict[str, Any]:
    """Replace image parts by file markers so turn files stay small."""
    paths = iter(str(p) for p in images)
    content: list[Any] = []
    for part in message["content"]:
        if isinstance(part, dict) and part.get("type") == "input_image":
            try:
                marker = next(paths)
            except StopIteration:
                marker = ""
            content.append({"type": "__image_file__", "path": marker})
        else:
            content.append(part)
    return dict(message, content=content)


def _write_turn(
    turns_dir: Path,
    *,
    n: int,
    spark_text: str,
    tool_call: str | None,
    arguments: Any,
    result_text: str,
    image_paths: list[Path],
    output_items: Any,
    result_items: list[dict[str, Any]],
    cost: float,
    cumulative: float,
    counters: dict[str, int],
) -> Path:
    """Write one turn file; returns its path."""
    record = {
        "n": n,
        "spark_text": spark_text,
        "tool_call": tool_call,
        "arguments": arguments,
        "result_text": result_text,
        "image_paths": [str(p) for p in image_paths],
        "output_items": output_items,
        "result_items": result_items,
        "cost": cost,
        "cumulative": cumulative,
        "counters": counters,
    }
    path = turns_dir / ("turn%02d.json" % n)
    path.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read_turn(path: Path) -> dict[str, Any]:
    """Load one turn file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _client_for(tier: str, run_dir: Path, spark: Any) -> tuple[Any, str]:
    """Build the provider: the injected fake, or a real MetaClient."""
    if spark is not None:
        return spark, getattr(spark, "model", "")
    if tier not in TIER_MODELS:
        raise ValueError("tier must be contributor|standard, got " + repr(tier))
    settings = Settings(
        base_url=Settings.from_env().base_url,
        model=TIER_MODELS[tier],
        effort=Settings.from_env().effort,
        max_output_tokens=Settings.from_env().max_output_tokens,
        prices_path=Settings.from_env().prices_path,
        global_ledger_path=Settings.from_env().global_ledger_path,
        run_ledger_path=None,
        timeout_s=Settings.from_env().timeout_s,
    )
    ledger = Ledger(run_dir / "ledger.jsonl", settings.global_ledger_path)
    client = MetaClient(settings=settings, ledger=ledger, run=run_dir.name)
    return client, TIER_MODELS[tier]


def _counters(
    sam: SamTool,
    search: SearchTool,
    mask: MaskCheck,
    sam_calls: int,
    toolbox: Toolbox | None = None,
) -> dict[str, int]:
    """Per-run tool counters for turn files and the summary."""
    return {
        "sam_calls": sam_calls,
        "sam_frames": sam.frames_used,
        "searches": search.searches_made,
        "mask_checks": mask.checks_made,
        "tools": toolbox.count() if toolbox is not None else 0,
    }


def run_analysis(
    video_path: str | Path,
    run_dir: str | Path,
    *,
    tier: str = "contributor",
    cap_usd: float = 2.0,
    max_turns: int = 60,
    sam_frames: int = 1500,
    searches: int = 6,
    mask_checks: int = 4,
    spark: Any = None,
    resume: bool = False,
    python_runner: PythonRunner | None = None,
    cache_dir: str | Path | None = None,
    effort: str = "high",
    agent_max_output_tokens: int | None = None,
    max_tools: int = 4,
    tool_attempts: int = 3,
) -> RunSummary:
    """Run one analysis: blind start, tool loop, finish, logs.

    spark is an injectable next-action provider for tests; by default it
    is Spark through MetaClient.respond. resume replays saved turns and
    continues from the next turn without calling anything again.
    python_runner runs the ``python`` tool (the sandbox by default; tests
    may pass a runner without the Seatbelt profile, which M5 owns).
    effort is the reasoning effort for the agent's own turns (high by
    default; sub-calls keep the configured Settings effort); it is
    logged in the summary. agent_max_output_tokens is the per-turn output
    limit for the agent's own calls (default 32768; reasoning tokens count
    toward it); a turn cut off by it retries once with double the limit.
    max_tools caps registered make_tool tools per run; tool_attempts caps
    make_tool attempts per tool name.
    """
    started = time.monotonic()
    run_path = Path(run_dir)
    workspace = run_path / "workspace"
    turns_dir = run_path / "turns"
    turns_dir.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    clip = workspace / "clip.mp4"
    if not resume or not clip.exists():
        shutil.copyfile(video_path, clip)
    info = video.probe(clip)
    dup_runs = video.duplicate_runs(video.frame_diffs(clip))
    probe_text = clip_probe_text(info, dup_runs)
    system = assemble_system_prompt(
        max_turns=max_turns,
        sam_frames=sam_frames,
        searches=searches,
        mask_checks=mask_checks,
        cap_usd=cap_usd,
        probe_text=probe_text,
        max_tools=max_tools,
        tool_attempts=tool_attempts,
    )

    provider, model = _client_for(tier, run_path, spark)
    if agent_max_output_tokens is None:
        agent_max_output_tokens = Settings.from_env().agent_max_output_tokens
    agent_limit = int(agent_max_output_tokens)
    budget = Budget(cap_usd=float(cap_usd))
    guard = GuardClient(provider, budget)
    sam = SamTool(guard, workspace, clip, budget_frames=sam_frames, cache_dir=cache_dir)
    search = SearchTool(guard, workspace, limit=searches)
    mask = MaskCheck(guard, workspace, clip, limit=mask_checks)
    runner = python_runner or run_python
    toolbox = Toolbox(workspace, runner, max_tools=max_tools, max_attempts=tool_attempts)
    tools = _Tools(
        sam=sam,
        search=search,
        mask=mask,
        workspace=workspace,
        clip=clip,
        client=guard,
        python_runner=runner,
        toolbox=toolbox,
    )
    sam_calls = 0

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": probe_text},
                dict(provider.video_part(str(clip))),
            ],
        }
    ]

    log_path = run_path / "conversation.jsonl"
    if resume and log_path.exists():
        old_turns = sorted(turns_dir.glob("turn*.json"))
        for path in old_turns:
            record = _read_turn(path)
            for item in record.get("output_items", []):
                messages.append(item)
            for item in record.get("result_items", []):
                messages.append(_rebuild_images(guard, item))
            budget.spent = float(record.get("cumulative", budget.spent))
            saved = record.get("counters", {})
            sam_calls = int(saved.get("sam_calls", sam_calls))
        turn = len(old_turns) + 1
        log_mode = "a"
    else:
        if log_path.exists():
            log_path.unlink()
        log_path.write_text(
            json.dumps({"n": 0, "probe": probe_text, "clip": "clip.mp4"}) + "\n",
            encoding="utf-8",
        )
        log_mode = "a"
        turn = 1

    def note(summary: RunSummary, *, done: int) -> RunSummary:
        """Fill the shared tail fields before returning."""
        summary.turns = done
        summary.sam_calls = sam_calls
        summary.sam_frames = sam.frames_used
        summary.searches = search.searches_made
        summary.mask_checks = mask.checks_made
        summary.tools_made = toolbox.count()
        summary.cost_usd = budget.spent
        summary.wall_s = time.monotonic() - started
        summary.tier = tier
        summary.model = model
        summary.effort = effort
        (run_path / "summary.json").write_text(
            json.dumps(summary.to_json(), indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        return summary

    while True:
        if turn > max_turns:
            return note(RunSummary(status=BUDGET_STATUS), done=turn - 1)
        try:
            budget.check()
        except BudgetExhausted:
            return note(RunSummary(status=BUDGET_STATUS), done=turn - 1)
        spent_before = budget.spent
        try:
            response = guard.respond(
                _prune(messages),
                instructions=system,
                tools=TOOLS,
                model=model or None,
                effort=effort,
                max_output_tokens=agent_limit,
                note="agent-turn-%02d" % turn,
            )
        except BudgetExhausted:
            return note(RunSummary(status=BUDGET_STATUS), done=turn - 1)
        except Exception as exc:
            detail = " ".join(str(exc).split())
            return note(RunSummary(status="error: spark call failed: " + detail), done=turn - 1)
        cut_off: str | None = None
        reason = getattr(response, "incomplete_reason", None)
        if reason is not None:
            if reason != "max_output_tokens":
                return note(
                    RunSummary(
                        status="error: spark call failed: response incomplete (" + reason + ")"
                    ),
                    done=turn - 1,
                )
            try:
                response = guard.respond(
                    _prune(messages),
                    instructions=system,
                    tools=TOOLS,
                    model=model or None,
                    effort=effort,
                    max_output_tokens=agent_limit * 2,
                    note="agent-turn-%02d-retry" % turn,
                )
            except BudgetExhausted:
                return note(RunSummary(status=BUDGET_STATUS), done=turn - 1)
            except Exception as exc:
                detail = " ".join(str(exc).split())
                return note(RunSummary(status="error: spark call failed: " + detail), done=turn - 1)
            if getattr(response, "incomplete_reason", None) is not None:
                cut_usage = getattr(response, "usage", None)
                cut_off = (
                    "Your last answer was cut off at %d output tokens "
                    "(max_output_tokens %d). Do the work in smaller steps: "
                    "make one small tool call now and continue bit by bit."
                    % (
                        int(getattr(cut_usage, "output_tokens", 0) or 0),
                        agent_limit * 2,
                    )
                )
        spark_text = str(getattr(response, "text", "") or "")
        calls = list(getattr(response, "function_calls", []) or [])
        output_items = getattr(response, "output", []) or []
        if cut_off is not None:
            calls = []
            output_items = []

        this_call: str | None = None
        arguments: Any = None
        finish_ok = False
        analysis_dest: Path | None = None
        images: list[Path] = []
        if not calls:
            result_text = cut_off or (
                "Reply with exactly one tool call per turn: pick the single most "
                "informative tool and call it now."
            )
        else:
            if len(calls) > 1:
                extra = " (Spark returned " + str(len(calls)) + " calls; running the first)"
            else:
                extra = ""
            first = calls[0]
            this_call = str(first.name)
            arguments = first.arguments
            if this_call == "sam":
                sam_calls += 1
            try:
                finish_ok, result_text, images, analysis_dest = _dispatch(
                    tools, this_call, arguments, turn, run_path
                )
            except BudgetExhausted:
                return note(RunSummary(status=BUDGET_STATUS), done=turn - 1)
            result_text = result_text + extra
            result_text += _low_note(
                turn=turn,
                max_turns=max_turns,
                sam=sam,
                sam_frames=sam_frames,
                search=search,
                searches=searches,
                mask=mask,
                mask_checks=mask_checks,
                budget=budget,
                toolbox=toolbox,
            )
        turn_cost = budget.spent - spent_before

        for item in output_items:
            messages.append(item)
        if this_call is None:
            guidance = {
                "role": "user",
                "content": [{"type": "input_text", "text": result_text}],
            }
            messages.append(guidance)
            result_items = [guidance]
        else:
            call_id = str(calls[0].call_id)
            messages.append(
                {"type": "function_call_output", "call_id": call_id, "output": result_text}
            )
            result_items: list[dict[str, Any]] = [
                {"type": "function_call_output", "call_id": call_id, "output": result_text}
            ]
            if images:
                shown = _image_message(guard, images)
                assert shown is not None
                messages.append(shown)
                result_items.append(_store_images(shown, images))

        stored_args = arguments if isinstance(arguments, dict) else {"arguments": arguments}
        _write_turn(
            turns_dir,
            n=turn,
            spark_text=spark_text,
            tool_call=this_call,
            arguments=stored_args,
            result_text=result_text,
            image_paths=images,
            output_items=output_items,
            result_items=result_items,
            cost=turn_cost,
            cumulative=budget.spent,
            counters=_counters(sam, search, mask, sam_calls, toolbox),
        )
        with open(log_path, log_mode, encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "n": turn,
                        "spark_text": spark_text,
                        "tool_call": this_call,
                        "arguments": stored_args,
                        "result_text": _compact_text(result_text),
                        "image_paths": [str(p) for p in images],
                        "cost": turn_cost,
                        "cumulative": budget.spent,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        if finish_ok:
            summary = RunSummary(status=OK_STATUS, analysis_path=analysis_dest)
            return note(summary, done=turn)
        turn += 1



