# TrueFoundry IP ranges

Outbound IP addresses TrueFoundry uses when it connects to your systems. Allowlist these if you restrict inbound access to your model endpoints, webhooks, databases, or private APIs.

The directory is the control plane:

| Control plane | List |
| --- | --- |
| EU | [`eu/ip-ranges.json`](eu/ip-ranges.json) |
| US | [`us/ip-ranges.json`](us/ip-ranges.json) |

Always-latest URLs are on GitHub Pages:

- https://truefoundry.github.io/ip-ranges/eu.json
- https://truefoundry.github.io/ip-ranges/us.json

Replace `.json` with `.txt` for one CIDR per line.

Each [GitHub Release](https://github.com/truefoundry/ip-ranges/releases) attaches the same lists, so a version can be pinned: `https://github.com/truefoundry/ip-ranges/releases/download/v2026.10.12/eu.json`.

## What to allowlist

Find the hostname you connect to. `nat_ips` is every address that hostname can connect from.

```json
{
  "endpoints": [
    {
      "type": "control_plane",
      "hostname": "eu.truefoundry.cloud",
      "nat_ips": ["203.0.113.10/32"]
    },
    {
      "type": "gateway",
      "hostname": "us.gateway.truefoundry.ai",
      "nat_ips": ["52.4.51.133/32", "54.204.114.10/32"]
    },
    {
      "type": "gateway",
      "airport_code": "orf",
      "hostname": "orf.gateway.truefoundry.ai",
      "nat_ips": ["52.4.51.133/32", "54.204.114.10/32"]
    }
  ]
}
```

`type` is `control_plane` or `gateway`. Airport endpoints include `airport_code`. Continent hostnames combine the regional gateways that can serve them, including the documented fallback, and `nat_ips` is that combined list. Which gateway you connect to is in the [globally distributed SaaS gateway](https://www.truefoundry.com/docs/ai-gateway/globally-distributed-saas) docs:

| Hostname | Addresses |
| --- | --- |
| `gateway.truefoundry.ai` | Every regional gateway |
| `us.gateway.truefoundry.ai` | North Virginia, San Francisco, Dallas, and Toronto |
| `eu.gateway.truefoundry.ai` | London, Madrid, Gavle, and Doha |
| `sa.gateway.truefoundry.ai` | Sao Paulo |
| `au.gateway.truefoundry.ai` | Sydney, Melbourne, and Singapore |
| `as.gateway.truefoundry.ai` | Mumbai, Singapore, Doha, and Melbourne |

`us/ip-ranges.json` is empty until the US control plane publishes egress addresses.

## When addresses change

Address changes are published as a GitHub Release.

A new address is announced in a release and starts carrying traffic **15 days** after that release. Allowlist it during those 15 days.

When an address is removed, a new release is published. Drop it from your allowlist after that release.

To be notified, choose **Watch → Custom → Releases** on this repository, or subscribe to:

```
https://github.com/truefoundry/ip-ranges/releases.atom
```

## Reporting a problem

Something wrong or missing? [Open an issue](https://github.com/truefoundry/ip-ranges/issues) or contact TrueFoundry support. For anything security-sensitive, email security@truefoundry.com.
