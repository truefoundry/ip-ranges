# TrueFoundry IP ranges

Outbound IP addresses TrueFoundry uses when it connects to your systems — model endpoints, MCP servers, webhooks, databases, or private APIs. Allowlist them if you restrict inbound access to those systems.

These files are meant for automation. Build your allowlist from them rather than copying addresses by hand. See [Connect Private Models and MCP Servers](https://www.truefoundry.com/docs/ai-gateway/connect-private-models-mcp-servers#option-2-allowlist-truefoundry-ip-addresses) in the TrueFoundry docs for the full guide.

> [!IMPORTANT]
> These addresses are shared by every tenant on a control plane. An IP allowlist proves a request came from TrueFoundry, not that it came from **your** tenant. Keep authentication — an API key, OAuth, or mTLS — on any endpoint you allowlist.

## Pick the list for your control plane

Each control plane has its own list. Use the one that matches your tenant URL:

| Your tenant URL | Control plane | Gateways | Always-latest list |
| --- | --- | --- | --- |
| `<tenant>.truefoundry.cloud` | Global, hosted in Europe (Ireland) | Worldwide | https://truefoundry.github.io/ip-ranges/global.json |
| `<tenant>.us.truefoundry.cloud` | US | US | https://truefoundry.github.io/ip-ranges/us.json |

The source files are [`global/ip-ranges.json`](global/ip-ranges.json) and [`us/ip-ranges.json`](us/ip-ranges.json).

> [!NOTE]
> The US control plane is being rolled out. `us.json` currently lists only the control plane. US gateway addresses will be added through releases as they come online, following the [15-day notice](#when-addresses-change).

Replace `.json` with `.txt` for one CIDR per line. Each [GitHub Release](https://github.com/truefoundry/ip-ranges/releases) attaches the same lists, so you can pin a version: `https://github.com/truefoundry/ip-ranges/releases/download/v2026.10.12/global.json`.

## What to allowlist

Each list has one entry per hostname. `nat_ips` is every address TrueFoundry can send traffic from for that hostname.

```json
{
  "sync_token": "4d074f6e6d95f47e",
  "endpoints": [
    {
      "type": "control_plane",
      "hostname": "*.truefoundry.cloud",
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

Allowlist **two** entries:

1. The **`control_plane`** entry. The control plane also connects to your services.
2. The **`gateway`** entry for the gateway endpoint your tenant sends traffic through:

| Your tenant's gateway endpoint | Gateway entry to allowlist |
| --- | --- |
| `gateway.truefoundry.ai` (the default) | `gateway.truefoundry.ai`, which contains every regional gateway |
| A [multi-regional endpoint](https://www.truefoundry.com/docs/ai-gateway/globally-distributed-saas#configure-a-multi-regional-gateway-endpoint) | That region's hostname below, which already includes its fallback locations |

| Hostname | Gateway locations included |
| --- | --- |
| `gateway.truefoundry.ai` | Every regional gateway |
| `us.gateway.truefoundry.ai` | North Virginia, San Francisco, Dallas, and Toronto |
| `eu.gateway.truefoundry.ai` | London, Madrid, Gavle, and Doha |
| `sa.gateway.truefoundry.ai` | Sao Paulo |
| `au.gateway.truefoundry.ai` | Sydney, Melbourne, and Singapore |
| `as.gateway.truefoundry.ai` | Mumbai, Singapore, Doha, and Melbourne |

If you pinned a single location such as `orf.gateway.truefoundry.ai`, use the entry with that `airport_code`. Cape Town (`cpt`) is not part of any multi-regional endpoint, so it is only covered by `gateway.truefoundry.ai` and `cpt.gateway.truefoundry.ai`.

The gateway endpoint is configured per tenant. See [globally distributed SaaS gateway](https://www.truefoundry.com/docs/ai-gateway/globally-distributed-saas) for the locations and how to change it.

### Build the allowlist

```bash
# Global control plane, US multi-regional gateway endpoint.
# Use gw=gateway.truefoundry.ai for the default global endpoint,
# and us.json if your tenant is on the US control plane.
curl -s https://truefoundry.github.io/ip-ranges/global.json \
  | jq -r --arg gw us.gateway.truefoundry.ai \
      '.endpoints[] | select(.type == "control_plane" or .hostname == $gw) | .nat_ips[]' \
  | sort -u
```

## When addresses change

> [!WARNING]
> TrueFoundry does not notify customers individually when these addresses change. Keeping your allowlist current is your responsibility. Subscribe to releases and automate your allowlist so changes are picked up.

Every change is published as a [GitHub Release](https://github.com/truefoundry/ip-ranges/releases), and the always-latest lists update with it.

- A **new address** is announced in a release and starts carrying traffic **15 days** after that release. Allowlist it during those 15 days. The lists include it from the release that announces it.
- When an address is **removed**, a new release is published. Drop it from your allowlist after that release.

To be notified, choose **Watch → Custom → Releases** on this repository, or subscribe to:

```
https://github.com/truefoundry/ip-ranges/releases.atom
```

### Automate it

Run the [allowlist command](#build-the-allowlist) on a schedule — daily is plenty given the 15-day notice — and apply the result to your firewall, security group, or WAF.

Each JSON file has a top-level `sync_token`, which is also in the `.txt` header. It is a hash of the endpoint list and changes only when an address or hostname changes. Compare it with the last value you applied to skip work when nothing has changed.

## Reporting a problem

Something wrong or missing? [Open an issue](https://github.com/truefoundry/ip-ranges/issues) or contact TrueFoundry support. For anything security-sensitive, email security@truefoundry.com.
