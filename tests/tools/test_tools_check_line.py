# generated from brief/07 · part 07 owns this file
"""``check_line``: a blind look at a measured line (part 07 §19)."""

from __future__ import annotations

import json

import pytest

from src.tools import check_line
from src.tools import schemas


def _blind_pair(requests, state):
    """Two-phase stub: image call -> descriptions, text call -> votes."""

    def _spark(request):
        requests.append(dict(request))
        if "image" in request:
            return {"descriptions": ["stub end-to-end description"
                                     ] * int(state["n"]),
                    "usage": {"input_tokens": 10, "cached_tokens": 0,
                              "output_tokens": 5,
                              "reasoning_tokens": 0}}
        claims = request.get("claims", [])
        votes = list(state.get("agrees", [True] * len(claims)))
        return {"results": [{"agrees": bool(votes[i])
                             if i < len(votes) else True,
                             "why": "the ends match the claim."}
                            for i in range(len(claims))],
                "usage": {"input_tokens": 8, "cached_tokens": 0,
                          "output_tokens": 4, "reasoning_tokens": 0}}

    return _spark


def _one_line():
    return [{"x1": 10, "y1": 20, "x2": 100, "y2": 20,
             "claim": "bar width: left edge to right edge"}]


def test_overlay_is_drawn_by_tool_on_the_given_frame(make_run):
    import cv2
    import numpy as np

    run = make_run(frames=40)
    requests: list = []
    stub = _blind_pair(requests, {"n": 1})
    result = check_line.check_line(str(run), 0, frame=5,
                                   lines=_one_line(),
                                   spark_client=stub)
    assert result["ok"], result
    overlay_rel = result["metrics"]["overlay_artifact"]
    assert overlay_rel.startswith("artifacts/t0_check_line_")
    assert overlay_rel in result["files"]
    raw = (run / overlay_rel).read_bytes()
    grid = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8),
                        cv2.IMREAD_COLOR)
    assert grid is not None and grid.shape[:2] == (120, 160)
    capture = cv2.VideoCapture(str(run / "input" / "clip.mp4"))
    try:
        capture.set(cv2.CAP_PROP_POS_FRAMES, 5.0)
        ok, source = capture.read()
    finally:
        capture.release()
    assert ok and source is not None
    assert not bool((grid == source).all()), \
        "the overlay must carry the tool's own drawn line"


def test_agent_supplied_image_is_rejected(make_run):
    run = make_run(frames=40)
    requests: list = []
    stub = _blind_pair(requests, {"n": 1})
    smuggled = check_line.check_line(
        str(run), 0, frame=5, lines=_one_line(), spark_client=stub,
        overlay_artifact="artifacts/t0_view_frames_0.jpg")
    assert not smuggled["ok"]
    assert not requests, "no blind call may run on a supplied image"
    keyed = [{"x1": 10, "y1": 20, "x2": 100, "y2": 20,
              "claim": "bar width", "image": "artifacts/x.png"}]
    keyed_result = check_line.check_line(
        str(run), 0, frame=5, lines=keyed, spark_client=stub)
    assert not keyed_result["ok"]
    assert not requests


def test_blind_call_carries_image_without_claim(make_run):
    run = make_run(frames=40)
    requests: list = []
    stub = _blind_pair(requests, {"n": 2})
    lines = [{"x1": 10, "y1": 20, "x2": 100, "y2": 20,
              "claim": "bar width: left edge to right edge"},
             {"x1": 10, "y1": 40, "x2": 60, "y2": 40,
              "claim": "inner mark: left tip to right tip"}]
    result = check_line.check_line(str(run), 1, frame=7,
                                   lines=lines, spark_client=stub)
    assert result["ok"], result
    assert len(requests) == 2
    first, second = requests
    assert isinstance(first.get("image"), bytes) and first["image"]
    assert first["question"] == check_line.BLIND_LOOK_QUESTION
    assert "claim" not in {str(key).lower() for key in first}
    assert "claim" not in str(first.get("question", "")).lower()
    assert "image" not in second
    assert not any(isinstance(value, bytes)
                   for value in second.values())
    assert second["claims"] == [line["claim"] for line in lines]
    assert second["question"] == check_line.MATCH_QUESTION


