# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

octodns-pihole is an [octoDNS](https://github.com/octodns/octodns) provider that manages local DNS records (A, AAAA, CNAME) in Pi-hole v6. It uses the [pihole6api](https://pypi.org/project/pihole6api/) library (`PiHole6Client`) for API communication. It follows the standard octoDNS provider pattern.

## Development Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests (network-disabled)
pytest --disable-network

# Run tests with coverage
pytest --disable-network --cov=octodns_pihole --cov-report=term-missing

# Run a single test
pytest tests/test_provider_octodns_pihole.py::test_populate_A
pytest tests/test_provider_octodns_pihole.py::test_apply_create_CNAME

# Lint (pyflakes)
pyflakes octodns_pihole/*.py tests/*.py

# Format (isort + black)
isort octodns_pihole/ tests/
black octodns_pihole/ tests/
```

To test against a real Pi-hole instance:
```bash
docker compose up
octodns-sync --config-file=./example/config.yaml          # dry run
octodns-sync --config-file=./example/config.yaml --doit   # apply
```

## Code Style

- **Black** with 80 char line length, single quotes preserved (`skip-string-normalization`), no magic trailing commas
- **isort** with `black` profile, custom section ordering (OCTODNS between THIRDPARTY and FIRSTPARTY)
- **pyflakes** for linting

## Architecture

All source code lives in a single module: `octodns_pihole/__init__.py`.

**PiholeProvider** — octoDNS `BaseProvider` subclass. Uses `PiHole6Client` from `pihole6api` for all Pi-hole communication. Translates between octoDNS zone/record model and Pi-hole's flat host/CNAME lists. Key behaviors:
- Pi-hole has no zone concept; `populate()` filters records by checking if the zone name appears in the FQDN
- Config is fetched via `self._client.config.get_config()` which returns hosts and cnameRecords
- Mutations use `self._client.config.add_local_a_record()`, `add_local_cname()`, `remove_local_a_record()`, `remove_local_cname()`
- TTL is only meaningful for CNAME records; `_process_desired_zone()` normalizes non-CNAME TTLs to `DEFAULT_TTL` (86400) to prevent false diffs
- Updates are implemented as delete + create
- Host entries use format `"ip name"`, CNAME entries use `"name,target,ttl"`

## Testing

Tests live in `tests/test_provider_octodns_pihole.py` as standalone functions (not class-based). `PiHole6Client` is mocked with `unittest.mock.MagicMock` and `patch`. Tests cover populate (per record type, zone filtering), apply (create/delete/update for each type), and error handling.