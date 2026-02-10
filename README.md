## Pi-hole provider for octoDNS

An [octoDNS](https://github.com/octodns/octodns/) provider that targets
[Pi-hole](https://docs.pi-hole.net). Uses the
[pihole6api](https://pypi.org/project/pihole6api/) library for API communication.

Pi-hole version 6 is supported.

This provider manages matching A/AAAA/CNAME records with Pi-hole's
`Local DNS Records`. It will manage host and CNAME entries that match
domain names under management by OctoDNS. Other existing Pi-hole entries are
untouched.

TTL values are unsupported on host records (A/AAAA). CNAME records support
an optional TTL.

### Installation

```
pip install octodns-pihole
```

### Configuration

```yaml
providers:
  pihole:
    class: octodns_pihole.PiholeProvider
    url: https://pihole.lan:443
    password: env/PIHOLE_PASSWORD
    strict_supports: false # ignore unsupported records
```

### Support Information

#### Records

Pi-hole supports A, AAAA, and CNAME. PTR records will automatically exist for
A and AAAA records.

#### Dynamic

PiholeProvider does not support dynamic records.

### Development

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest --disable-network

# Run tests with coverage
pytest --disable-network --cov=octodns_pihole --cov-report=term-missing

# Lint
pyflakes octodns_pihole/*.py tests/*.py

# Format
isort octodns_pihole/ tests/
black octodns_pihole/ tests/
```

There is a [docker-compose.yml](docker-compose.yml) file included in the repo
that will set up a Pi-hole server with the API enabled for use in development.
The admin password/api-key for it is `correct horse battery staple`.

A configuration [example](example/) is provided and can be used along with the
[docker-compose.yml](docker-compose.yml):

1. Launch the container.

        docker compose up

    * Admin UI: http://localhost/admin
    * API Docs: http://localhost/api/docs

2. Run octodns-sync against the container

        octodns-sync --config-file=./example/config.yaml

3. Synchronize changes with Pi-hole

        octodns-sync --config-file=./example/config.yaml --doit

4. View records within the admin UI:
   [Local DNS Records](http://localhost/admin/settings/dnsrecords)