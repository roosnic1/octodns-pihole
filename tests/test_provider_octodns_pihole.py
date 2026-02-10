from unittest.mock import MagicMock, patch

import pytest

from octodns.provider.plan import Plan
from octodns.record import Record
from octodns.record.change import Create, Delete, Update
from octodns.zone import Zone

from octodns_pihole import PiholeProvider

ZONE_NAME = "unit.tests."


def _get_provider(mock_client):
    with patch('octodns_pihole.PiHole6Client', return_value=mock_client):
        return PiholeProvider('test', 'http://pihole.mock', 'password')


def _get_zone():
    return Zone(ZONE_NAME, [])


def _make_config(hosts=None, cnames=None):
    return {
        "config": {
            "dns": {
                "hosts": hosts if hosts is not None else [],
                "cnameRecords": (cnames if cnames is not None else []),
            }
        }
    }


def _populate(mock_client, config):
    mock_client.config.get_config.return_value = config
    provider = _get_provider(mock_client)
    zone = _get_zone()
    provider.populate(zone)
    return zone, provider


def _mock_client_for_apply():
    mock_client = MagicMock()
    mock_client.config.get_config.return_value = _make_config()
    mock_client.config.add_local_a_record.return_value = {}
    mock_client.config.add_local_cname.return_value = {}
    mock_client.config.remove_local_a_record.return_value = {}
    mock_client.config.remove_local_cname.return_value = {}
    return mock_client


# --- Tests: populate ---


def test_populate_empty():
    zone, _ = _populate(MagicMock(), _make_config())
    assert len(zone.records) == 0


def test_populate_A():
    config = _make_config(
        hosts=["1.2.3.4 www.unit.tests.", "1.2.3.5 www.unit.tests."]
    )
    zone, _ = _populate(MagicMock(), config)
    record = list(zone.records)[0]
    assert record._type == "A"
    assert record.name == "www"
    assert sorted(record.values) == ["1.2.3.4", "1.2.3.5"]
    assert record.ttl == 86400


def test_populate_A_root():
    config = _make_config(hosts=["1.2.3.4 unit.tests."])
    zone, _ = _populate(MagicMock(), config)
    record = list(zone.records)[0]
    assert record._type == "A"
    assert record.name == ""
    assert list(record.values) == ["1.2.3.4"]


def test_populate_AAAA():
    config = _make_config(
        hosts=["2601:644:500:e210:62f8:1dff:feb8:947a aaaa.unit.tests."]
    )
    zone, _ = _populate(MagicMock(), config)
    record = list(zone.records)[0]
    assert record._type == "AAAA"
    assert record.name == "aaaa"
    assert list(record.values) == ["2601:644:500:e210:62f8:1dff:feb8:947a"]


def test_populate_CNAME():
    config = _make_config(cnames=["cname.unit.tests.,target.unit.tests.,300"])
    zone, _ = _populate(MagicMock(), config)
    record = list(zone.records)[0]
    assert record._type == "CNAME"
    assert record.name == "cname"
    assert record.value == "target.unit.tests."
    assert record.ttl == 300


def test_populate_filters_by_zone():
    config = _make_config(
        hosts=["1.1.1.1 other.tld.", "1.2.3.4 www.unit.tests."],
        cnames=["alias.other.tld.,target.other.tld.,300"],
    )
    zone, _ = _populate(MagicMock(), config)
    assert len(zone.records) == 1
    record = list(zone.records)[0]
    assert record.name == "www"


def test_populate_all():
    config = _make_config(
        hosts=[
            "1.2.3.4 unit.tests.",
            "1.2.3.5 unit.tests.",
            "2.2.3.6 www.unit.tests.",
            "2601:644:500:e210:62f8:1dff:feb8:947a aaaa.unit.tests.",
        ],
        cnames=["cname.unit.tests.,unit.tests.,300"],
    )
    zone, _ = _populate(MagicMock(), config)
    type_names = {r._type for r in zone.records}
    assert type_names == {"A", "AAAA", "CNAME"}
    # root A (2 values) + www A + aaaa AAAA + cname CNAME
    assert len(zone.records) == 4


# --- Tests: _apply create ---


def test_apply_create_A():
    mock_client = _mock_client_for_apply()
    provider = _get_provider(mock_client)

    zone = _get_zone()
    record = Record.new(
        zone,
        "www",
        {"type": "A", "ttl": 86400, "values": ["1.2.3.4", "5.6.7.8"]},
    )

    change = Create(record)
    plan = Plan(zone, zone, [change], True)
    provider._apply(plan)

    assert mock_client.config.add_local_a_record.call_count == 2
    mock_client.config.add_local_a_record.assert_any_call(
        "www.unit.tests.", "1.2.3.4"
    )
    mock_client.config.add_local_a_record.assert_any_call(
        "www.unit.tests.", "5.6.7.8"
    )


