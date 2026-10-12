#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Flatten the per-plane source files under data/ into the published artifacts in dist/.

Run with: uv run scripts/build.py --version 2026.10.12
"""

from __future__ import annotations

import argparse
import ipaddress
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DIST_DIR = ROOT / "dist"

PLANES = ("us", "eu")


def sort_key(entry: dict) -> tuple:
    """Stable ordering so a rebuild with no data change produces a byte-identical file."""
    return (
        entry["control_plane"],
        0 if entry["type"] == "control_plane" else 1,
        entry.get("airport_code", ""),
        entry["region"],
    )


def load_entries() -> list[dict]:
    entries: list[dict] = []

    for path in sorted(DATA_DIR.rglob("*.json")):
        doc = json.loads(path.read_text())
        control_plane = doc["control_plane"]

        for source in doc["entries"]:
            entry = {
                "control_plane": control_plane,
                "type": source["type"],
                "cloud": source["cloud"],
                "region": source["region"],
                "continent": source["continent"],
            }

            if source["type"] == "gateway":
                entry["status"] = source["status"]
                entry["airport_code"] = source["airport_code"]
                entry["gateway_host"] = doc["host"]
                # A provisioned cluster has no published endpoint yet, so it gets no host.
                # Inventing one would tell customers to resolve a name that does not exist.
                if "hostname" in source:
                    entry["host"] = source["hostname"]
            else:
                entry["host"] = doc.get("host_pattern") or doc.get("host")

            if "notes" in source:
                entry["notes"] = source["notes"]

            entry["nat_ips"] = sorted(
                source["nat_ips"], key=lambda cidr: ipaddress.IPv4Network(cidr)
            )
            entries.append(entry)

    entries.sort(key=sort_key)
    return entries


def flat_ip_list(entries: list[dict]) -> list[str]:
    unique = {cidr for entry in entries for cidr in entry["nat_ips"]}
    return sorted(unique, key=lambda cidr: ipaddress.IPv4Network(cidr))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def write_text(path: Path, version: str, timestamp: str, ips: list[str]) -> None:
    header = [
        "# TrueFoundry outbound NAT IPs",
        f"# version: {version}",
        f"# generated: {timestamp}",
        "# https://github.com/truefoundry/nat-ips",
    ]
    path.write_text("\n".join(header + ips) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="CalVer release, e.g. 2026.10.12")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = load_entries()
    DIST_DIR.mkdir(exist_ok=True)

    def envelope(subset: list[dict]) -> dict:
        return {
            "version": args.version,
            "generation_timestamp": timestamp,
            "entry_count": len(subset),
            "ip_count": len(flat_ip_list(subset)),
            "live_count": sum(1 for e in subset if e.get("status") != "provisioned"),
            "provisioned_count": sum(1 for e in subset if e.get("status") == "provisioned"),
            "entries": subset,
        }

    write_json(DIST_DIR / "nat-ips.json", envelope(entries))
    write_text(DIST_DIR / "nat-ips.txt", args.version, timestamp, flat_ip_list(entries))

    for plane in PLANES:
        subset = [e for e in entries if e["control_plane"] == plane]
        if not subset:
            continue
        write_json(DIST_DIR / f"{plane}.json", envelope(subset))
        write_text(DIST_DIR / f"{plane}.txt", args.version, timestamp, flat_ip_list(subset))

    print(f"\n{len(entries)} entries, {len(flat_ip_list(entries))} unique IPs, version {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
