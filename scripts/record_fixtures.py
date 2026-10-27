"""Record the three real API fixtures for M1 (cost must stay under $0.01).

Saves raw SSE streams to tests/fixtures/:
  spark_text.sse   - one short Spark text answer
  spark_tool.sse   - one Spark turn that calls a tool
  sam_red_square.sse (+ sam_clip.mp4, sam_manifest.json) - SAM 3.1 on a
    synthetic 10-frame clip (red square moving on grey, made with ffmpeg).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from physics_proof.config import Settings  # noqa: E402
from physics_proof.ledger import Ledger  # noqa: E402
from physics_proof.meta_client import MetaClient, video_dimensions  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures"
CLIP = FIXTURES / "sam_clip.mp4"
WIDTH, HEIGHT, FPS, N_FRAMES = 256, 256, 10, 10

TIME_TOOL = {
    "type": "function",
    "name": "get_time",
    "description": "Returns the current wall-clock time in a city.",
    "parameters": {
        "type": "object",
        "properties": {"city": {"type": "string", "description": "City name"}},
        "required": ["city"],
        "additionalProperties": False,
    },
    "strict": True,
}


def make_clip() -> None:
    """Generate the synthetic 10-frame clip with ffmpeg (lavfi only)."""
    FIXTURES.mkdir(parents=True, exist_ok=True)
    duration = N_FRAMES / FPS
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x808080:s={WIDTH}x{HEIGHT}:r={FPS}:d={duration}",
        "-f", "lavfi",
        "-i", f"color=c=red:s=40x40:r={FPS}:d={duration}",
        "-filter_complex", "overlay=x=10+n*20:y=108",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-frames:v", str(N_FRAMES),
        str(CLIP),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    width, height = video_dimensions(CLIP)
    assert (width, height) == (WIDTH, HEIGHT), f"clip is {width}x{height}"


def main() -> None:
    make_clip()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ledger = Ledger(tmp_path / "run.jsonl", tmp_path / "global.jsonl")
        client = MetaClient(settings=Settings(), ledger=ledger, run="m1-record")

        text = client.respond(
            "Reply with exactly the two words: hello world",
            max_output_tokens=1024,
            note="m1 fixture: text",
        )
        (FIXTURES / "spark_text.sse").write_bytes(text.raw)
        print(f"Spark text: status={text.status} cost=${text.cost_usd:.6f}", flush=True)

        tool = client.respond(
            "Call the get_time function with city set to Paris.",
            tools=[TIME_TOOL],
            max_output_tokens=1024,
            note="m1 fixture: tool",
        )
        (FIXTURES / "spark_tool.sse").write_bytes(tool.raw)
        print(
            f"Spark tool: status={tool.status} "
            f"calls={[(c.name, c.arguments) for c in tool.function_calls]} "
            f"cost=${tool.cost_usd:.6f}",
            flush=True,
        )
        assert len(tool.function_calls) == 1, "expected exactly one tool call"

        sam = client.sam_video(CLIP, "red square", note="m1 fixture: sam")
        (FIXTURES / "sam_red_square.sse").write_bytes(sam.raw)
        manifest = {
            "width": WIDTH,
            "height": HEIGHT,
            "frames_processed": sam.frames_processed,
            "frames_with_objects": sorted(sam.frames),
            "frame_count": len(sam.frames),
        }
        (FIXTURES / "sam_manifest.json").write_text(json.dumps(manifest, indent=2))
        print(
            f"SAM: frames={len(sam.frames)} processed={sam.frames_processed} "
            f"cost=${sam.cost_usd:.6f}",
            flush=True,
        )

        total_usd = Ledger.total(tmp_path / "run.jsonl")
        print(f"Total recorded cost: ${total_usd:.6f} (cap $0.01)", flush=True)
        if total_usd >= 0.01:
            raise SystemExit(f"over budget: ${total_usd:.6f} >= $0.01")


if __name__ == "__main__":
    main()