def test_apply_create_root_A():
    mock_client = _mock_client_for_apply()
    provider = _get_provider(mock_client)

    zone = _get_zone()
    record = Record.new(
        zone, "", {"type": "A", "ttl": 86400, "value": "1.2.3.4"}
    )

    change = Create(record)
    plan = Plan(zone, zone, [change], True)
    provider._apply(plan)

    mock_client.config.add_local_a_record.assert_called_once_with(
        "unit.tests.", "1.2.3.4"
    )


def test_apply_create_AAAA():
    mock_client = _mock_client_for_apply()
    provider = _get_provider(mock_client)

    zone = _get_zone()
    record = Record.new(
        zone, "ipv6", {"type": "AAAA", "ttl": 86400, "values": ["2001:db8::1"]}
    )

    change = Create(record)
    plan = Plan(zone, zone, [change], True)
    provider._apply(plan)

    mock_client.config.add_local_a_record.assert_called_once_with(
        "ipv6.unit.tests.", "2001:db8::1"
    )


def test_apply_create_CNAME():
    mock_client = _mock_client_for_apply()
    provider = _get_provider(mock_client)

    zone = _get_zone()
    record = Record.new(
        zone, "alias", {"type": "CNAME", "ttl": 300, "value": "www.unit.tests."}
    )

    change = Create(record)
    plan = Plan(zone, zone, [change], True)
    provider._apply(plan)

    mock_client.config.add_local_cname.assert_called_once_with(
        "alias.unit.tests.", "www.unit.tests.", ttl=300
    )


# --- Tests: _apply delete ---


def test_apply_delete_A():
    mock_client = _mock_client_for_apply()
    provider = _get_provider(mock_client)

    zone = _get_zone()
    existing = Record.new(
        zone,
        "www",
        {"type": "A", "ttl": 86400, "values": ["1.2.3.4", "5.6.7.8"]},
    )

    change = Delete(existing)
    plan = Plan(zone, zone, [change], True)
    provider._apply(plan)

    assert mock_client.config.remove_local_a_record.call_count == 2
    mock_client.config.remove_local_a_record.assert_any_call(
        "www.unit.tests.", "1.2.3.4"
    )
    mock_client.config.remove_local_a_record.assert_any_call(
        "www.unit.tests.", "5.6.7.8"
    )


def test_apply_delete_CNAME():
    mock_client = _mock_client_for_apply()
    provider = _get_provider(mock_client)

    zone = _get_zone()
    existing = Record.new(
        zone, "alias", {"type": "CNAME", "ttl": 300, "value": "www.unit.tests."}
    )

    change = Delete(existing)
    plan = Plan(zone, zone, [change], True)
    provider._apply(plan)

    mock_client.config.remove_local_cname.assert_called_once_with(
        "alias.unit.tests.", "www.unit.tests.", ttl=300
    )


# --- Tests: _apply update ---


def test_apply_update_A():
    mock_client = _mock_client_for_apply()
    provider = _get_provider(mock_client)

    zone = _get_zone()
    existing = Record.new(
        zone, "www", {"type": "A", "ttl": 86400, "value": "1.2.3.4"}
    )
    new = Record.new(
        zone, "www", {"type": "A", "ttl": 86400, "value": "9.8.7.6"}
    )

    change = Update(existing, new)
    plan = Plan(zone, zone, [change], True)
    provider._apply(plan)

    # Delete old
    mock_client.config.remove_local_a_record.assert_called_once_with(
        "www.unit.tests.", "1.2.3.4"
    )
    # Create new
    mock_client.config.add_local_a_record.assert_called_once_with(
        "www.unit.tests.", "9.8.7.6"
    )


# --- Tests: error handling ---


def test_apply_create_raises_on_error():
    mock_client = _mock_client_for_apply()
    mock_client.config.add_local_a_record.return_value = {
        "error": "something went wrong"
    }
    provider = _get_provider(mock_client)

    zone = _get_zone()
    record = Record.new(
        zone, "www", {"type": "A", "ttl": 86400, "value": "1.2.3.4"}
    )

    change = Create(record)
    plan = Plan(zone, zone, [change], True)

    with pytest.raises(ValueError):
        provider._apply(plan)


def test_apply_delete_raises_on_error():
    mock_client = _mock_client_for_apply()
    mock_client.config.remove_local_a_record.return_value = {
        "error": "not found"
    }
    provider = _get_provider(mock_client)

    zone = _get_zone()
    existing = Record.new(
        zone, "www", {"type": "A", "ttl": 86400, "value": "1.2.3.4"}
    )

    change = Delete(existing)
    plan = Plan(zone, zone, [change], True)

    with pytest.raises(ValueError):
        provider._apply(plan)
