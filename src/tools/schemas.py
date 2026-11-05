# generated from brief/07 · part 07 owns this file
"""Tool schemas: the single source of every tool definition (part 07 §10).

The loop's prompt prefix (part 06) and the Spark client (part 04)
both use this export; neither keeps its own copy.

Each entry is ``{"name", "description", "parameters"}`` where
``parameters`` is a strict JSON schema: every object level sets
``additionalProperties: false`` and lists every property in
``required`` (optional values use nullable ``type`` arrays, the
strict-mode idiom). The live API and the offline stub both reject
anything looser.

The ``submit`` description is generated from
``src/contract/evidence.schema.json`` (part 12 §14), never
hand-written: it lists every field path with its type, whether it is
required, and its schema description, then embeds the shipped
``src/contract/evidence.example.json``. A hand-written skeleton once
failed the schema itself (``contract_version: 1``, ``worlds: []``,
``clock: {}``, string artifacts); generating it from the schema
keeps the description and the validator in lockstep.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    "TOOL_SCHEMAS",
    "TOOL_NAMES",
    "EXPECTED_PARAMS",
    "SUBMIT_DESCRIPTION",
    "SUBMIT_EVIDENCE_PATHS",
    "submit_description",
    "required_evidence_paths",
]

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "contract"


def _load_json(name: str) -> dict:
    return json.loads((_SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _resolve(node, root):
    """Follow one local ``$ref`` (``#/$defs/...``); else the node."""
    if isinstance(node, dict) and isinstance(node.get("$ref"), str):
        ref = node["$ref"]
        if ref == "#" or ref.startswith("#/"):
            target = root
            for part in ref.lstrip("#/").split("/"):
                if not isinstance(target, dict) or part not in target:
                    return node
                target = target[part]
            if isinstance(target, dict):
                return target
    return node


def _type_of(node) -> str:
    kind = node.get("type", "object") if isinstance(node, dict) else "?"
    if isinstance(kind, list):
        return "/".join(str(k) for k in kind)
    return str(kind)


def _describe_lines(schema: dict, root: dict) -> tuple:
    """``[(path, type, required, description)]`` for every schema node."""
    lines: list = []

    def _walk(node, path: str, required: bool) -> None:
        node = _resolve(node, root)
        if not isinstance(node, dict):
            return
        kind = node.get("type", "object")
        kinds = [kind] if isinstance(kind, str) else list(kind)
        description = str(node.get("description") or "").strip()
        enum = node.get("enum")
        extra = f" one of {sorted(enum)}" if isinstance(enum, list) else ""
        lines.append((path or "(root)", _type_of(node), required,
                      (description + extra).strip()))
        if "object" in kinds:
            properties = node.get("properties") or {}
            need = node.get("required") or []
            for name in properties:
                child = (f"{path}.{name}" if path else str(name))
                _walk(properties[name], child, name in need)
        if "array" in kinds and isinstance(node.get("items"), dict):
            _walk(node["items"], f"{path}[]", required=False)

    _walk(schema, "", True)
    return tuple(lines)


def _error_budget_lines(root: dict) -> list:
    """Description lines for the error budget, generated from the schema.

    Part 07 §13: the ``submit`` description names the required parts
    of the error budget — the always-required components and the
    conditions that require ``reading_spread`` and
    ``repetition_spread`` (part 12 §15). Everything here is read off
    the evidence schema's ``error_budget.components`` node (its
    description text and its controlled ``name`` enum), never
    hand-written, so the description and the validator stay in
    lockstep.
    """
    lines: list = []
    try:
        budget = _resolve(root.get("properties", {}).get(
            "error_budget", {}), root)
        components = _resolve((budget.get("properties", {}) or {}).get(
            "components", {}), root)
    except AttributeError:
        return lines
    if not isinstance(components, dict):
        return lines
    stated = str(components.get("description") or "").strip()
    if stated:
        lines.append("Error-budget rules (from the evidence schema, "
                     "part 12 section 15):")
        lines.append(stated)
    try:
        names = (((components.get("items", {}) or {}).get(
            "properties", {}) or {}).get("name", {}) or {}).get("enum")
    except AttributeError:
        names = None
    if isinstance(names, list) and names:
        lines.append("Controlled component names: "
                     + ", ".join(f"`{name}`" for name in names) + ".")
    return lines


def _node_description(root: dict, *steps) -> str:
    """Description of a schema node reached by property/index steps.

    ``steps`` are property names, with ``[]`` meaning the array's
    ``items`` (resolving ``$defs`` evidence-segment style ``$ref`` s on
    the way). Returns ``""`` when the path does not resolve to a node
    carrying a description.
    """
    node = root
    for step in steps:
        node = _resolve(node, root)
        if not isinstance(node, dict):
            return ""
        if step == "[]":
            node = node.get("items")
            if not isinstance(node, dict):
                return ""
            continue
        node = (node.get("properties") or {}).get(step)
        if not isinstance(node, dict):
            return ""
    node = _resolve(node, root)
    if not isinstance(node, dict):
        return ""
    stated = node.get("description")
    return str(stated).strip() if isinstance(stated, str) else ""


def _scale_rules_lines(root: dict) -> list:
    """Description lines for the scale cross-check, generated from the schema.

    Part 07 §16 (rule R-S6, part 11 §13): scale is always cross-checked
    by two or three references of different things — never by a rule
    tied to a role in the clip. The person-as-second-reference rule
    (``SECOND_REFERENCE_REQUIRED_PERSON``) and the ``subject.kind``
    checks are withdrawn; ``subject.kind`` is descriptive only and no
    rule reads it. Every rule sentence here is the evidence schema's
    own description text for the node it governs (read off the schema,
    never hand-written), so the description and the validator stay in
    lockstep; the framing names the enforcing validator codes so the
    agent can match a rejection to the rule it broke.
    """
    quotes = [
        ("references",
         _node_description(root, "references")),
        ("scale",
         _node_description(root, "scale")),
        ("scale.second_reference_index",
         _node_description(root, "scale", "second_reference_index")),
        ("scale.second_reference_absent_reason",
         _node_description(root, "scale",
                            "second_reference_absent_reason")),
        ("segments[].subject",
         _node_description(root, "segments", "[]", "subject")),
        ("references[].mask_check.alternative_readings",
         _node_description(root, "references", "[]", "mask_check",
                            "alternative_readings")),
    ]
    lines = [
        "Scale cross-check rules (from the evidence schema, part 12; "
        "enforced by the validator, part 11 section 13, rule R-S6):",
        "scale comes from two or three references of different things, "
        "each with its own blind check, size source and extent at the "
        "depth of the motion. Every pair of references must agree "
        "within 2 combined sigmas (`REFERENCES_DISAGREE` names the "
        "pair): find the wrong reading or size, never average a "
        "disagreement away. A scale resting on one reference is "
        "accepted only with `second_reference_absent_reason`, and its "
        "verdict is `undetermined` (\"scale rests on one reference\"). "
        "Two extents of near-identical masks are not two references "
        "(`SECOND_REFERENCE_SAME_OBJECT`). `subject.kind` is "
        "descriptive only — no rule reads it. Every blind-check "
        "alternative is answered (`ALTERNATIVE_NOT_ADDRESSED`).",
    ]
    for path, stated in quotes:
        if stated:
            lines.append(f"`{path}`: {stated}")
    return lines


def required_evidence_paths(schema: dict | None = None) -> tuple:
    """Every required evidence field path (``a.b``, arrays as ``a[]``).

    Independent of the description generator below: the submit test
    re-derives these paths from the schema and asserts each one
    appears verbatim in the description, so a hand-written skeleton
    that drops a field fails.
    """
    root = dict(schema) if isinstance(schema, dict) else _load_json(
        "evidence.schema.json")
    paths: list = []

    def _walk(node, path: str) -> None:
        node = _resolve(node, root)
        if not isinstance(node, dict):
            return
        kind = node.get("type", "object")
        kinds = [kind] if isinstance(kind, str) else list(kind)
        if "object" in kinds:
            properties = node.get("properties") or {}
            for name in node.get("required") or []:
                if name not in properties:
                    continue
                child = f"{path}.{name}" if path else str(name)
                paths.append(child)
                _walk(properties[name], child)
        if "array" in kinds and isinstance(node.get("items"), dict):
            _walk(node["items"], f"{path}[]")

    _walk(root, "")
    return tuple(paths)


def submit_description(schema: dict | None = None,
                       example: dict | None = None) -> tuple:
    """Build the ``submit`` description from the evidence schema.

    Returns ``(description, required_paths)``. The description gives
    every field path with its type, whether it is required, and its
    schema description, then embeds the shipped example verbatim.
    """
    root = dict(schema) if isinstance(schema, dict) else _load_json(
        "evidence.schema.json")
    if example is None:
        try:
            example = _load_json("evidence.example.json")
        except OSError:
            example = {}
    parts = [
        "Hand in the measured evidence object defined by the result-data",
        "contract (evidence schema, contract part 12 section 14). Pass",
        "it as `evidence` (a JSON object, or a JSON string of one) or as",
        "`evidence_path`: a run-relative path to a JSON file under",
        "`workspace/` that the agent wrote with `run_python`, holding the",
        "same object. Give exactly one of the two, never both, never",
        "neither. Prefer `evidence_path` whenever the evidence holds",
        "arrays (tracks, fit curves, outlines): the file's content as",
        "submitted is copied to `artifacts/t<turn>_evidence.json`, so a",
        "retyped curve can never silently replace the measured one.",
        "Set `dry_run: true` to validate without consuming an attempt:",
        "a dry run runs every check and returns the same error list",
        "but writes no submission and no result (only the error-list",
        "file, plus the evidence copy when `evidence_path` is used) and",
        "counts against the dry-run budget only.",
        "",
        "The object is checked by the validator; on acceptance the run",
        "ends and the validator computes the verdict, ghosts and sentence",
        "itself. On rejection the result's summary lists every error as",
        "`CODE field: detail` (validator codes first, grouped by code) and",
        "the full list is saved to",
        "`artifacts/t<turn>_submit_errors.json`, named in the result.",
        "At most three rejected non-dry-run submits per run, and at most",
        "five dry runs per run.",
        "",
    ]
    parts.extend(_error_budget_lines(root))
    parts += [""]
    parts.extend(_scale_rules_lines(root))
    parts += [
        "",
        "Every field path with its type, required flag and meaning:",
    ]
    for path, kind, required, description in _describe_lines(root, root):
        flag = "required" if required else "optional"
        line = f"- `{path}` ({kind}, {flag})"
        if description:
            line += f": {description}"
        parts.append(line)
    parts += [
        "",
        "Minimal skeleton — fill every required field (the shipped",
        "`evidence.example.json`, embedded verbatim):",
        "```json",
        json.dumps(example, indent=2, sort_keys=True),
        "```",
    ]
    return "\n".join(parts) + "\n", required_evidence_paths(root)


SUBMIT_DESCRIPTION, SUBMIT_EVIDENCE_PATHS = submit_description()


def _view_frames_schema() -> dict:
    return {
        "type": "object",
        "description": (
            "Look at the clip as contact-sheet images with a text index "
            "mapping each cell to its frame number and measured timestamp "
            "(from input/timing.json, never a container fps claim). "
            "Give a frame range plus stride, or explicit frame indices. "
            "An optional normalised crop (x0,y0,x1,y1 in 0..1) zooms into "
            "a region (mask-quality and scene-evidence inspection). "
            "Layout is a contact-sheet grid or a sequence. Frame indices "
            "out of range, and ranges spanning a confirmed cut, are "
            "reported — never silently served. Contact sheets are saved "
            "under artifacts/ and named in the result; the text index "
            "rides in metrics."
        ),
        "properties": {
            "frame_start": {
                "type": ["integer", "null"],
                "description": "First frame of the range (with frame_end).",
            },
            "frame_end": {
                "type": ["integer", "null"],
                "description": "Last frame of the range, inclusive.",
            },
            "stride": {
                "type": ["integer", "null"],
                "description": ("Step between sampled frames; default 1. "
                                "Must be >= 1 when given."),
            },
            "frame_indices": {
                "type": ["array", "null"],
                "description": ("Explicit frames instead of a range. "
                                "Either this or frame_start+frame_end."),
                "items": {"type": "integer"},
            },
            "crop": {
                "type": ["object", "null"],
                "description": ("Normalised crop window in 0..1 "
                                "(left, top, right, bottom)."),
                "properties": {
                    "x0": {"type": "number",
                           "description": "Left edge in 0..1."},
                    "y0": {"type": "number",
                           "description": "Top edge in 0..1."},
                    "x1": {"type": "number",
                           "description": "Right edge in 0..1."},
                    "y1": {"type": "number",
                           "description": "Bottom edge in 0..1."},
                },
                "required": ["x0", "y0", "x1", "y1"],
                "additionalProperties": False,
            },
            "layout": {
                "type": ["string", "null"],
                "description": ("Contact-sheet layout: 'grid' (default) "
                                "or 'sequence'."),
            },
        },
        "required": ["frame_start", "frame_end", "stride",
                     "frame_indices", "crop", "layout"],
        "additionalProperties": False,
    }


def _segment_schema() -> dict:
    return {
        "type": "object",
        "description": (
            "Segment one noun phrase (e.g. 'the astronaut', 'the wall') "
            "over a frame range with remote SAM 3.1. BILLING IS REAL: "
            "every call bills at least 50 frames — ranges under 50 frames "
            "are refused unless confirm_small_range is true, and the "
            "ledger is debited max(50, frames). Outputs: masks.npz "
            "(per-frame mask arrays plus frame indices and timestamps), "
            "preview overlays for a sparse set of frames, and a per-frame "
            "mask area/bbox/centroid table — all named in the result. "
            "The tool reports what pixels the mask covers, never what "
            "object they are: whether the mask covers what the phrase "
            "meant is established by check_mask, not assumed here."
        ),
        "properties": {
            "phrase": {
                "type": "string",
                "description": "One noun phrase naming what to segment.",
            },
            "frame_start": {
                "type": "integer",
                "description": "First frame of the range, inclusive.",
            },
            "frame_end": {
                "type": "integer",
                "description": "Last frame of the range, inclusive.",
            },
            "confirm_small_range": {
                "type": "boolean",
                "description": ("Confirm billing for ranges under 50 "
                                "frames (still billed 50). Default false, "
                                "which refuses the call."),
            },
        },
        "required": ["phrase", "frame_start", "frame_end",
                     "confirm_small_range"],
        "additionalProperties": False,
    }


def _check_mask_schema() -> dict:
    return {
        "type": "object",
        "description": (
            "Blind second look at one mask overlay (the scale lesson). A "
            "separate context-free model call receives ONLY the overlay "
            "image, the mask's pixel extents, and a neutral question — no "
            "history, no phrase, no hypothesis, no clip name. It returns a "
            "structured description of WHAT THE MASK COVERS (which part of "
            "the visible object, which edges it includes or excludes, "
            "e.g. 'covers the pack and the box mounted above it'), plus "
            "alternative readings where coverage is ambiguous — "
            "including any separable or stacked parts inside the tinted "
            "region (for example a unit mounted on top of another) and "
            "any part of the same object left outside it. It is "
            "deliberately NOT asked what the object IS: it reports "
            "coverage, never identity. Debits the mask-check budget; at "
            "least one record per run is required and verified at "
            "submit time."
        ),
        "properties": {
            "overlay_artifact": {
                "type": "string",
                "description": ("Run-relative artifacts/ path of the mask "
                                "overlay image (a segment preview)."),
            },
            "extents": {
                "type": ["object", "string", "null"],
                "description": ("Mask pixel extents as an object or a JSON "
                                "string of one; default is the overlay "
                                "image dimensions."),
            },
        },
        "required": ["overlay_artifact", "extents"],
        "additionalProperties": False,
    }


def _web_search_schema() -> dict:
    return {
        "type": "object",
        "description": (
            "Look up generic facts (real-world sizes of objects, natural "
            "human step-rate ranges, standard dimensions — including "
            "things named in the frames such as places, missions, people "
            "or models) through the blindness filter. Every query passes "
            "two gates before execution: a pattern screen rejecting "
            "answer-seeking forms (the clip itself, an analysis of it, "
            "real-or-fake questions, measured gravity / jump height / "
            "hang time of the event), and a context-free classifier that "
            "sees ONLY the query text and rejects queries trying to find "
            "a specific video, an analysis of it, or the answer to "
            "whether its motion is real or what gravity it shows. "
            "Rejected queries return a structured refusal — rephrase "
            "generically. Allowed queries return the sourced facts: each "
            "item carries its text, source URL and verbatim quote, so "
            "references can cite them. All queries and filter decisions "
            "are logged for the prompt-leak audit."
        ),
        "properties": {
            "query": {
                "type": "string",
                "description": ("One generic fact lookup, e.g. 'life "
                                "support backpack height metres'."),
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }


def _run_python_schema() -> dict:
    return {
        "type": "object",
        "description": (
            "Run agent-written Python in a macOS sandbox-exec sandbox. "
            "The run directory is the working directory: read only "
            "input/, workspace/, artifacts/ and src/helpers/ (read-only); "
            "write only workspace/ and artifacts/; no network; the "
            "environment is scrubbed (no API keys, no home directory). "
            "Address files by these relative paths: resolving the "
            "working directory itself (os.getcwd, abspath, resolve of "
            "a relative path) and listing it are denied because the "
            "run root is unreadable — plain relative opens work. "
            "Import the verified helpers with e.g. "
            "`from helpers import masks_io` (also tracks, physics, "
            "clock) — never re-implement fits. CPU/wall timeout and a "
            "memory cap apply from config (overridable per call via "
            "timeout_s/memory_mb, clamped to the caps). Stdout/stderr return "
            "truncated, plus the list of files created or modified (names "
            "and sizes); full stdout is saved to "
            "artifacts/t<turn>_run_python_<n>.stdout.txt when truncated, "
            "and that file is named instead. Nothing printed here is a "
            "result until submitted and validated."
        ),
        "properties": {
            "code": {
                "type": "string",
                "description": ("The Python program to run (run with the "
                                "run directory as cwd)."),
            },
            "timeout_s": {
                "type": ["number", "null"],
                "description": ("Wall-time budget in seconds, clamped to "
                                "the config cap; default is the cap."),
            },
            "memory_mb": {
                "type": ["number", "null"],
                "description": ("Resident-size cap in MiB, clamped to the "
                                "config cap; default is the cap."),
            },
        },
        "required": ["code", "timeout_s", "memory_mb"],
        "additionalProperties": False,
    }


def _check_line_schema() -> dict:
    return {
        "type": "object",
        "description": (
            "Blind look at one to three measured lines on one frame "
            "(the line-span check). The tool draws each line itself "
            "on that frame of the run's own clip — numbered, 3 px, a "
            "contrasting colour, small end caps — and saves the "
            "overlay under artifacts/; the agent never supplies an "
            "image. Two fresh context-free model calls follow: the "
            "first receives ONLY the overlay plus a neutral question "
            "and describes where each numbered line starts and ends, "
            "from which side the object is seen, and along which of "
            "its own dimensions the line runs; "
            "the second receives those descriptions plus the claims, "
            "with no image, and answers yes or no per line. The "
            "record (frame, endpoints, claim, blind description, "
            "view, dimension, agrees, why) is saved as "
            "artifacts/t<turn>_check_line_"
            "<k>.json and appended to artifacts/line_checks.jsonl, "
            "and both files are named in the result. At most 6 calls "
            "per run. The blindness filter applies to the claims. A "
            "checking tool: it stays open in the finishing phase."
        ),
        "properties": {
            "frame": {
                "type": "integer",
                "description": ("Frame of the run's own clip to draw "
                                "on."),
            },
            "lines": {
                "type": "array",
                "description": ("One to three measured lines: each "
                                "{x1, y1, x2, y2, claim} in frame "
                                "pixels, with claim in plain words, "
                                "e.g. 'hand length: wrist crease to "
                                "the tip of the middle finger'."),
                "items": {
                    "type": "object",
                    "properties": {
                        "x1": {
                            "type": "number",
                            "description": "Start x in frame pixels.",
                        },
                        "y1": {
                            "type": "number",
                            "description": "Start y in frame pixels.",
                        },
                        "x2": {
                            "type": "number",
                            "description": "End x in frame pixels.",
                        },
                        "y2": {
                            "type": "number",
                            "description": "End y in frame pixels.",
                        },
                        "claim": {
                            "type": "string",
                            "description": ("What the line is said to "
                                            "measure, in plain words."),
                        },
                    },
                    "required": ["x1", "y1", "x2", "y2", "claim"],
                    "additionalProperties": False,
                },
                "minItems": 1,
                "maxItems": 3,
            },
        },
        "required": ["frame", "lines"],
        "additionalProperties": False,
    }


def _motion_overview_schema() -> dict:
    return {
        "type": "object",
        "description": (
            "Show the trajectories of what SAM found, so every "
            "repetition is seen before it is measured. Local "
            "computation over a segment masks file: no API call, no "
            "price. Per object and frame the tool reads bottom, top "
            "and centroid y, centroid x, height and area on measured "
            "timestamps; the support level at a frame is the lowest "
            "bottom position within plus/minus 1 s and rise is "
            "support minus bottom, in pixels. A candidate flight is a "
            "maximal run of at least 4 frames where the rise is at "
            "least max(3 px, 4 percent of the median mask height). "
            "Each candidate reports its id, frames, times, airtime, "
            "peak rise, fitted centroid parabola curvature with sign "
            "and R squared, and mask flags (area jumps, frame-edge "
            "contact, splits). Outputs: a JSON table, a chart image "
            "with one row per object, and one strip image per "
            "candidate with the object outline drawn. Candidates are "
            "pixel facts, never decisions: the tool never says jump."
        ),
        "properties": {
            "masks_artifact": {
                "type": ["string", "null"],
                "description": ("Run-relative artifacts path of the "
                                "segment masks file to overview."),
            },
            "object_ids": {
                "type": ["array", "null"],
                "description": ("Object ids to overview; null (default) "
                                "overviews every object in the file."),
                "items": {"type": ["string", "integer"]},
            },
        },
        "required": ["masks_artifact", "object_ids"],
        "additionalProperties": False,
    }


def _submit_schema() -> dict:
    return {
        "type": "object",
        "description": SUBMIT_DESCRIPTION,
        "properties": {
            "evidence": {
                # The description (generated from the evidence schema)
                # carries the full field list; the wire type stays an
                # open object so the definition keeps its strict shape.
                "type": ["object", "null"],
                "description": ("The measured evidence object (see "
                                "description for every field). Give "
                                "exactly one of this or evidence_path."),
            },
            "evidence_path": {
                "type": ["string", "null"],
                "description": ("Run-relative path to a JSON file under "
                                "workspace/ holding the evidence object; "
                                "preferred when the evidence holds "
                                "arrays. Give exactly one of this or "
                                "evidence."),
            },
            "dry_run": {
                "type": "boolean",
                "description": ("Validate only: same error list, no "
                                "attempt consumed, nothing written."),
            },
        },
        "required": ["evidence", "evidence_path", "dry_run"],
        "additionalProperties": False,
    }


TOOL_SCHEMAS: list = [
    {"name": "view_frames", "description": (
        "Look at frames as contact sheets with measured timestamps."),
     "parameters": _view_frames_schema()},
    {"name": "segment", "description": (
        "Cut out one named phrase over a frame range; every call bills "
        "frames (minimum 50)."),
     "parameters": _segment_schema()},
    {"name": "check_mask", "description": (
        "Blind second look at a mask overlay; coverage only, never "
        "identity."),
     "parameters": _check_mask_schema()},
    {"name": "web_search", "description": (
        "Look up generic facts through the blindness filter."),
     "parameters": _web_search_schema()},
    {"name": "run_python", "description": (
        "Run agent code in the sandbox (run dir is cwd; helpers via "
        "`from helpers import ...`)."),
     "parameters": _run_python_schema()},
    {"name": "check_line", "description": (
        "Blind look at measured lines; the tool draws the overlay."),
     "parameters": _check_line_schema()},
    {"name": "motion_overview", "description": (
        "Trajectories of what SAM found; pixel facts, not decisions."),
     "parameters": _motion_overview_schema()},
    {"name": "submit", "description": (
        "Hand in evidence; structured feedback, at most three tries."),
     "parameters": _submit_schema()},
]

#: Tool names in dispatch order.
TOOL_NAMES: tuple = tuple(entry["name"] for entry in TOOL_SCHEMAS)

#: Top-level parameters each tool accepts (the loop only forwards these).
EXPECTED_PARAMS: dict = {
    entry["name"]: tuple(entry["parameters"]["properties"])
    for entry in TOOL_SCHEMAS
}
