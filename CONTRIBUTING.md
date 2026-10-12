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

Gateway entries need both an `airport_code` (lowercase IATA) and a `hostname`:

```json
{
  "type": "gateway",
  "cloud": "gcp",
  "region": "asia-south1",
  "continent": "ap",
  "airport_code": "bom",
  "hostname": "bom.us.truefoundry.cloud",
  "nat_ips": ["34.100.0.1/32"]
}
```

### Timing

Publish **before** the IPs go live. Customers need lead time to get a firewall change through their own approval process. Retiring an IP is lower risk, but still announce it ahead of the cutover.
