"""Offline probe 7: the API key never leaks into files, logs, or exceptions."""

from __future__ import annotations

import json
import logging

import pytest

from physics_proof.config import Settings
from physics_proof.ledger import Ledger
from physics_proof.meta_client import ApiError, MetaClient

from fake_server import start_fake_server

SENTINEL = "SENTINEL-KEY-9f8e7d6c5b4a"


def test_key_never_leaks(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv("META_API_KEY", SENTINEL)
    run_path = tmp_path / "run.jsonl"
    global_path = tmp_path / "global.jsonl"
    ledger = Ledger(run_path, global_path)
    error_body = json.dumps({"error": {"message": "bad request"}}).encode()
    server, base_url = start_fake_server(
        [(400, {"Content-Type": "application/json"}, error_body)]
    )
    try:
        client = MetaClient(settings=Settings(base_url=base_url), ledger=ledger, run="leak")
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(ApiError) as excinfo:
                client.respond("hello", note="leak check")
    finally:
        server.shutdown()
    assert SENTINEL not in str(excinfo.value)
    assert SENTINEL not in repr(excinfo.value)
    assert SENTINEL not in caplog.text
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert SENTINEL not in path.read_text(encoding="utf-8")
    assert "SENTINEL" not in repr(client)
