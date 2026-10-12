# Contributing

This repo publishes TrueFoundry's outbound NAT IPs. Changes to `data/` are made by TrueFoundry engineers; anyone can open an issue.

## Reporting a problem

[Open an issue](https://github.com/truefoundry/nat-ips/issues) if an IP looks wrong, a region is missing, or traffic arrives from an address that isn't listed. Include the destination you saw it on and a timestamp.

Anything security-sensitive goes to security@truefoundry.com, not a public issue.

## Changing the data

1. Edit the right file under `data/<plane>/`. Nothing in `dist/` is hand-edited.
2. Write IPs as CIDR — a single address is `/32`.
3. Run the checks locally:
   ```bash
   uv run scripts/validate.py
   uv run scripts/build.py --version 0.0.0-local
   ```
4. Open a PR. CI validates and comments the exact IP diff.
5. Merge to `main` — the release workflow tags and publishes automatically.

### Adding a regional gateway PoP

Gateway entries need an `airport_code` (lowercase IATA) and a `status`. A `live` entry also needs a `hostname`, whose first label must match the airport code:

```json
{
  "type": "gateway",
  "cloud": "gcp",
  "region": "asia-south1",
  "continent": "ap",
  "airport_code": "bom",
  "status": "live",
  "cluster": "tfy-gcp-bom-gtw",
  "hostname": "bom.gateway.truefoundry.ai",
  "nat_ips": ["34.100.0.1/32"]
}
```

Use `"status": "provisioned"` and omit `hostname` while the NAT addresses are allocated but the endpoint isn't published. Flip to `live` and add the hostname when it goes into service — that flip is itself a release, which is what tells customers the region is active.

### Transcribing from the wiki

The *LLMGateway Clusters* page renders paired NAT addresses as one unseparated string (`18.119.53.2363.130.37.65`). Several of those split more than one way and **all candidates parse as valid IPv4**, so do not eyeball them. Resolve each against the provider's published ranges — AWS `ip-ranges.json`, GCP `cloud.json`, Azure service tags — and accept a split only when both addresses fall inside the region the row claims. Two entries currently in `data/` do not split the way they look; see the Provenance section in the README.

### Timing

Publish **before** the IPs go live. Customers need lead time to get a firewall change through their own approval process. Retiring an IP is lower risk, but still announce it ahead of the cutover.
