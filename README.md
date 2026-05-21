# amy-patch

A small utility that patches a Clash subscription config with custom rule providers, proxy groups, and rules.

Given a subscription URL, it:

- Strips the "current traffic" / "expiration" pseudo-proxies that some providers prepend.
- Groups remaining proxies by region into `url-test` groups.
- Generates a `PROXY` selector and per-rule selectors based on `extra-rules.yaml`.
- Merges rule providers from `clash-rules.yaml` and `extra-rules.yaml`.
- Writes the patched config to a file (`output/config.yaml` by default).

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/)

## Install

```sh
uv sync
```

This installs the project and exposes the `amy-patch` CLI.

## Configuration

Copy the example files and edit them as needed:

```sh
cp clash-rules.example.yaml clash-rules.yaml
cp extra-rules.example.yaml extra-rules.yaml
```

- `clash-rules.yaml` — base rule providers and rule lists (with `rules-blacklist` and `rules-whitelist` variants).
- `extra-rules.yaml` — extra rule providers (`extra-rule-providers`) and the rules that reference them (`extra-provider-rules`). A provider with `default: DIRECT` is treated as direct-by-default in its generated selector.

Both files must exist in the current working directory when running the CLI.

## Usage

```sh
uv run amy-patch --url <SUBSCRIPTION_URL> [--mode blacklist|whitelist] [--tun-mode] [-o config.yaml]
```

Arguments:

- `--url` — Clash subscription URL.
- `--mode` — `blacklist` (default) or `whitelist`. Controls the final rule set and the default action of `FINAL-<mode>`.
- `--tun-mode` — Flag; enable TUN mode with the `system` stack.
- `-o`, `--output` — Output file path. Defaults to `./output/config.yaml`. Parent directories are created as needed.

The patched config is written to the output file (`output/` is gitignored):

```sh
uv run amy-patch --url <SUBSCRIPTION_URL> -o output/config.yaml
```

## Development

```sh
uv run ruff check
uv run ty check
```
