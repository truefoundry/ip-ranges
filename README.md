# TrueFoundry NAT IPs

The outbound (egress) IP addresses TrueFoundry connects **from**. If you restrict inbound traffic to your model endpoints, webhooks, databases, or private APIs, allowlist these.

Published as machine-readable JSON with a [GitHub Release](https://github.com/truefoundry/nat-ips/releases) for every change, so you can subscribe and automate.

> **IPs change.** Regions get added and cloud NAT gateways get renumbered. Subscribe to releases rather than copying the list once.

---

## Get the list

Always-latest URLs — these follow the newest release:

| What | URL |
| --- | --- |
| Everything | `https://github.com/truefoundry/nat-ips/releases/latest/download/nat-ips.json` |
| EU control plane only | `https://github.com/truefoundry/nat-ips/releases/latest/download/eu.json` |
| Plain text, one CIDR per line | swap `.json` → `.txt` in any URL above |

Pin to an exact version by replacing `latest/download` with `download/v2026.10.12`.

```bash
# Every IP, ready to paste into a firewall rule
curl -sL https://github.com/truefoundry/nat-ips/releases/latest/download/nat-ips.txt | grep -v '^#'

# Just the EU-region PoPs
curl -sL https://github.com/truefoundry/nat-ips/releases/latest/download/nat-ips.json \
  | jq -r '.entries[] | select(.continent == "eu") | .nat_ips[]'
```

## Coverage

| Plane | Status |
| --- | --- |
| AI Gateway — `*.gateway.truefoundry.ai` | **Published**, 42 regions |
| EU control plane — `*.eu.truefoundry.cloud` | Not yet published |
| US control plane — `*.us.truefoundry.cloud` | Not yet published |

If you call models through the AI Gateway, what's published today is what you need. Control-plane egress IPs are coming; watch releases to be notified.

## Data format

```json
{
  "version": "2026.10.12",
  "generation_timestamp": "2026-10-12T12:52:47Z",
  "entry_count": 42,
  "ip_count": 84,
  "entries": [
    {
      "control_plane": "eu",
      "type": "gateway",
      "cloud": "gcp",
      "region": "europe-southwest1",
      "continent": "eu",
      "airport_code": "mad",
      "gateway_host": "gateway.truefoundry.ai",
      "host": "mad.gateway.truefoundry.ai",
      "nat_ips": ["34.175.44.33/32", "34.175.219.109/32"]
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `version` | CalVer release, matching the git tag `v<version>` |
| `generation_timestamp` | UTC build time, ISO 8601 |
| `control_plane` | `us` or `eu` — which control plane manages this cluster |
| `type` | `control_plane` or `gateway` |
| `cloud` / `region` | Where the egress NAT lives |
| `continent` | `na`, `sa`, `eu`, `ap`, `me`, `af`, `oc` |
| `airport_code` | Gateway entries only — IATA code for the PoP |
| `gateway_host` | Gateway entries only — the global entry point |
| `host` | The endpoint this entry serves. Absent when the cluster's NAT addresses are allocated but its endpoint isn't published yet — **allowlist those IPs anyway**, so a region going live isn't an urgent firewall change on your side |
| `nat_ips` | IPv4 CIDRs. Single addresses are written `/32` |

> `airport_code` is **not unique**. Two clusters in the same metro on different clouds share a code — `sfo` is both AWS `us-west-1` and Azure `westus`. Key on `cluster`/`region`, not the airport code.

Entries are sorted deterministically and IPs are sorted numerically, so a `git diff` between versions is readable.

JSON Schema for the source files: [`schema/nat-ips.schema.json`](schema/nat-ips.schema.json).

## Subscribe to changes

**1. GitHub notifications** — **Watch → Custom → Releases** at the top of this repo. Each person who wants alerts does this individually.

**2. RSS / Atom** — point a feed reader, the Slack RSS app, or an internal bot at:

```
https://github.com/truefoundry/nat-ips/releases.atom
```

In Slack: `/feed subscribe https://github.com/truefoundry/nat-ips/releases.atom`

**3. Poll from automation** — check `version` and act when it changes:

```bash
VERSION=$(curl -sL https://github.com/truefoundry/nat-ips/releases/latest/download/nat-ips.json | jq -r .version)
```

Every release note lists the exact IPs **added** and **removed** versus the previous release, so you never need to diff on your side.

> Add newly published IPs promptly. Removing retired IPs is optional and can wait for your next maintenance window — stale entries are harmless.

---

## For TrueFoundry engineers

Source of truth is `data/<control-plane>/<plane>.json`. `dist/` is a build artifact — it is **not tracked in git**, it is built in CI and attached to each release. Build it locally whenever you want to inspect it.

```
data/
└── eu/
    └── gateway.json      # 42 clusters on *.gateway.truefoundry.ai
```

Still to add: `data/eu/control-plane.json`, `data/us/control-plane.json`, `data/us/gateway.json`.

To add or change IPs:

1. Edit the relevant file under `data/`.
2. Open a PR. CI validates the schema and comments the exact IP diff for review.
3. Merge to `main`. The release workflow builds `dist/`, tags `v<CalVer>` at that commit, and publishes a release with notes listing added and removed IPs.

Run the same checks locally:

```bash
uv run .github/scripts/validate.py
uv run .github/scripts/build.py --version 0.0.0-local
```

Validation rejects malformed CIDRs, host bits set on a prefix, private or reserved addresses, overlapping ranges within an entry, a `hostname` whose leading label disagrees with its `airport_code`, gateway entries missing an `airport_code`, and a `control_plane` that disagrees with its directory. Duplicate IPs across entries are reported as warnings.

To preview a release without publishing: **Actions → Release → Run workflow → dry run**. The notes land in the job summary.

> The release workflow never pushes to `main` — it tags the merge commit and uploads artifacts, so the branch ruleset requiring pull requests doesn't block it. Each release's diff baseline is the `nat-ips.json` asset from the previous release, so **don't delete old releases**.

### Provenance

The gateway data was transcribed from the internal *LLMGateway Clusters* wiki page, where paired NAT addresses render as one unseparated string (`18.119.53.2363.130.37.65`). Those splits are ambiguous — several parse more than one way — so each was resolved against the provider's published ranges (AWS `ip-ranges.json`, GCP `cloud.json`, Azure service tags) and accepted only when both addresses fall inside the claimed region. Two rows do not split the way they look:

- `tfy-aws-fra-gtw` → `3.65.93.12` + `63.181.139.3` (not `3.65.93.126` + `3.181.139.3`)
- `tfy-aws-hnd-gtw` → `54.238.73.1` + `18.178.26.39` (not `54.238.73.11` + `8.178.26.39`)

Two region codes on the wiki are also wrong and are corrected here: `tfy-aws-mad-gtw` is `eu-south-2` (wiki says `ap-south-2`) and `tfy-aws-zrh-gtw` is `eu-central-2` (wiki says `eu-central-1`).

**Re-verify after any bulk edit** rather than trusting a copy-paste from the wiki.

## Reporting a problem

Something wrong or missing? [Open an issue](https://github.com/truefoundry/nat-ips/issues) or contact TrueFoundry support. For anything security-sensitive, email security@truefoundry.com instead of filing a public issue.
