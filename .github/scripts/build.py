#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Copy global/ and us/ into the release artifacts in dist/.

Run with: uv run .github/scripts/build.py --version 2026.10.12
"""

from __future__ import annotations

import argparse
import ipaddress
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # .github/scripts/build.py -> repo root
DIST_DIR = ROOT / "dist"
PLANES = ("global", "us")
REPO = "https://github.com/truefoundry/ip-ranges"


def flat_ips(endpoints: list[dict]) -> list[str]:
    unique = {cidr for endpoint in endpoints for cidr in endpoint["nat_ips"]}
    return sorted(unique, key=lambda cidr: ipaddress.IPv4Network(cidr))


def load_plane(plane: str) -> dict:
    path = ROOT / plane / "ip-ranges.json"
    if not path.exists():
        raise SystemExit(f"missing {path} — refusing to build")
    doc = json.loads(path.read_text())
    # Release assets are the public document. $schema is only for editors in the repo.
    return {"endpoints": doc["endpoints"]}


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def write_text(path: Path, plane: str, version: str, timestamp: str, ips: list[str]) -> None:
    header = [
        f"# TrueFoundry {plane.upper()} outbound NAT IPs",
        f"# version: {version}",
        f"# generated: {timestamp}",
        f"# {REPO}",
    ]
    path.write_text("\n".join(header + ips) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="CalVer release, e.g. 2026.10.12")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    DIST_DIR.mkdir(exist_ok=True)

    for plane in PLANES:
        doc = load_plane(plane)
        write_json(DIST_DIR / f"{plane}.json", doc)
        write_text(
            DIST_DIR / f"{plane}.txt",
            plane,
            args.version,
            timestamp,
            flat_ips(doc["endpoints"]),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
