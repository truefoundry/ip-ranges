#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.21"]
# ///
"""Validate every source file under data/ against the schema and our own sanity rules.

Run with: uv run scripts/validate.py
"""

from __future__ import annotations

import ipaddress
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCHEMA_PATH = ROOT / "schema" / "nat-ips.schema.json"

HOSTNAME_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")

errors: list[str] = []
warnings: list[str] = []


def error(where: str, msg: str) -> None:
    errors.append(f"{where}: {msg}")


def warn(where: str, msg: str) -> None:
    warnings.append(f"{where}: {msg}")


def check_cidr(where: str, raw: str) -> ipaddress.IPv4Network | None:
    """Parse a CIDR and reject anything that cannot be a public NAT egress address."""
    try:
        net = ipaddress.IPv4Network(raw, strict=True)
    except ValueError as exc:
        # strict=True rejects host bits set, e.g. 10.0.0.1/24 — call that out specifically.
        error(where, f"invalid CIDR {raw!r}: {exc}")
        return None

    if not net.is_global:
        error(where, f"{raw} is not a globally routable address; NAT egress IPs must be public")
    return net


def validate_file(path: Path, validator: Draft202012Validator) -> list[dict]:
    rel = path.relative_to(ROOT)
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        error(str(rel), f"not valid JSON: {exc}")
        return []

    schema_errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if schema_errors:
        for exc in schema_errors:
            location = "/".join(str(p) for p in exc.path) or "<root>"
            error(str(rel), f"{location}: {exc.message}")
        return []

    # The directory is the source of truth for which control plane a file belongs to.
    expected_plane = path.parent.name
    if doc["control_plane"] != expected_plane:
        error(str(rel), f"control_plane is {doc['control_plane']!r} but the file lives under data/{expected_plane}/")

    expected_type = doc["plane"]
    if expected_type == "control_plane" and "host_pattern" not in doc:
        error(str(rel), "control-plane files need a host_pattern")
    if expected_type == "gateway" and "host" not in doc:
        error(str(rel), "gateway files need a host")

    built: list[dict] = []
    for index, entry in enumerate(doc["entries"]):
        where = f"{rel} entries[{index}]"

        if entry["type"] != expected_type:
            error(where, f"type is {entry['type']!r} but this file declares plane {expected_type!r}")

        hostname = entry.get("hostname")
        if hostname and not HOSTNAME_RE.match(hostname):
            error(where, f"hostname {hostname!r} is not a valid lowercase FQDN")

        # Catches a row pasted into the wrong cluster: the endpoint always leads with its
        # own airport code, so a mismatch means the entry has been crossed with another.
        airport = entry.get("airport_code")
        if hostname and airport and not hostname.startswith(f"{airport}."):
            error(where, f"hostname {hostname!r} does not start with airport code {airport!r}")

        nets = [n for n in (check_cidr(where, ip) for ip in entry["nat_ips"]) if n]
        for a_index, a in enumerate(nets):
            for b in nets[a_index + 1 :]:
                if a.overlaps(b):
                    error(where, f"{a} and {b} overlap; collapse them into one entry")

        built.append({"file": str(rel), "entry": entry, "nets": nets})

    return built


def check_cross_file(records: list[dict]) -> None:
    """A NAT IP appearing in two places is usually a copy-paste slip, not a real shared gateway."""
    seen: dict[str, list[str]] = defaultdict(list)
    for record in records:
        entry = record["entry"]
        label = f"{record['file']} ({entry['region']})"
        for net in record["nets"]:
            seen[str(net)].append(label)

    for cidr, locations in sorted(seen.items()):
        if len(locations) > 1:
            warn("duplicate IP", f"{cidr} appears in {len(locations)} entries: {', '.join(locations)}")


def main() -> int:
    if not SCHEMA_PATH.exists():
        print(f"missing schema at {SCHEMA_PATH}", file=sys.stderr)
        return 1

    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    paths = sorted(DATA_DIR.rglob("*.json"))
    if not paths:
        print("no source files found under data/", file=sys.stderr)
        return 1

    records: list[dict] = []
    for path in paths:
        records.extend(validate_file(path, validator))
    check_cross_file(records)

    for message in warnings:
        print(f"warning  {message}")
    for message in errors:
        print(f"error    {message}", file=sys.stderr)

    total_ips = sum(len(r["nets"]) for r in records)
    print(f"\nchecked {len(paths)} files, {len(records)} entries, {total_ips} IPs")

    if errors:
        print(f"FAILED with {len(errors)} error(s)", file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
