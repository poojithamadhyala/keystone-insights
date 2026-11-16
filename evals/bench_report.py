"""Shared helpers for `make bench-*`: hardware description and BENCHMARKS.md section updates.

Each benchmark owns one section delimited by HTML comments, so re-running a benchmark replaces
its own numbers and never touches the others. Nothing in BENCHMARKS.md is edited by hand.
"""

from __future__ import annotations

import platform
import re
import subprocess
from pathlib import Path

BENCHMARKS = Path("BENCHMARKS.md")


def hardware() -> str:
    chip = platform.processor() or platform.machine()
    if platform.system() == "Darwin":
        try:
            chip = (
                subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
                ).stdout.strip()
                or chip
            )
            mem = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True,
                                     text=True).stdout.strip()) // 2**30  # fmt: skip
            chip = f"{chip}, {mem} GB RAM"
        except (OSError, ValueError):
            pass
    try:
        from common.device import best_device

        device = best_device()
    except ImportError:
        device = "cpu"
    return f"{chip}, {platform.system()} {platform.release()}, torch device: {device}"


def update_benchmarks(key: str, body: str) -> None:
    start, end = f"<!-- bench:{key}:start -->", f"<!-- bench:{key}:end -->"
    text = BENCHMARKS.read_text()
    block = f"{start}\n{body}{end}"
    if start in text:
        text = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _: block, text, flags=re.S)
    else:
        text = text.replace("_No benchmarks yet. They are added from milestone 2 onward._\n", "")
        text = text.rstrip() + "\n\n" + block + "\n"
    BENCHMARKS.write_text(text)
