"""`make bench-a11y`: Lighthouse accessibility score for the main pages -> BENCHMARKS.md.

Needs the app running (`make demo`, or a dev server) and Google Chrome. WEB_URL picks the target,
e.g. WEB_URL=https://keystone-insights-nu.vercel.app make bench-a11y for the live demo.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from evals.bench_report import update_benchmarks

LIGHTHOUSE = "lighthouse@12.2.1"
PAGES = {
    "Welcome page": "/",
    "Portfolio dashboard": "/dashboard",
    "Property drill-down": "/properties/1",
    "Weekly digest": "/digest",
}


def audit(url: str) -> tuple[int, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "lh.json"
        subprocess.run(
            ["npx", "-y", LIGHTHOUSE, url, "--only-categories=accessibility", "--quiet",
             "--chrome-flags=--headless=new", "--output=json", f"--output-path={out}"],
            check=True, capture_output=True,
        )  # fmt: skip
        report = json.loads(out.read_text())
    cat = report["categories"]["accessibility"]
    ids = {r["id"] for r in cat["auditRefs"]}
    failing = [a["id"] for a in report["audits"].values() if a["id"] in ids and a.get("score") == 0]
    return round(cat["score"] * 100), failing


def main() -> None:
    base = os.environ.get("WEB_URL", "http://localhost:5173").rstrip("/")
    rows = []
    for name, path in PAGES.items():
        score, failing = audit(base + path)
        rows.append((name, score, failing))
        print(f"{name:20s} {score:3d}  {failing or ''}")
    body = "\n".join([
        "## Accessibility (Lighthouse)\n",
        "- **Command:** `make bench-a11y`",
        f"- **Date:** {time.strftime('%Y-%m-%d')}",
        f"- **Tool:** {LIGHTHOUSE}, headless Chrome, light mode, desktop viewport",
        f"- **Target:** `{base}`",
        "",
        "| Page | Score | Failing audits |",
        "|---|---|---|",
        *(f"| {n} | {s} | {', '.join(f) or 'none'} |" for n, s, f in rows),
        "",
        "Automated checks catch only part of accessibility (contrast, labels, roles, names). "
        "Manual keyboard and screen-reader testing hasn't been done.",
    ]) + "\n"  # fmt: skip
    update_benchmarks("a11y", body)


if __name__ == "__main__":
    main()