def test_record_fields_and_jsonl_append(make_run, ledger):
    run = make_run(frames=40)
    requests: list = []
    stub = _blind_pair(requests, {"n": 1, "agrees": [True]})
    result = check_line.check_line(str(run), 2, frame=9,
                                   lines=_one_line(),
                                   spark_client=stub,
                                   ledger=ledger)
    assert result["ok"], result
    assert result["metrics"]["descriptions"] == [
        "stub end-to-end description"]
    assert result["metrics"]["agrees"] == [True]
    record_rel = result["metrics"]["record_artifact"]
    record = json.loads((run / record_rel).read_text(
        encoding="utf-8"))
    assert record["frame"] == 9
    assert len(record["lines"]) == 1
    entry = record["lines"][0]
    assert entry["x1"] == 10 and entry["y1"] == 20
    assert entry["x2"] == 100 and entry["y2"] == 20
    assert entry["claim"] == "bar width: left edge to right edge"
    assert entry["description"] == "stub end-to-end description"
    assert entry["agrees"] is True
    assert isinstance(entry["why"], str) and entry["why"]
    journal = (run / "artifacts" / "line_checks.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert len(journal) == 1
    assert json.loads(journal[0]) == record
    # Both Spark calls go on the ledger like check_mask.
    assert ledger.mask_checks == 2


def test_cap_refuses_the_seventh_call(make_run):
    run = make_run(frames=40)
    requests: list = []
    stub = _blind_pair(requests, {"n": 1})
    for turn in range(check_line.MAX_LINE_CHECKS):
        result = check_line.check_line(
            str(run), turn, frame=turn % 40, lines=_one_line(),
            spark_client=stub)
        assert result["ok"], (turn, result)
    refused = check_line.check_line(str(run), 99, frame=1,
                                    lines=_one_line(),
                                    spark_client=stub)
    assert not refused["ok"]
    assert refused["error"]["code"] == "cap_spent"
    assert str(check_line.MAX_LINE_CHECKS) in refused["summary"]
    assert len(requests) == 2 * check_line.MAX_LINE_CHECKS


def test_bad_inputs_are_rejected(make_run):
    run = make_run(frames=40)
    requests: list = []
    stub = _blind_pair(requests, {"n": 1})
    cases = [
        {"frame": 999, "lines": _one_line()},
        {"frame": -1, "lines": _one_line()},
        {"frame": True, "lines": _one_line()},
        {"frame": 5, "lines": []},
        {"frame": 5, "lines": _one_line() * 4},
        {"frame": 5, "lines": [{"x1": 10, "y1": 20, "x2": 100,
                                "y2": 20, "claim": "  "}]},
        {"frame": 5, "lines": [{"x1": 10, "y1": 20, "x2": 10,
                                "y2": 20, "claim": "a point"}]},
        {"frame": 5, "lines": [{"x1": 10, "y1": 20, "x2": 1000,
                                "y2": 20, "claim": "off frame"}]},
        {"frame": 5, "lines": [{"x1": "a", "y1": 20, "x2": 100,
                                "y2": 20, "claim": "not numeric"}]},
    ]
    for case in cases:
        result = check_line.check_line(str(run), 0, spark_client=stub,
                                       **case)
        assert not result["ok"], case
    assert not requests
    assert check_line.line_check_count(str(run)) == 0
    nobackend = check_line.check_line(str(run), 0, frame=5,
                                      lines=_one_line(),
                                      spark_client=None)
    assert not nobackend["ok"]
    assert nobackend["error"]["code"] == "blind_unavailable"


def test_parse_lines_rejects_images_and_points():
    good = check_line.parse_lines(_one_line())
    assert good[0]["claim"].startswith("bar width")
    with pytest.raises(ValueError):
        check_line.parse_lines([{"x1": 0, "y1": 0, "x2": 1, "y2": 1,
                                 "claim": "ok",
                                 "overlay": "artifacts/x.png"}])
    with pytest.raises(ValueError):
        check_line.parse_lines([{"x1": 5, "y1": 5, "x2": 5, "y2": 5,
                                 "claim": "a point"}])


def test_answer_seeking_claim_is_refused(make_run):
    run = make_run(frames=40)
    requests: list = []
    stub = _blind_pair(requests, {"n": 1})
    lines = [{"x1": 10, "y1": 20, "x2": 100, "y2": 20,
              "claim": "jump height of the viral video debunked"}]
    result = check_line.check_line(str(run), 0, frame=5,
                                   lines=lines, spark_client=stub,
                                   classifier=lambda query: "no")
    assert not result["ok"]
    assert result["error"]["code"] == "query_rejected"
    assert not requests, "a refused claim never reaches Spark"


def test_classifier_yes_rejects_when_wired(make_run):
    run = make_run(frames=40)
    requests: list = []
    stub = _blind_pair(requests, {"n": 1})
    refused = check_line.check_line(
        str(run), 0, frame=5, lines=_one_line(), spark_client=stub,
        classifier=lambda query: "yes")
    assert not refused["ok"]
    assert refused["error"]["code"] == "query_rejected"
    assert not requests
    passed = check_line.check_line(
        str(run), 0, frame=5, lines=_one_line(), spark_client=stub,
        classifier=lambda query: "no")
    assert passed["ok"], passed


def test_blind_failure_is_a_tool_error(make_run, ledger):
    run = make_run(frames=40)

    def _boom(request):
        raise RuntimeError("model down")

    result = check_line.check_line(str(run), 0, frame=5,
                                   lines=_one_line(),
                                   spark_client=_boom,
                                   ledger=ledger)
    assert not result["ok"]
    assert result["error"]["code"] == "blind_failed"
    assert ledger.mask_checks == 0
    malformed = check_line.check_line(
        str(run), 0, frame=5, lines=_one_line(),
        spark_client=lambda request: {"nope": []}, ledger=ledger)
    assert not malformed["ok"]
    assert malformed["error"]["code"] == "blind_malformed"
    assert ledger.mask_checks == 0


def test_line_kinds_sent_to_blind_client(make_run):
    run = make_run(frames=40)
    requests: list = []
    stub = _blind_pair(requests, {"n": 2})
    lines = [{"x1": 10, "y1": 20, "x2": 100, "y2": 20,
              "claim": "bar width: left edge to right edge"},
             {"x1": 10, "y1": 40, "x2": 60, "y2": 40,
              "claim": "inner mark: left tip to right tip"}]
    result = check_line.check_line(str(run), 1, frame=7,
                                   lines=lines, spark_client=stub)
    assert result["ok"], result
    assert len(requests) == 2
    first, second = requests
    assert set(first) == {"kind", "image", "question", "n_lines"}
    assert first["kind"] == "line_look"
    assert first["n_lines"] == 2
    assert set(second) == {"kind", "descriptions", "claims",
                           "question"}
    assert second["kind"] == "line_match"
    assert second["descriptions"] == ["stub end-to-end description"] * 2


def test_failed_call_error_is_blind_failed_without_retry(make_run,
                                                         ledger):
    from src.accounting import FailedCallError

    run = make_run(frames=40)

    def _malformed(request):
        raise FailedCallError("line look returned no structured "
                              "answer")

    result = check_line.check_line(str(run), 0, frame=5,
                                   lines=_one_line(),
                                   spark_client=_malformed,
                                   ledger=ledger)
    assert not result["ok"]
    assert result["error"]["code"] == "blind_failed"
    assert "line look returned no structured answer" in \
        result["error"]["detail"]
    assert "do not retry the identical call" in result["summary"]
    assert result["metrics"]["retry_once"] is False
    assert ledger.mask_checks == 0
    assert check_line.line_check_count(str(run)) == 0


def test_transport_error_may_retry_once(make_run, ledger):
    run = make_run(frames=40)

    def _down(request):
        raise ConnectionError("connection reset by peer")

    result = check_line.check_line(str(run), 0, frame=5,
                                   lines=_one_line(),
                                   spark_client=_down,
                                   ledger=ledger)
    assert not result["ok"]
    assert result["error"]["code"] == "blind_failed"
    assert "retry this call once" in result["summary"]
    assert result["metrics"]["retry_once"] is True
    assert ledger.mask_checks == 0
    assert check_line.line_check_count(str(run)) == 0


def test_failures_do_not_consume_cap(make_run):
    from src.accounting import FailedCallError

    run = make_run(frames=40)

    def _flaky(request):
        raise FailedCallError("line look returned an empty "
                              "description")

    for turn in range(3):
        refused = check_line.check_line(
            str(run), turn, frame=5, lines=_one_line(),
            spark_client=_flaky)
        assert not refused["ok"]
        assert refused["error"]["code"] == "blind_failed"
    requests: list = []
    stub = _blind_pair(requests, {"n": 1})
    for turn in range(check_line.MAX_LINE_CHECKS):
        result = check_line.check_line(
            str(run), turn, frame=turn % 40, lines=_one_line(),
            spark_client=stub)
        assert result["ok"], (turn, result)
    refused = check_line.check_line(str(run), 99, frame=1,
                                    lines=_one_line(),
                                    spark_client=stub)
    assert not refused["ok"]
    assert refused["error"]["code"] == "cap_spent"


def test_blind_questions_ask_parts_not_identity():
    assert "numbered line" in check_line.BLIND_LOOK_QUESTION
    assert "where it starts" in check_line.BLIND_LOOK_QUESTION
    assert "Do not guess what the video is" in \
        check_line.BLIND_LOOK_QUESTION
    assert "claim" not in check_line.BLIND_LOOK_QUESTION.lower()
    assert "yes or no" in check_line.MATCH_QUESTION


def test_blind_questions_name_view_and_dimension():
    """Part 07 §22: the look asks the side and the dimension.

    A Moon run measured a "width" with a line that spans the
    figure's depth (seen from the side); the look must say both so
    the match can judge the dimension, not just the endpoints.
    """
    assert "from which side" in check_line.BLIND_LOOK_QUESTION
    assert "along which of its own dimensions" in \
        check_line.BLIND_LOOK_QUESTION
    for word in ("front", "back", "side", "top", "unclear",
                 "height", "width", "depth"):
        assert word in check_line.BLIND_LOOK_QUESTION, word
    assert "claim" not in check_line.BLIND_LOOK_QUESTION.lower()
    assert "along that same dimension" in check_line.MATCH_QUESTION


def test_dimension_reaches_match_and_record(make_run):
    """Part 07 §22: a depth look against a width claim.

    The stub look returns ``dimension: "depth"`` for the claim
    "suited figure width". The stub match must then receive a
    question containing "along that same dimension", and every
    line of the result JSON must hold ``view`` and ``dimension``.
    """
    run = make_run(frames=40)
    requests: list = []

    def _spark(request):
        requests.append(dict(request))
        if "image" in request:
            return {
                "descriptions": [{
                    "description": "the line spans the suited figure "
                                   "from chest to backpack",
                    "view": "side",
                    "dimension": "depth",
                }],
                "usage": {"input_tokens": 10, "cached_tokens": 0,
                          "output_tokens": 5, "reasoning_tokens": 0},
            }
        return {"results": [{"agrees": False,
                             "why": "the claim says width but the "
                                    "line runs along the depth."}],
                "usage": {"input_tokens": 8, "cached_tokens": 0,
                          "output_tokens": 4, "reasoning_tokens": 0}}

    lines = [{"x1": 10, "y1": 20, "x2": 100, "y2": 20,
              "claim": "suited figure width: left edge to right"}]
    result = check_line.check_line(str(run), 0, frame=5,
                                   lines=lines, spark_client=_spark)
    assert result["ok"], result
    assert len(requests) == 2
    first, second = requests
    assert "claim" not in {str(key).lower() for key in first}
    assert "along that same dimension" in second["question"]
    assert "depth" in second["descriptions"][0]
    entry = json.loads((run / result["metrics"][
        "record_artifact"]).read_text(encoding="utf-8"))["lines"][0]
    assert entry["view"] == "side"
    assert entry["dimension"] == "depth"
    assert entry["description"].startswith("the line spans")
    assert result["metrics"]["views"] == ["side"]
    assert result["metrics"]["dimensions"] == ["depth"]
    assert result["metrics"]["agrees"] == [False]


def test_bare_string_look_defaults_to_unclear(make_run):
    """A pre-§22 string look still works; view/dimension read unclear.

    The blind client passes bare strings through, so the tool must
    accept them: the record gains ``view``/``dimension`` (both
    "unclear") and the match receives the raw string unchanged.
    """
    run = make_run(frames=40)
    requests: list = []
    stub = _blind_pair(requests, {"n": 1})
    result = check_line.check_line(str(run), 0, frame=5,
                                   lines=_one_line(),
                                   spark_client=stub)
    assert result["ok"], result
    entry = json.loads((run / result["metrics"][
        "record_artifact"]).read_text(encoding="utf-8"))["lines"][0]
    assert entry["view"] == "unclear"
    assert entry["dimension"] == "unclear"
    assert result["metrics"]["views"] == ["unclear"]
    assert result["metrics"]["dimensions"] == ["unclear"]
    assert requests[1]["descriptions"] == ["stub end-to-end description"]


def test_object_look_without_description_is_malformed(make_run,
                                                      ledger):
    """A per-line object with an empty description is blind_malformed."""
    run = make_run(frames=40)

    def _spark(request):
        if "image" in request:
            return {"descriptions": [{"description": "  ",
                                      "view": "side",
                                      "dimension": "depth"}]}
        raise AssertionError("the match must not run on no look")

    result = check_line.check_line(str(run), 0, frame=5,
                                   lines=_one_line(),
                                   spark_client=_spark,
                                   ledger=ledger)
    assert not result["ok"]
    assert result["error"]["code"] == "blind_malformed"
    assert ledger.mask_checks == 0
    assert check_line.line_check_count(str(run)) == 0


def test_check_line_is_published_in_schemas():
    assert "check_line" in schemas.TOOL_NAMES
    assert set(schemas.EXPECTED_PARAMS["check_line"]) == {
        "frame", "lines"}
    by_name = {entry["name"]: entry
               for entry in schemas.TOOL_SCHEMAS}
    assert by_name["check_line"]["parameters"]["required"] == [
        "frame", "lines"]
    assert "line_checks.jsonl" in \
        by_name["check_line"]["parameters"]["description"]


def _sse_completed_text(text, **usage):
    """One minimal SSE stream with a terminal ``response.completed``."""
    terminal = {
        "type": "response.completed",
        "sequence_number": 1,
        "response": {
            "id": "resp_stub",
            "output": [{
                "type": "message", "id": "msg_1",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }],
            "usage": {
                "input_tokens": usage.get("input_tokens", 50),
                "input_tokens_details": {
                    "cached_tokens": usage.get("cached_tokens", 0)},
                "output_tokens": usage.get("output_tokens", 20),
                "output_tokens_details": {
                    "reasoning_tokens": usage.get(
                        "reasoning_tokens", 0)},
            },
        },
    }
    body = ('event: response.created\n'
            'data: {"type": "response.created", '
            '"sequence_number": 0}\n\n'
            'event: response\ndata: ' + json.dumps(terminal)
            + '\n\n' + 'data: [DONE]\n\n')
    return body.encode()


class _LineStubServer:
    """Minimal stub of ``POST /responses`` for the joint test.

    Answers the blind client's ``line_look``/``line_match`` schema
    shapes from the request's own format name and ``maxItems``. In
    ``mask`` mode it always answers the mask-check shape, which the
    real client must reject with ``FailedCallError``.
    """

    def __init__(self, mode="line", agrees=()):
        from http.server import (  # noqa: PLC0415 — test-only server
            BaseHTTPRequestHandler, ThreadingHTTPServer)
        import threading

        self.mode = mode
        self.agrees = list(agrees)
        self.log = []
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: D102 — quiet
                pass

            def do_POST(self):  # noqa: D102 — stub endpoint
                length = int(self.headers.get("Content-Length")
                             or 0)
                raw = (self.rfile.read(length) if length else b"")
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except ValueError:
                    body = {}
                outer.log.append(body)
                if self.path != "/responses":
                    payload = b"{}"
                    self.send_response(404)
                    self.send_header("Content-Length",
                                     str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                payload = _sse_completed_text(
                    json.dumps(outer._answer(body)))
                self.send_response(200)
                self.send_header("Content-Type",
                                 "text/event-stream")
                self.send_header("Content-Length",
                                 str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0),
                                           _Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def _answer(self, body):
        if self.mode == "mask":
            return {"description": "covers the bright bar",
                    "alternatives": ["covers the whole bar"]}
        if self.mode == "line_objects":
            name = ((body.get("text") or {}).get("format") or {}
                    ).get("name", "")
            if name == "line_look":
                return {"descriptions": [
                    {"description": "stub line spans the bar edge",
                     "view": "side",
                     "dimension": "depth"}]}
            votes = list(self.agrees) or [True]
            return {"results": [
                {"agrees": bool(votes[0]),
                 "why": "stub: the dimension matches the claim."}]}
        name = ((body.get("text") or {}).get("format") or {}
                ).get("name", "")
        schema = ((body.get("text") or {}).get("format") or {}
                  ).get("schema", {})
        if name == "line_look":
            count = (((schema.get("properties") or {})
                      .get("descriptions") or {}).get("maxItems")
                     or 1)
            return {"descriptions": [
                f"stub line {i + 1} spans the bar edge"
                for i in range(int(count))]}
        count = (((schema.get("properties") or {}).get("results")
                  or {}).get("maxItems") or 1)
        votes = list(self.agrees) or [True] * int(count)
        return {"results": [
            {"agrees": bool(votes[i]) if i < len(votes) else True,
             "why": "stub: the ends match the claim."
             if (votes[i] if i < len(votes) else True)
             else "stub: the description names another part."}
            for i in range(int(count))]}

    @property
    def base_url(self):
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)


def test_joint_real_blind_client_end_to_end(make_run, ledger):
    """``check_line`` through the real blind client (part 07 §20).

    The server answers both line kinds with schema-shaped JSON, so
    the tool succeeds, writes the record to ``line_checks.jsonl``,
    and takes ``agrees`` from the stub.
    """
    from src.clients.blind import make_blind_client

    run = make_run(frames=40)
    server = _LineStubServer(mode="line", agrees=[True, False])
    try:
        blind = make_blind_client("test-key",
                                  base_url=server.base_url,
                                  timeout=10,
                                  sleep=lambda seconds: None)
        lines = [{"x1": 10, "y1": 20, "x2": 100, "y2": 20,
                  "claim": "bar width: left edge to right edge"},
                 {"x1": 10, "y1": 40, "x2": 60, "y2": 40,
                  "claim": "inner mark: left tip to right tip"}]
        result = check_line.check_line(str(run), 3, frame=9,
                                       lines=lines,
                                       spark_client=blind,
                                       ledger=ledger)
    finally:
        server.stop()
    assert result["ok"], result
    assert result["metrics"]["agrees"] == [True, False]
    assert result["metrics"]["descriptions"] == [
        "stub line 1 spans the bar edge",
        "stub line 2 spans the bar edge"]
    journal = (run / "artifacts" / "line_checks.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert len(journal) == 1
    record = json.loads(journal[0])
    assert record["frame"] == 9
    assert [entry["agrees"] for entry in record["lines"]] == [
        True, False]
    assert all(entry["description"] and entry["why"]
               for entry in record["lines"])
    assert ledger.mask_checks == 2
    assert len(server.log) == 2, \
        "both blind calls reach the stub HTTP server"


def test_joint_object_look_end_to_end(make_run, ledger):
    """Part 07 §22 through the real blind client: object-shaped look.

    The server answers the line-look schema with per-line objects
    carrying ``view`` and ``dimension``; the tool records them in
    ``line_checks.jsonl`` and the match judges the annotated text.
    """
    from src.clients.blind import make_blind_client

    run = make_run(frames=40)
    server = _LineStubServer(mode="line_objects", agrees=[True])
    try:
        blind = make_blind_client("test-key",
                                  base_url=server.base_url,
                                  timeout=10,
                                  sleep=lambda seconds: None)
        result = check_line.check_line(
            str(run), 4, frame=9,
            lines=[{"x1": 10, "y1": 20, "x2": 100, "y2": 20,
                    "claim": "bar depth: front edge to back edge"}],
            spark_client=blind, ledger=ledger)
    finally:
        server.stop()
    assert result["ok"], result
    assert result["metrics"]["views"] == ["side"]
    assert result["metrics"]["dimensions"] == ["depth"]
    assert result["metrics"]["agrees"] == [True]
    journal = (run / "artifacts" / "line_checks.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert len(journal) == 1
    record = json.loads(journal[0])
    assert record["lines"][0]["view"] == "side"
    assert record["lines"][0]["dimension"] == "depth"
    assert ledger.mask_checks == 2


def test_joint_mask_shape_yields_blind_failed(make_run):
    """A mask-check-shaped stub reply is ``blind_failed``, not a crash.

    The live failure of §20: the tool and the client disagreed on the
    reply shape. With the kinds wired, the real client raises
    ``FailedCallError`` on the mask shape and the tool surfaces it.
    """
    from src.clients.blind import make_blind_client

    run = make_run(frames=40)
    server = _LineStubServer(mode="mask")
    try:
        blind = make_blind_client("test-key",
                                  base_url=server.base_url,
                                  timeout=10,
                                  sleep=lambda seconds: None)
        result = check_line.check_line(str(run), 0, frame=5,
                                       lines=_one_line(),
                                       spark_client=blind)
    finally:
        server.stop()
    assert not result["ok"]
    assert result["error"]["code"] == "blind_failed"
    assert "do not retry the identical call" in result["summary"]
    assert check_line.line_check_count(str(run)) == 0
