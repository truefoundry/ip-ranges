# TrueFoundry NAT IPs

The outbound (egress) IP addresses TrueFoundry connects **from**. If you restrict inbound traffic to your model endpoints, webhooks, databases, or private APIs, allowlist the IPs for your control plane.

Published as machine-readable JSON with a [GitHub Release](https://github.com/truefoundry/nat-ips/releases) for every change, so you can subscribe and automate.

> **IPs change.** New regions get added and cloud NAT gateways get renumbered. Subscribe to releases rather than copying the list once.

---

## Get the list

Always-latest URLs — these follow the newest release:

| What | URL |
| --- | --- |
| Everything | `https://github.com/truefoundry/nat-ips/releases/latest/download/nat-ips.json` |
| US control plane only | `https://github.com/truefoundry/nat-ips/releases/latest/download/us.json` |
| EU control plane only | `https://github.com/truefoundry/nat-ips/releases/latest/download/eu.json` |
| Plain text, one CIDR per line | swap `.json` → `.txt` in any URL above |

Pin to an exact version by replacing `latest/download` with `download/v2026.10.12`.

```bash
# Every IP, ready to paste into a firewall rule
curl -sL https://github.com/truefoundry/nat-ips/releases/latest/download/nat-ips.txt | grep -v '^#'

# Just the EU gateway PoPs
curl -sL https://github.com/truefoundry/nat-ips/releases/latest/download/eu.json \
  | jq -r '.entries[] | select(.type == "gateway") | .nat_ips[]'
```

## Which IPs do I need?

Pick by the TrueFoundry domain you were onboarded onto.

| Your setup | Allowlist |
| --- | --- |
| Control plane at `*.us.truefoundry.cloud` | `us.json` |
| Control plane at `*.eu.truefoundry.cloud` | `eu.json` |
| Not sure, or you use both | `nat-ips.json` |

Within a control plane there are two kinds of entry:

- **`control_plane`** — the TrueFoundry platform itself. Covers deployments, webhooks, and integrations calling out to your systems.
- **`gateway`** — regional AI Gateway points of presence. Traffic to your self-hosted or private model endpoints comes from these. Each has a `hostname` (for example `mad.us.truefoundry.cloud`) and an `airport_code`.

**If you only serve models through the AI Gateway, the `gateway` entries alone are enough.** Most customers need both.

## Subscribe to changes

Pick whichever fits how you work:

**1. GitHub notifications** — click **Watch → Custom → Releases** at the top of this repo. Everyone on your team who wants alerts should do this individually.

**2. RSS / Atom** — point any feed reader, Slack RSS app, or internal bot at:

```
https://github.com/truefoundry/nat-ips/releases.atom
```

In Slack: `/feed subscribe https://github.com/truefoundry/nat-ips/releases.atom`

**3. Poll from automation** — check the `version` field and act when it changes:

```bash
VERSION=$(curl -sL https://github.com/truefoundry/nat-ips/releases/latest/download/nat-ips.json | jq -r .version)
```

Every release note lists the exact IPs **added** and **removed** versus the previous release, so a diff is never required on your side.

> Add newly published IPs promptly. Removing retired IPs is optional and can wait for your next maintenance window — stale entries are harmless.

## Data format

```json
{
  "version": "2026.10.12",
  "generation_timestamp": "2026-10-12T09:14:03Z",
  "entry_count": 4,
  "ip_count": 8,
  "entries": [
    {
      "control_plane": "us",
      "type": "gateway",
      "host": "mad.us.truefoundry.cloud",
      "gateway_host": "us.truefoundry.cloud",
      "cloud": "gcp",
      "region": "europe-southwest1",
      "continent": "eu",
      "airport_code": "mad",
      "nat_ips": ["34.175.44.33/32", "34.175.219.109/32"]
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `version` | CalVer release, matching the git tag `v<version>` |
| `generation_timestamp` | UTC build time, ISO 8601 |
| `control_plane` | `us` or `eu` |
| `type` | `control_plane` or `gateway` |
| `host` | The endpoint this entry serves. Wildcard for control planes, regional FQDN for gateways |
| `gateway_host` | Gateway entries only — the global entry point that routes to this PoP |
| `cloud` / `region` | Where the egress NAT lives |
| `airport_code` | Gateway entries only — IATA code for the PoP |
| `nat_ips` | IPv4 CIDRs. Single addresses are written `/32` |

Entries are sorted deterministically and IPs are sorted numerically, so a `git diff` between versions is readable.

JSON Schema for the source files: [`schema/nat-ips.schema.json`](schema/nat-ips.schema.json).

---

## For TrueFoundry engineers

Source of truth is `data/<plane>/<control-plane|gateway>.json`. Everything in `dist/` is generated — never edit it by hand.

```
data/
├── us/
│   ├── control-plane.json    # *.us.truefoundry.cloud
│   └── gateway.json          # us.truefoundry.cloud + regional PoPs
└── eu/
    ├── control-plane.json    # *.eu.truefoundry.cloud
    └── gateway.json          # eu.truefoundry.cloud + regional PoPs
```

To add or change IPs:

1. Edit the relevant file under `data/`.
2. Open a PR. CI validates the schema and comments the exact IP diff for review.
3. Merge to `main`. The release workflow builds `dist/`, tags `v<CalVer>`, and publishes a release with notes listing added and removed IPs.

Run the same checks locally:

```bash
uv run scripts/validate.py
uv run scripts/build.py --version 0.0.0-local
```

Validation rejects malformed CIDRs, host bits set on a prefix, private or reserved addresses, overlapping ranges within an entry, gateway entries missing a `hostname` or `airport_code`, and a `control_plane` that disagrees with its directory. Duplicate IPs across entries are reported as warnings.

To preview a release without publishing: **Actions → Release → Run workflow → dry run**.

> The release workflow pushes a commit to `main`. If you enable branch protection, allow `github-actions[bot]` to bypass it, or the release step will fail.

## Reporting a problem

Something wrong or missing? [Open an issue](https://github.com/truefoundry/nat-ips/issues) or contact TrueFoundry support. For anything security-sensitive, email security@truefoundry.com instead of filing a public issue.
