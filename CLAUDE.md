# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

octodns-pihole is an [octoDNS](https://github.com/octodns/octodns) provider that manages local DNS records (A, AAAA, CNAME) in Pi-hole v6 via its HTTP API. It follows the standard octoDNS provider pattern.

## Development Commands

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests (network-disabled)
pytest --disable-network

# Run tests with coverage
pytest --disable-network --cov=octodns_pihole --cov-report=term-missing

# Run a single test
pytest tests/test_pihole_client.py
pytest tests/test_provider_octodns_pihole.py::TestPiholeProvider::test_apply

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

**PiholeClient** — HTTP client for Pi-hole API v6. Handles session-based auth (with optional TOTP 2FA). Records are cached in memory (`_host_cache`, `_cname_cache`) and bulk-applied via a single `PATCH /api/config` call.

**PiholeProvider** — octoDNS `BaseProvider` subclass. Translates between octoDNS zone/record model and Pi-hole's flat host/CNAME lists. Key behaviors:
- Pi-hole has no zone concept; `populate()` filters records by checking if the zone name appears in the FQDN
- TTL is meaningless in Pi-hole; `_process_desired_zone()` normalizes all TTLs to `DEFAULT_TTL` (86400) to prevent false diffs
- Updates are implemented as delete + create
- Host entries use format `"ip name"`, CNAME entries use `"name,target"`

## Testing

Tests use `pytest` with `requests_mock` for HTTP mocking and `pytest-network` to disable real network calls. Coverage must be 100% on `octodns_pihole/`. Fixtures live in `tests/fixtures/` (JSON Pi-hole API responses) and `tests/config/` (octoDNS zone YAML).
