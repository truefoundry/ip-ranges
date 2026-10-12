#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Diff published IP range files and write release notes.

Prints publish=, added=, and removed= for the release workflow.
Run with: uv run .github/scripts/release_notes.py --version 2026.10.12 --eu dist/eu.json --us dist/us.json
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "https://github.com/truefoundry/ip-ranges"
PAGES = "https://truefoundry.github.io/ip-ranges"
PLANES = ("eu", "us")
ACTIVATION_DAYS = 15


def ip_sort(cidr: str) -> ipaddress.IPv4Network:
    return ipaddress.IPv4Network(cidr)


def load_doc(path: Path | None) -> dict:
    if path is None:
        return {"endpoints": []}
    if not path.exists():
        raise SystemExit(f"missing {path}")
    return json.loads(path.read_text())


def cidrs_of(doc: dict) -> set[str]:
    return {cidr for endpoint in doc.get("endpoints", []) for cidr in endpoint["nat_ips"]}


def by_hostname(doc: dict) -> dict[str, set[str]]:
    return {endpoint["hostname"]: set(endpoint["nat_ips"]) for endpoint in doc.get("endpoints", [])}


def noun(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def activation_date(version: str) -> str | None:
    """CalVer date plus 15 days. Local and CI versions have no calendar date."""
    date_part = version.split("-", 1)[0]
    try:
        published = datetime.strptime(date_part, "%Y.%m.%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (published + timedelta(days=ACTIVATION_DAYS)).strftime("%Y-%m-%d")


def render_full(plane: str, doc: dict) -> list[str]:
    lines: list[str] = []
    for endpoint in doc.get("endpoints", []):
        lines.append(f"**{plane.upper()}** · `{endpoint['hostname']}`")
        lines.extend(f"- `{cidr}`" for cidr in endpoint["nat_ips"])
        lines.append("")
    return lines


def render_hostname_changes(plane: str, hostname: str, added: list[str], removed: list[str]) -> list[str]:
    lines = [f"### {plane.upper()} · `{hostname}`", ""]
    if added:
        lines.append("Added:")
        lines.extend(f"- `{cidr}`" for cidr in added)
        lines.append("")
    if removed:
        lines.append("Removed:")
        lines.extend(f"- `{cidr}`" for cidr in removed)
        lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--eu", required=True, type=Path)
    parser.add_argument("--us", required=True, type=Path)
    parser.add_argument("--old-eu", type=Path)
    parser.add_argument("--old-us", type=Path)
    parser.add_argument("--out", type=Path, default=Path("RELEASE_NOTES.md"))
    args = parser.parse_args()

    new_docs = {"eu": load_doc(args.eu), "us": load_doc(args.us)}
    has_baseline = args.old_eu is not None or args.old_us is not None
    old_docs = {
        "eu": load_doc(args.old_eu) if has_baseline else {"endpoints": []},
        "us": load_doc(args.old_us) if has_baseline else {"endpoints": []},
    }

    added_ips: set[str] = set()
    removed_ips: set[str] = set()
    hostname_changes: list[tuple[str, str, list[str], list[str]]] = []

    for plane in PLANES:
        new_set = cidrs_of(new_docs[plane])
        old_set = cidrs_of(old_docs[plane]) if has_baseline else set()
        if has_baseline:
            added_ips |= new_set - old_set
            removed_ips |= old_set - new_set

        new_hosts = by_hostname(new_docs[plane])
        old_hosts = by_hostname(old_docs[plane]) if has_baseline else {}
        for hostname in sorted(set(new_hosts) | set(old_hosts)):
            added = sorted(new_hosts.get(hostname, set()) - old_hosts.get(hostname, set()), key=ip_sort)
            removed = sorted(old_hosts.get(hostname, set()) - new_hosts.get(hostname, set()), key=ip_sort)
            if added or removed:
                hostname_changes.append((plane, hostname, added, removed))

    publish = not has_baseline or bool(added_ips or removed_ips or hostname_changes)
    lines = [f"## TrueFoundry IP ranges — {args.version}", ""]

    if not has_baseline:
        lines += [
            "First published release. These addresses are in use. Allowlist them for traffic arriving from TrueFoundry.",
            "",
            "Addresses added in a later release start carrying traffic 15 days after that release. "
            "When an address is removed, a release is published so it can be dropped from allowlists.",
            "",
        ]
        for plane in PLANES:
            lines += render_full(plane, new_docs[plane])
    elif not hostname_changes:
        lines += [
            "No IP changes since the previous release. **No firewall action needed.**",
            "",
        ]
    else:
        if added_ips:
            live = activation_date(args.version)
            when = f" on **{live}**" if live else ""
            lines += [
                f"Allowlist **{noun(len(added_ips), 'new address', 'new addresses')}** "
                f"before they start carrying traffic{when}, {ACTIVATION_DAYS} days after this release.",
                "",
            ]
        if removed_ips:
            lines += [
                f"**{noun(len(removed_ips), 'address removed', 'addresses removed')}.** "
                "They are no longer used and can be dropped from allowlists.",
                "",
            ]
        if hostname_changes and not added_ips and not removed_ips:
            lines += [
                "Addresses moved between hostnames. Update the allowlist for the hostnames below.",
                "",
            ]
        for plane, hostname, added, removed in hostname_changes:
            lines += render_hostname_changes(plane, hostname, added, removed)

    lines += ["---", "", "### Full list", ""]
    for plane in PLANES:
        count = len(cidrs_of(new_docs[plane]))
        lines.append(
            f"- {plane.upper()} ({count} addresses): {REPO}/releases/download/v{args.version}/{plane}.json"
        )
    lines += [
        "- Plain text, one CIDR per line: swap `.json` for `.txt`.",
        f"- Always-latest: {PAGES}/eu.json",
        "",
    ]

    args.out.write_text("\n".join(lines))
    print(f"publish={'true' if publish else 'false'}")
    print(f"added={len(added_ips)}")
    print(f"removed={len(removed_ips)}")
    print(f"wrote {args.out} ({len(added_ips)} added, {len(removed_ips)} removed)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
