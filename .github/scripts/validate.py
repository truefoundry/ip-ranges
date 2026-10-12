#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["jsonschema>=4.21"]
# ///
"""Validate global/ip-ranges.json and us/ip-ranges.json.

Run with: uv run .github/scripts/validate.py
"""

from __future__ import annotations

import ipaddress
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]  # .github/scripts/validate.py -> repo root
SCHEMA_PATH = ROOT / ".github" / "schema" / "ip-ranges.schema.json"
PLANES = ("global", "us")

HOSTNAME_RE = re.compile(r"^(\*\.)?(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")

# Continent hostnames combine the published regional gateways that can serve them,
# including the documented fallback region. gateway.truefoundry.ai is every regional gateway.
# https://www.truefoundry.com/docs/ai-gateway/globally-distributed-saas
GEO_ORDER = (
    "gateway.truefoundry.ai",
    "us.gateway.truefoundry.ai",
    "eu.gateway.truefoundry.ai",
    "sa.gateway.truefoundry.ai",
    "au.gateway.truefoundry.ai",
    "as.gateway.truefoundry.ai",
)
REGIONAL_GATEWAYS = {
    "us.gateway.truefoundry.ai": frozenset({"orf", "sfo", "dfw", "yyz"}),
    "eu.gateway.truefoundry.ai": frozenset({"lhr", "mad", "gvx", "dia"}),
    "sa.gateway.truefoundry.ai": frozenset({"gru"}),
    "au.gateway.truefoundry.ai": frozenset({"syd", "mel", "sin"}),
    "as.gateway.truefoundry.ai": frozenset({"bom", "sin", "dia", "mel"}),
}

errors: list[str] = []
warnings: list[str] = []


def error(where: str, msg: str) -> None:
    errors.append(f"{where}: {msg}")


def warn(where: str, msg: str) -> None:
    warnings.append(f"{where}: {msg}")


def ip_sort(cidr: str):
    return ipaddress.IPv4Network(cidr)


def check_cidr(where: str, raw: str) -> ipaddress.IPv4Network | None:
    """Parse a CIDR and reject anything that cannot be a public NAT egress address."""
    try:
        net = ipaddress.IPv4Network(raw, strict=True)
    except ValueError as exc:
        error(where, f"invalid CIDR {raw!r}: {exc}")
        return None

    if not net.is_global:
        error(where, f"{raw} is not a globally routable address; NAT egress IPs must be public")
    return net


def endpoint_sort_key(endpoint: dict) -> tuple:
    if endpoint["type"] == "control_plane":
        return (0, endpoint["hostname"])
    hostname = endpoint["hostname"]
    if hostname in GEO_ORDER:
        return (1, GEO_ORDER.index(hostname))
    return (2, endpoint.get("airport_code", ""), hostname)


def check_rollups(where: str, endpoints: list[dict]) -> None:
    """Geolocated hostnames must list exactly the NAT addresses of their airports."""
    airports: dict[str, set[str]] = {}
    geos: dict[str, set[str]] = {}

    for endpoint in endpoints:
        if endpoint["type"] != "gateway":
            continue
        if "airport_code" in endpoint:
            airports[endpoint["airport_code"]] = set(endpoint["nat_ips"])
        else:
            geos[endpoint["hostname"]] = set(endpoint["nat_ips"])

    if not airports:
        return

    expected_global = set().union(*airports.values())
    if GEO_ORDER[0] not in geos:
        error(where, f"missing {GEO_ORDER[0]}, the union of every airport")
    else:
        report_set_diff(where, GEO_ORDER[0], expected_global, geos[GEO_ORDER[0]])

    for hostname, members in REGIONAL_GATEWAYS.items():
        present = members & airports.keys()
        if not present:
            if hostname in geos:
                error(where, f"{hostname} lists addresses but none of its airports are in this file")
            continue
        expected = set().union(*(airports[code] for code in present))
        if hostname not in geos:
            error(where, f"missing {hostname}")
            continue
        report_set_diff(where, hostname, expected, geos[hostname])


def report_set_diff(where: str, hostname: str, expected: set[str], actual: set[str]) -> None:
    missing = sorted(expected - actual, key=ip_sort)
    extra = sorted(actual - expected, key=ip_sort)
    if missing:
        shown = ", ".join(missing[:6])
        suffix = "" if len(missing) <= 6 else f" (+{len(missing) - 6} more)"
        error(where, f"{hostname} is missing {shown}{suffix}")
    if extra:
        shown = ", ".join(extra[:6])
        suffix = "" if len(extra) <= 6 else f" (+{len(extra) - 6} more)"
        error(where, f"{hostname} includes {shown}{suffix}, which are not on its airports")


