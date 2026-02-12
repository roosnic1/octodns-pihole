import logging
from collections import defaultdict
from ipaddress import ip_address

from pihole6api import PiHole6Client

from octodns.provider.base import BaseProvider
from octodns.record import Record


class PiholeProvider(BaseProvider):
    DEFAULT_TTL = 86400  # TTL does not matter/unsupported for Pi-hole

    SUPPORTS_GEO = False
    SUPPORTS_DYNAMIC = False
    SUPPORTS_ROOT_NS = False
    SUPPORTS = set(('A', 'AAAA', 'CNAME'))

    def __init__(self, id, url, password, *args, **kwargs):
        self.log = logging.getLogger(f'PiholeProvider[{id}]')
        self.log.debug('__init__: id=%s, url=%s', id, url)
        super().__init__(id, *args, **kwargs)

        self._client = PiHole6Client(url, password)

    def _data_for_multiple(self, type, records):
        return {
            'ttl': PiholeProvider.DEFAULT_TTL,
            'type': type,
            'values': [r for r in records],
        }

    _data_for_A = _data_for_multiple
    _data_for_AAAA = _data_for_multiple

    def _data_for_CNAME(self, _type, records):
        values = records[0].split(',')

        return {
            'ttl': int(values[1]) or PiholeProvider.DEFAULT_TTL,
            'type': _type,
            'value': f'{values[0]}',
        }

    def _process_desired_zone(self, desired):
        # TTL is not supported for records in Pi-hole.
        # Reset desired records TTL to a known default to
        # ignore the source provider and prevent false changes.
        for record in desired.records:
            record = record.copy()
            if record._type != 'CNAME':
                record.ttl = PiholeProvider.DEFAULT_TTL
            desired.add_record(record, replace=True)

        return super()._process_desired_zone(desired)

    def populate(self, zone, target=False, lenient=False):
        self.log.debug(
            'populate: name=%s, target=%s, lenient=%s',
            zone.name,
            target,
            lenient,
        )

        values = defaultdict(lambda: defaultdict(list))
        pihole_config = self._client.config.get_config()
        # A/AAAA "records"
        for entry in pihole_config['config']['dns']['hosts']:
            ip, name = entry.split(' ', 1)
            # Pi-hole does not really have the concept of zones
            # we only want to return "records" within the zone
            if zone.name not in name:
                continue

            # Strip the zone name from the list entry
            name = name.split(zone.name, 1)[0].rstrip('.')

            version = ip_address(ip).version
            if version == 4:
                values[name]['A'].append(ip)
            elif version == 6:
                values[name]['AAAA'].append(ip)

        # CNAME "records"
        for entry in pihole_config['config']['dns']['cnameRecords']:
            name, target = entry.split(',', 1)

            # Pi-hole does not really have the concept of zones
            # we only want to return "records" within the zone
            if zone.name not in name:
                continue

            # Strip the zone name from the list entry
            name = name.split(f".{zone.name}", 1)[0]
            values[name]['CNAME'].append(target)

        before = len([r for r in values.values()])
        for name, types in values.items():
            for _type, records in types.items():
                data_for = getattr(self, f'_data_for_{_type}')
                record = Record.new(
                    zone,
                    name,
                    data_for(_type, records),
                    source=self,
                    lenient=lenient,
                )
                zone.add_record(record, lenient=lenient)

        exists = len(values) > 0
        self.log.info(
            'populate:   found %s records, exists=%s',
            len(zone.records) - before,
            exists,
        )
        return exists

    def _params_for_multiple(self, record):
        for value in record.values:
            yield {
                'name': (
                    f"{record.name}.{record.zone.name}"
                    if record.name
                    else record.zone.name
                ),
                'data': value,
            }

    _params_for_A = _params_for_multiple
    _params_for_AAAA = _params_for_multiple

    def _params_for_single(self, record):
        yield {
            'name': (
                f"{record.name}.{record.zone.name}"
                if record.name
                else record.zone.name
            ),
            'ttl': record.ttl,
            'data': record.value,
        }

    _params_for_CNAME = _params_for_single

    def _apply_Create(self, change):
        new = change.new
        params_for = getattr(self, f'_params_for_{new._type}')
        for params in params_for(new):
            record_type = change.record._type
            if record_type in ('A', 'AAAA'):
                result = self._client.config.add_local_a_record(
                    params['name'], params['data']
                )
            elif record_type == 'CNAME':
                result = self._client.config.add_local_cname(
                    params['name'], params['data'], ttl=params['ttl']
                )
            else:
                result = None

            if result is None or 'error' in result:
                raise ValueError(
                    f"Failed to apply change for record: {change.record.name}"
                )

    def _apply_Update(self, change):
        self._apply_Delete(change)
        self._apply_Create(change)

    def _apply_Delete(self, change):
        existing = change.existing
        params_for = getattr(self, f'_params_for_{existing._type}')
        for params in params_for(existing):
            record_type = change.record._type
            if record_type in ('A', 'AAAA'):
                result = self._client.config.remove_local_a_record(
                    params['name'], params['data']
                )
            elif record_type == 'CNAME':
                result = self._client.config.remove_local_cname(
                    params['name'], params['data'], ttl=params['ttl']
                )
            else:
                result = None

            if result is None or 'error' in result:
                raise ValueError(
                    f"Failed to delete the record: {change.record.name}"
                )

    def _apply(self, plan):
        desired = plan.desired
        changes = plan.changes
        self.log.debug(
            '_apply: zone=%s, len(changes)=%d', desired.name, len(changes)
        )

        for change in changes:
            class_name = change.__class__.__name__
            getattr(self, f'_apply_{class_name}')(change)

        self.log.info('_apply: sending changes to Pi-hole')
