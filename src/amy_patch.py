from collections import defaultdict
from pathlib import Path
from typing import Literal

import httpx
import yaml

Mode = Literal["blacklist", "whitelist"]

TIMEOUT = 10
URL_TEST_URL = "http://www.gstatic.com/generate_204"
URL_TEST_INTERVAL = 600
URL_TEST_TOLERANCE = 50

# Some providers prepend two pseudo-proxies carrying account info; these prefixes
# identify them so they can be stripped before the real proxies are processed.
TRAFFIC_INFO_PREFIX = "当前流量"
EXPIRY_INFO_PREFIX = "到期时间"


async def load_config(url: str) -> tuple[dict, str]:
    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=TIMEOUT)
    config = yaml.safe_load(r.text)
    sub_info = r.headers.get("subscription-userinfo", "")
    return config, sub_info


def _proxy_direct_order(prefer_direct: bool) -> list[str]:
    return ["DIRECT", "PROXY"] if prefer_direct else ["PROXY", "DIRECT"]


def gen_proxy_groups(
    mode: Mode,
    proxy_names: list[str],
    providers: dict,
    provider_rules: list[str],
) -> list[dict]:
    proxy_groups = []
    region_proxies = defaultdict(list)
    for proxy_name in proxy_names:
        parts = proxy_name.split(" ")
        if len(parts) < 2:
            raise ValueError(
                f"Proxy name {proxy_name!r} does not match the expected "
                "'<region> <code> ...' format"
            )
        region_name = f"{parts[0]} Auto {parts[1]}"
        region_proxies[region_name].append(proxy_name)
    regions = list(region_proxies.keys())

    # all proxies
    proxy_groups.append(
        {"name": "PROXY", "type": "select", "proxies": regions + proxy_names}
    )

    # region groups
    for region, proxies in region_proxies.items():
        proxy_groups.append(
            {
                "name": region,
                "type": "url-test",
                "url": URL_TEST_URL,
                "interval": URL_TEST_INTERVAL,
                "tolerance": URL_TEST_TOLERANCE,
                "proxies": proxies,
            }
        )

    # provider groups
    for rule in provider_rules:
        _, provider, rule_name = rule.split(",")
        prefer_direct = providers[provider].get("default") == "DIRECT"
        proxy_groups.append(
            {
                "name": rule_name,
                "type": "select",
                "proxies": _proxy_direct_order(prefer_direct) + regions,
            }
        )

    # final
    proxy_groups.append(
        {
            "name": f"FINAL-{mode}",
            "type": "select",
            "proxies": _proxy_direct_order(mode != "whitelist"),
        }
    )

    return proxy_groups


def patch(
    config: dict,
    clash_rules: dict,
    extra_rules: dict,
    mode: Mode = "blacklist",
    tun_mode: bool = False,
) -> str:
    if "nameserver-policy" in extra_rules:
        if "nameserver-policy" not in config["dns"]:
            config["dns"]["nameserver-policy"] = {}
        config["dns"]["nameserver-policy"].update(extra_rules["nameserver-policy"])
    if tun_mode:
        config["tun"] = {
            "enable": True,
            "stack": "system",
        }

    # strip the leading traffic-usage / expiry info pseudo-proxies
    proxies = config["proxies"]
    if (
        len(proxies) < 2
        or not proxies[0]["name"].startswith(TRAFFIC_INFO_PREFIX)
        or not proxies[1]["name"].startswith(EXPIRY_INFO_PREFIX)
    ):
        raise ValueError(
            "Expected the first two proxies to be the traffic-usage and "
            "expiry info nodes"
        )
    config["proxies"] = proxies[2:]

    proxy_names = [p["name"] for p in config["proxies"]]

    # proxy-groups
    config["proxy-groups"] = gen_proxy_groups(
        mode,
        proxy_names,
        extra_rules["extra-rule-providers"],
        extra_rules["extra-provider-rules"],
    )

    # rule-providers
    config["rule-providers"] = (
        clash_rules["rule-providers"] | extra_rules["extra-rule-providers"]
    )
    for v in config["rule-providers"].values():
        if "default" in v:
            v.pop("default")

    # rules — pop before reassigning so the key moves to the end of the dump
    # (yaml.dump uses sort_keys=False, which preserves insertion order)
    config.pop("rules", None)
    config["rules"] = extra_rules["extra-provider-rules"] + clash_rules[f"rules-{mode}"]

    return yaml.dump(config, allow_unicode=True, sort_keys=False)


async def main(
    url: str,
    mode: Mode = "blacklist",
    tun_mode: bool = False,
    output: Path = Path("./output/config.yaml"),
) -> None:
    config, _ = await load_config(url)
    clash_rules = yaml.safe_load(Path("./clash-rules.yaml").read_text())
    extra_rules = yaml.safe_load(Path("./extra-rules.yaml").read_text())
    patched = patch(config, clash_rules, extra_rules, mode, tun_mode)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(patched)
    print(f"Patched config written to {output}")


def cli() -> None:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--mode", choices=["blacklist", "whitelist"], default="blacklist"
    )
    parser.add_argument("--tun-mode", action="store_true")
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("./output/config.yaml")
    )
    args = parser.parse_args()
    asyncio.run(main(args.url, args.mode, args.tun_mode, args.output))


if __name__ == "__main__":
    cli()
