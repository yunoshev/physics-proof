# generated from brief/07 · part 07 owns this file
"""``submit`` — handing in evidence (part 07 §7).

Takes the structured evidence object defined by part 12, writes it
to ``workspace/submission.json``, invokes part 11's validator, and
returns acceptance (the loop ends) or the structured error list
(bounded retries, part 06 §2). The agent cannot write
``result.json`` directly — ``submit`` is the only path, so no run
can bypass validation.

Rejections are readable: the summary lists every error as
``CODE field: detail`` (validator codes first, grouped by code, up
to 40 lines, then ``+N more of CODE``), and the full list is saved
to ``artifacts/t<turn>_submit_errors.json`` (dry runs included).
``dry_run: true`` validates fully and returns the same error list
without consuming an attempt or writing any result.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from src import config as _config

from .common import (
    append_produced,
    check_run_path,
    next_artifact,
    read_produced,
    read_timing,
    run_path,
)
from .result import err_result, ok_result

__all__ = [
    "submit",
    "collect_run_context",
    "format_errors",
    "MAX_SUMMARY_ERRORS",
]

#: Error lines carried in the summary before the overflow marker.
MAX_SUMMARY_ERRORS = 40


def _dry_runs_path(run_dir) -> Path:
    # Operator-only counter: dry runs are a budget, not agent data.
    return (Path(str(run_dir)) / str(_config.LOGS_DIR_NAME)
            / "dry_runs.json")


def read_dry_run_count(run_dir) -> int:
    """Dry runs used so far by this run (operator-only counter)."""
    try:
        raw = json.loads(_dry_runs_path(run_dir).read_text(
            encoding="utf-8"))
        if isinstance(raw, dict):
            return max(0, int(raw.get("dry_runs", 0)))
    except (OSError, ValueError, TypeError):
        pass
    return 0


def _bump_dry_runs(run_dir) -> int:
    count = read_dry_run_count(run_dir) + 1
    try:
        path = _dry_runs_path(run_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"dry_runs": count}) + "\n",
                        encoding="utf-8")
    except OSError:
        pass
    return count


def _call_validator(check, draft, run_context, dry_run):
    """Call the validator with the widest shape it accepts.

    The real part-11 validator takes ``dry_run``; narrower fakes
    (two- or one-argument) are honoured by falling back. The shape
    is probed with :mod:`inspect` so a validator is never invoked
    twice for one submission.
    """
    kwargs: dict = {}
    try:
        parameters = inspect.signature(check).parameters
        takes_dry_run = (
            "dry_run" in parameters
            or any(p.kind is inspect.Parameter.VAR_KEYWORD
                   for p in parameters.values()))
        if takes_dry_run:
            kwargs = {"dry_run": bool(dry_run)}
    except (TypeError, ValueError):
        if dry_run:
            kwargs = {"dry_run": True}
    try:
        return check(draft, run_context, **kwargs)
    except TypeError:
        pass
    try:
        return check(draft, run_context)
    except TypeError:
        return check(draft)


def _default_validator(evidence, run_context, dry_run=False):
    """Part-11 validator, imported lazily to avoid a hard cycle."""
    from src.validate import validate as _validate  # noqa: PLC0415

    return _validate(evidence, run_context, dry_run=dry_run)


def _normalise_report(report):
    """Acceptance/errors from a validator report, or a fault string."""
    if not isinstance(report, dict):
        return None, "validation returned no structured report"
    errors = report.get("errors") or []
    if report.get("accepted"):
        if not isinstance(errors, list):
            errors = []
        return {"accepted": True, "errors": errors,
                "result": report.get("result"),
                "result_path": report.get("result_path")}, ""
    if not isinstance(errors, list):
        errors = [{"code": "VALIDATOR_FAULT", "field": "submission",
                   "detail": "validation returned unstructured errors"}]
    return {"accepted": False, "errors": errors}, ""


def collect_run_context(run_dir, run_id=None) -> dict:
    """The small run-context shape the validator normalises.

    ``run_dir``/``run_id``, the ``input/timing.json`` report (when
    readable), the on-disk artifact set, the produced-files log when
    it exists (authoritative for V2/V8), and the blind-check record
    artifacts from ``workspace/mask_checks.json`` (part 11 ``V3``).
    """
    base = Path(str(run_dir))
    try:
        timing = read_timing(run_dir)
    except ValueError:
        timing = {}
    artifacts: set = set()
    try:
        artifacts = {str(p.relative_to(base)) for p in
                     (base / str(_config.ARTIFACTS_DIR_NAME)
                      ).rglob("*") if p.is_file()}
    except OSError:
        pass
    context = {
        "run_dir": str(run_dir),
        "run_id": (str(run_id) if run_id is not None else base.name),
        "timing": timing,
        "artifacts": sorted(artifacts),
    }
    produced_log = (base / str(_config.WORKSPACE_DIR_NAME)
                    / "produced_files.json")
    if produced_log.is_file():
        context["produced_files"] = read_produced(run_dir)
    try:
        records = json.loads(
            (base / str(_config.WORKSPACE_DIR_NAME)
             / "mask_checks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        records = []
    if isinstance(records, list):
        context["mask_checks"] = [
            str(r.get("artifact")) for r in records
            if isinstance(r, dict) and r.get("artifact")]
    return context


def format_errors(errors) -> str:
    """Readable rejection: ``CODE field: detail`` per error.

    Validator ``V1`` errors first (they gate the rest), then grouped
    by code in first-appearance order; at most 40 lines, then
    ``+N more of CODE``.
    """
    ordered: list = []
    rest = list(errors or [])
    ordered.extend([e for e in rest
                    if isinstance(e, dict) and e.get("code") == "V1"])
    seen: set = set()
    for error in rest:
        if not isinstance(error, dict) or error.get("code") == "V1":
            continue
        code = str(error.get("code") or "error")
        if code in seen:
            continue
        seen.add(code)
        ordered.extend([e for e in rest
                        if isinstance(e, dict)
                        and str(e.get("code") or "error") == code])
    ordered.extend([e for e in rest if not isinstance(e, dict)])
    lines = []
    for error in ordered:
        if isinstance(error, dict):
            lines.append(f"{error.get('code', 'error')} "
                         f"{error.get('field', '?')}: "
                         f"{error.get('detail', '')}")
        else:
            lines.append(str(error))
    if len(lines) > MAX_SUMMARY_ERRORS:
        head = lines[:MAX_SUMMARY_ERRORS]
        omitted = ordered[MAX_SUMMARY_ERRORS:]
        code = (omitted[0].get("code", "error")
                if isinstance(omitted[0], dict) else "error")
        head.append(f"+{len(omitted)} more of {code}")
        return "\n".join(head)
    return "\n".join(lines)


def _save_errors(run_dir, turn, errors) -> str:
    # The name is fixed by the spec (no <n> suffix): one error list
    # per turn, overwritten when a turn submits twice.
    rel = f"artifacts/t{int(turn)}_submit_errors.json"
    path = run_path(run_dir, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(errors, indent=2) + "\n",
                    encoding="utf-8")
    append_produced(run_dir, [rel])
    return rel


def _load_evidence_path(run_dir, evidence_path, dry_run) -> tuple:
    """Parse ``evidence_path`` into ``(evidence, fault)``.

    The path must be run-relative under ``workspace/`` (the file the
    agent wrote with ``run_python``). ``fault`` is a ready-made
    ``bad_arguments`` result when the path is unusable; otherwise
    ``(parsed, None)``.
    """
    reason = check_run_path(evidence_path)
    if reason is not None:
        return None, err_result(
            "bad_arguments",
            f"evidence_path is not a clean run-relative path: {reason}",
            metrics={"dry_run": bool(dry_run)})
    if not str(evidence_path).startswith("workspace/"):
        return None, err_result(
            "bad_arguments",
            f"evidence_path must live under workspace/, got "
            f"{evidence_path!r}",
            metrics={"dry_run": bool(dry_run)})
    try:
        raw = run_path(run_dir, evidence_path).read_text(encoding="utf-8")
    except OSError as exc:
        return None, err_result(
            "bad_arguments",
            f"evidence_path is unreadable: {exc}",
            metrics={"dry_run": bool(dry_run)})
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        return None, err_result(
            "bad_arguments",
            f"evidence_path is not valid JSON: {exc}",
            metrics={"dry_run": bool(dry_run)})
    if not isinstance(parsed, dict):
        return None, err_result(
            "bad_arguments",
            f"evidence_path must hold a JSON object, got "
            f"{type(parsed).__name__}",
            metrics={"dry_run": bool(dry_run)})
    return parsed, None


def _save_evidence_copy(run_dir, turn, evidence_path) -> str:
    """Copy the submitted file, byte for byte, into ``artifacts/``.

    Returns the run-relative artifact name; the result names it so a
    retyped curve can never silently replace the measured one.
    """
    rel = f"artifacts/t{int(turn)}_evidence.json"
    target = run_path(run_dir, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(run_path(run_dir, evidence_path).read_bytes())
    append_produced(run_dir, [rel])
    return rel


def submit(run_dir, turn, evidence=None, validator=None,
           dry_run=False, evidence_path=None) -> dict:
    """Write the evidence draft, validate it, accept or report errors.

    Besides inline ``evidence``, ``evidence_path`` accepts a
    run-relative path to a JSON file under ``workspace/`` that the
    agent wrote with ``run_python`` — prefer it whenever the evidence
    holds arrays (tracks, fit curves, outlines). Exactly one of the
    two is given; both or neither is a readable rejection. Dry runs
    work the same way.

    ``validator`` is ``(evidence, run_context[, dry_run]) ->
    {"accepted", "errors", ...}`` (part 11); narrower fakes are
    honoured by falling back to fewer arguments. On acceptance the
    metrics carry ``accepted: True`` and ``result_path``; on
    rejection the summary carries every error as
    ``CODE field: detail`` and the metrics carry the structured
    ``errors`` list plus the ``errors_artifact`` file holding the
    full list. With ``dry_run=True`` the same checks run but no
    submission is written and the call is not a submit attempt.
    """
    given_inline = evidence is not None
    given_path = evidence_path is not None
    if given_inline and given_path:
        return err_result(
            "bad_arguments",
            "give exactly one of evidence or evidence_path, not both; "
            "prefer evidence_path when the evidence holds arrays",
            metrics={"dry_run": bool(dry_run)})
    if not given_inline and not given_path:
        return err_result(
            "bad_arguments",
            "submit needs evidence: either an inline evidence object "
            "or evidence_path to a workspace/ JSON file",
            metrics={"dry_run": bool(dry_run)})
    evidence_copy_rel = None
    if given_path:
        if not isinstance(evidence_path, str):
            return err_result(
                "bad_arguments",
                f"evidence_path must be a run-relative path string, got "
                f"{type(evidence_path).__name__}",
                metrics={"dry_run": bool(dry_run)})
        evidence, fault = _load_evidence_path(run_dir, evidence_path,
                                              dry_run)
        if fault is not None:
            return fault
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except ValueError as exc:
            return err_result("bad_arguments",
                              f"evidence is not valid JSON: {exc}",
                              metrics={"dry_run": bool(dry_run)})
    if not isinstance(evidence, dict):
        return err_result(
            "bad_arguments",
            f"evidence must be a JSON object, got "
            f"{type(evidence).__name__}",
            metrics={"dry_run": bool(dry_run)})
    if given_path:
        try:
            evidence_copy_rel = _save_evidence_copy(run_dir, turn,
                                                    evidence_path)
        except OSError as exc:
            return err_result("run_unwritable",
                              f"cannot copy submitted evidence: {exc}",
                              metrics={"dry_run": bool(dry_run)})
    check = validator if validator is not None else _default_validator
    if dry_run:
        used = read_dry_run_count(run_dir)
        if used >= int(_config.MAX_DRY_RUNS_PER_RUN):
            return err_result(
                "dry_run_capped",
                f"dry-run budget spent ({used} of "
                f"{int(_config.MAX_DRY_RUNS_PER_RUN)} used); call submit "
                "with dry_run false to spend a submit attempt",
                metrics={"dry_run": True, "dry_runs_used": used,
                         "dry_runs_max": int(
                             _config.MAX_DRY_RUNS_PER_RUN)})
        used = _bump_dry_runs(run_dir)
        try:
            report = _call_validator(check, evidence,
                                     collect_run_context(run_dir),
                                     dry_run=True)
        except Exception as exc:  # noqa: BLE001 — validator never crashes us
            return err_result("validator_fault",
                              "validation failed to run: "
                              f"{type(exc).__name__}: {exc}",
                              metrics={"dry_run": True,
                                       "dry_runs_used": used})
        outcome, fault = _normalise_report(report)
        if outcome is None:
            return err_result("validator_fault", fault,
                              metrics={"dry_run": True,
                                       "dry_runs_used": used})
        if outcome["accepted"]:
            errors_rel = _save_errors(run_dir, turn, [])
            dry_files = ([evidence_copy_rel] if evidence_copy_rel
                         else []) + [errors_rel]
            return ok_result(
                "submission accepted (dry run): no result written; "
                "repeat with dry_run false to submit",
                files=dry_files,
                metrics={"accepted": True, "errors": [],
                         "dry_run": True, "dry_runs_used": used,
                         "result": None, "result_path": None,
                         "errors_artifact": errors_rel,
                         "evidence_artifact": evidence_copy_rel})
        errors = outcome["errors"]
        errors_rel = _save_errors(run_dir, turn, list(errors))
        head = format_errors(errors)
        summary = (f"dry run rejected with {len(errors)} error(s); "
                   "nothing written" + (f":\n{head}" if head else ""))
        dry_files = ([evidence_copy_rel] if evidence_copy_rel
                     else []) + [errors_rel]
        return err_result(
            "submit_rejected", summary,
            files=dry_files,
            metrics={"accepted": False, "errors": list(errors),
                     "error_count": len(errors),
                     "dry_run": True, "dry_runs_used": used,
                     "errors_artifact": errors_rel,
                     "evidence_artifact": evidence_copy_rel})
    try:
        target = run_path(run_dir, "workspace/submission.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(evidence, indent=2,
                                     sort_keys=True) + "\n",
                          encoding="utf-8")
    except OSError as exc:
        return err_result("run_unwritable",
                          f"cannot write submission.json: {exc}",
                          metrics={"dry_run": False})
    append_produced(run_dir, ["workspace/submission.json"])
    try:
        report = _call_validator(check, evidence,
                                 collect_run_context(run_dir),
                                 dry_run=False)
    except Exception as exc:  # noqa: BLE001 — validator never crashes us
        return err_result("validator_fault",
                          "validation failed to run: "
                          f"{type(exc).__name__}: {exc}",
                          files=["workspace/submission.json"],
                          metrics={"dry_run": False})
    outcome, fault = _normalise_report(report)
    if outcome is None:
        return err_result("validator_fault", fault,
                          files=["workspace/submission.json"],
                          metrics={"dry_run": False})
    if outcome["accepted"]:
        # Every submit call saves its error list (empty here) and
        # names the file (part 07 §§11–12).
        errors_rel = _save_errors(run_dir, turn, [])
        real_files = ["workspace/submission.json"] + (
            [evidence_copy_rel] if evidence_copy_rel else []) + [errors_rel]
        return ok_result(
            "submission accepted: result at "
            f"{outcome['result_path']}" if outcome["result_path"]
            else "submission accepted; the run ends here",
            files=real_files,
            metrics={"accepted": True, "errors": [],
                     "result": outcome["result"],
                     "result_path": outcome["result_path"],
                     "dry_run": False,
                     "errors_artifact": errors_rel,
                     "evidence_artifact": evidence_copy_rel})
    errors = outcome["errors"]
    errors_rel = _save_errors(run_dir, turn, list(errors))
    head = format_errors(errors)
    summary = (f"submission rejected with {len(errors)} error(s):\n{head}"
               if head else
               f"submission rejected with {len(errors)} error(s)")
    real_files = ["workspace/submission.json"] + (
        [evidence_copy_rel] if evidence_copy_rel else []) + [errors_rel]
    return err_result(
        "submit_rejected", summary,
        files=real_files,
        metrics={"accepted": False, "dry_run": False,
                 "errors": list(errors), "error_count": len(errors),
                 "errors_artifact": errors_rel,
                 "evidence_artifact": evidence_copy_rel})
