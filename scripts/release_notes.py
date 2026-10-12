#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Diff two built nat-ips.json files and write release notes a firewall admin can act on.

Run with: uv run scripts/release_notes.py --new dist/nat-ips.json --old /tmp/prev.json
"""

from __future__ import annotations

import argparse
import ipaddress
import json
from collections import defaultdict
from pathlib import Path

REPO = "https://github.com/truefoundry/nat-ips"


def ip_owners(doc: dict) -> dict[str, list[dict]]:
    """Map every CIDR to all entries that use it.

    One NAT gateway can back several entries, so this is deliberately many-to-many —
    attributing an IP to a single entry would hide where it is actually in use.
    """
    index: dict[str, list[dict]] = defaultdict(list)
    for entry in doc.get("entries", []):
        for cidr in entry["nat_ips"]:
            index[cidr].append(entry)
    return index


def describe(entry: dict) -> str:
    bits = [entry["control_plane"].upper(), entry["type"].replace("_", " "), entry["region"]]
    if entry.get("airport_code"):
        bits.append(entry["airport_code"].upper())
    return " · ".join(bits)


def host_label(entry: dict) -> str:
    """A provisioned cluster has no endpoint, so say that rather than print empty backticks."""
    host = entry.get("host")
    if host:
        return f"`{host}`"
    if entry.get("status") == "provisioned":
        return "_provisioned, no endpoint yet_"
    return "_no endpoint_"


def ip_sort(cidr: str) -> ipaddress.IPv4Network:
    return ipaddress.IPv4Network(cidr)


def render_changed(title: str, cidrs: list[str], index: dict[str, list[dict]]) -> list[str]:
    """Group changed IPs under every entry that uses them."""
    if not cidrs:
        return []

    buckets: dict[tuple[str, str], set[str]] = defaultdict(set)
    for cidr in cidrs:
        for entry in index[cidr]:
            buckets[(describe(entry), host_label(entry))].add(cidr)

    lines = [f"### {title} ({len(cidrs)})", ""]
    for (label, host), group in sorted(buckets.items()):
        lines.append(f"**{label}** — {host}")
        lines.extend(f"- `{cidr}`" for cidr in sorted(group, key=ip_sort))
        lines.append("")
    return lines


def render_full(doc: dict) -> list[str]:
    """List every entry in order — used for the first release, where nothing is a 'change'."""
    lines = ["### Published IPs", ""]
    for entry in doc.get("entries", []):
        lines.append(f"**{describe(entry)}** — {host_label(entry)}")
        lines.extend(f"- `{cidr}`" for cidr in entry["nat_ips"])
        lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--new", required=True, type=Path)
    parser.add_argument("--old", type=Path, help="omit for the first release")
    parser.add_argument("--out", type=Path, default=Path("RELEASE_NOTES.md"))
    args = parser.parse_args()

    new_doc = json.loads(args.new.read_text())
    new_index = ip_owners(new_doc)
    version = new_doc["version"]

    old_doc: dict = {}
    if args.old and args.old.exists():
        old_doc = json.loads(args.old.read_text())
    old_index = ip_owners(old_doc)

    added = sorted(set(new_index) - set(old_index), key=ip_sort)
    removed = sorted(set(old_index) - set(new_index), key=ip_sort)

    lines = [f"## TrueFoundry outbound NAT IPs — {version}", ""]

    if not old_doc:
        lines += [
            "First published release. Allowlist the IPs below for traffic arriving from TrueFoundry.",
            "",
        ]
        lines += render_full(new_doc)
    elif not added and not removed:
        lines += [
            f"No IP changes since `{old_doc['version']}`. Metadata or docs only — **no firewall action needed**.",
            "",
        ]
    else:
        action = []
        if added:
            action.append(f"**{len(added)} IP(s) to add**")
        if removed:
            action.append(f"**{len(removed)} IP(s) safe to remove**")
        lines += [
            f"Changes since `{old_doc['version']}`: " + " and ".join(action) + ".",
            "",
            "> Add new IPs **before** the rollout date. Removing retired IPs is optional and can wait.",
            "",
        ]
        lines += render_changed("Added", added, new_index)
        lines += render_changed("Removed", removed, old_index)

    # Only link per-plane assets that this release actually built.
    planes = sorted({e["control_plane"] for e in new_doc.get("entries", [])})
    lines += [
        "---",
        "",
        "### Full list",
        "",
        f"- Everything: {REPO}/releases/download/v{version}/nat-ips.json",
    ]
    lines += [
        f"- {plane.upper()} control plane: {REPO}/releases/download/v{version}/{plane}.json"
        for plane in planes
    ]
    totals = f"**{new_doc['entry_count']} entries, {new_doc['ip_count']} unique IPs**"
    if new_doc.get("provisioned_count"):
        totals += f" ({new_doc['live_count']} live, {new_doc['provisioned_count']} provisioned)"
    lines += [
        "- Plain text for firewall scripts: swap `.json` for `.txt` in any URL above.",
        f"- Always-latest instead of pinned: {REPO}/releases/latest/download/nat-ips.json",
        "",
        f"Totals in this release: {totals}.",
        "",
    ]

    args.out.write_text("\n".join(lines))
    print(f"wrote {args.out} ({len(added)} added, {len(removed)} removed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
