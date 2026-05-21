# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```sh
uv sync                                              # install deps + the amy-patch CLI
uv run amy-patch --url <URL> [--mode blacklist|whitelist] [--tun-mode] [-o output/config.yaml]
uv run ruff check                                    # lint
uv run ty check                                      # type-check
```

There is no test suite. To exercise the code, run the CLI against a real subscription URL.

## Architecture

A single-module CLI (`src/amy_patch.py`) that rewrites a Clash subscription config. The pipeline in `main()`:

1. `load_config()` — fetch the subscription YAML over HTTP (`httpx`, async).
2. Read `clash-rules.yaml` and `extra-rules.yaml` **from the current working directory** — these are required and not packaged. `.example.yaml` versions are committed; the real files are gitignored. The CLI fails if they are absent.
3. `patch()` — mutate the config dict in place, then `yaml.dump` it.
4. Write to `--output` (default `./output/config.yaml`, gitignored).

`patch()` does the real work:

- Strips the first two `proxies` entries — providers prepend two pseudo-proxies whose names start with `当前流量` (traffic) and `到期时间` (expiry). It **raises `ValueError` if those two entries are not present**, so this assumption is load-bearing.
- `gen_proxy_groups()` parses each proxy name as `<region> <code> ...` (split on spaces, **raises if fewer than 2 parts**). It builds: one `url-test` group per region named `<region> Auto <code>`, a top-level `PROXY` selector, one `select` group per extra-provider rule, and a `FINAL-<mode>` group.
- Merges `rule-providers` from both config files; `rules` becomes `extra-provider-rules` + `rules-<mode>`.

### Config file contract

- `clash-rules.yaml` — `rule-providers` (base rulesets) plus `rules-blacklist` / `rules-whitelist` (the two selectable rule lists). `--mode` picks which `rules-<mode>` list and which `FINAL-<mode>` default is used.
- `extra-rules.yaml` — `extra-rule-providers` (per-service rulesets) and `extra-provider-rules` (the `RULE-SET,<provider>,<selector-name>` lines referencing them). Optional `nameserver-policy` is merged into `dns`.
- A provider with `default: DIRECT` makes its generated selector list `DIRECT` before `PROXY`. The `default` key is provider metadata only — it is stripped from `rule-providers` before the config is dumped, so it must never reach the output.

### Conventions that matter

- `patch()` deliberately `config.pop("rules")` before reassigning so `rules` lands last in the dump — `yaml.dump` uses `sort_keys=False` and preserves insertion order.
- `mode` is `Literal["blacklist", "whitelist"]` (the `Mode` type alias); keep that exhaustive if you add modes.