def validate_file(plane: str, validator: Draft202012Validator) -> list[dict]:
    path = ROOT / plane / "ip-ranges.json"
    rel = f"{plane}/ip-ranges.json"
    extras = sorted(p.name for p in (ROOT / plane).glob("*.json") if p.name != "ip-ranges.json")
    if extras:
        error(plane, f"unexpected JSON files {extras}; keep addresses in ip-ranges.json")

    if not path.exists():
        error(plane, "missing ip-ranges.json")
        return []

    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        error(rel, f"not valid JSON: {exc}")
        return []

    schema_errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if schema_errors:
        for exc in schema_errors:
            location = "/".join(str(part) for part in exc.path) or "<root>"
            error(rel, f"{location}: {exc.message}")
        return []

    endpoints = doc["endpoints"]
    if plane == "global" and not endpoints:
        error(rel, "global publishes gateway addresses; endpoints is empty")

    if endpoints != sorted(endpoints, key=endpoint_sort_key):
        error(rel, "endpoints must be ordered control plane, then geolocated gateways, then airport code")

    built: list[dict] = []
    seen_hosts: dict[str, int] = {}
    for index, endpoint in enumerate(endpoints):
        where = f"{rel} endpoints[{index}]"
        hostname = endpoint["hostname"]
        if not HOSTNAME_RE.match(hostname):
            error(where, f"hostname {hostname!r} is not a valid lowercase FQDN")
        if hostname.startswith("*.") and endpoint["type"] != "control_plane":
            error(where, "only a control plane hostname may start with *.")

        if hostname in seen_hosts:
            error(where, f"hostname {hostname!r} is already used by endpoints[{seen_hosts[hostname]}]")
        seen_hosts[hostname] = index

        airport = endpoint.get("airport_code")
        if endpoint["type"] == "gateway" and airport is None and hostname not in GEO_ORDER:
            error(where, f"hostname {hostname!r} is not a known geolocated gateway")
        if airport is not None:
            expected = f"{airport}.gateway.truefoundry.ai"
            if hostname != expected:
                error(where, f"hostname {hostname!r} does not match airport code {airport!r} ({expected})")

        ordered = sorted(endpoint["nat_ips"], key=ip_sort)
        if endpoint["nat_ips"] != ordered:
            error(where, "nat_ips must be sorted numerically")

        nets = [net for net in (check_cidr(where, cidr) for cidr in endpoint["nat_ips"]) if net]
        for left_index, left in enumerate(nets):
            for right in nets[left_index + 1 :]:
                if left.overlaps(right):
                    error(where, f"{left} and {right} overlap; collapse them into one range")

        built.append({"plane": plane, "endpoint": endpoint, "nets": nets})

    check_rollups(rel, endpoints)
    return built


def check_duplicates(records: list[dict]) -> None:
    """The same address on a geolocated hostname and its airports is expected.

    The same address on two airports, or on two control planes, is a copy-paste slip.
    """
    seen: dict[str, list[str]] = {}
    for record in records:
        endpoint = record["endpoint"]
        if endpoint["type"] == "gateway" and "airport_code" not in endpoint:
            continue
        label = f"{record['plane']} {endpoint['hostname']}"
        for net in record["nets"]:
            seen.setdefault(str(net), []).append(label)

    for cidr, locations in sorted(seen.items()):
        if len(locations) > 1:
            warn("duplicate IP", f"{cidr} appears in {len(locations)} endpoints: {', '.join(locations)}")


def main() -> int:
    if not SCHEMA_PATH.exists():
        print(f"missing schema at {SCHEMA_PATH}", file=sys.stderr)
        return 1

    for plane in PLANES:
        if not (ROOT / plane).is_dir():
            print(f"missing {plane}/ directory", file=sys.stderr)
            return 1

    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    records: list[dict] = []
    for plane in PLANES:
        records.extend(validate_file(plane, validator))
    check_duplicates(records)

    for message in warnings:
        print(f"warning  {message}")
    for message in errors:
        print(f"error    {message}", file=sys.stderr)

    total_ips = sum(len(record["nets"]) for record in records)
    print(f"\nchecked {len(PLANES)} files, {len(records)} endpoints, {total_ips} IP references")

    if errors:
        print(f"FAILED with {len(errors)} error(s)", file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
