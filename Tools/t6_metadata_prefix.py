"""Experimental PS3 metadata-prefix reader; no general type map or world decoder.

The supported profile is a first asset with raw type 52 and an inline
name/count/pairs layout. The layout was checked against the supplied decoded
Tranzit stream, but has not been validated against engine execution. Unknown
types and string references are rejected, never guessed or searched for.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from Tools.t6_asset_index import inspect
from Tools.dump_inventory import write_report


class PrefixReader:
    def __init__(self, data, offset, virtual_offset, virtual_limit):
        self.data = data
        self.offset = offset
        self.virtual_offset = virtual_offset
        self.virtual_limit = virtual_limit
        self.strings = {}
        self.reserve(0)

    def reserve(self, size, alignment=1):
        start = (self.virtual_offset + alignment - 1) & ~(alignment - 1)
        if start + size > self.virtual_limit:
            raise ValueError('declared virtual block capacity exceeded')
        self.virtual_offset = start + size
        return start

    def words(self, count):
        if count < 0 or count > (len(self.data) - self.offset) // 4:
            raise ValueError('truncated word array')
        values = struct.unpack_from(f'>{count}I', self.data, self.offset)
        self.offset += count * 4
        return values

    def string(self, pointer):
        if pointer == 0:
            return None
        if pointer != 0xffffffff:
            if pointer not in self.strings:
                raise ValueError(f'unresolved string alias 0x{pointer:08x}')
            return self.strings[pointer]
        end = self.data.find(b'\0', self.offset, min(len(self.data), self.offset + 1024 * 1024))
        if end < 0:
            raise ValueError('unterminated or oversized inline string')
        value = self.data[self.offset:end].decode('utf-8')
        address = self.reserve(end + 1 - self.offset)
        # T6 32-bit zone references encode a three-bit block and offset+1.
        # Block 5 is VIRTUAL. Register only bytes this reader actually consumed.
        self.strings[(5 << 29) | (address + 1)] = value
        self.offset = end + 1
        return value


def inspect_prefix(data: bytes) -> dict:
    index = inspect(data)
    if not index['records'] or index['records'][0]['type_id'] != 52:
        raise ValueError('unsupported first asset type; expected observed PS3 profile 52')
    if index['records'][0]['serialized_pointer'] != 'ffffffff':
        raise ValueError('unsupported first asset pointer; inline asset required')
    start = index['asset_data_offset']
    virtual_limit = struct.unpack_from('>I', data, 28)[0]
    # The 40-byte XFile and 24-byte TEMP XAssetList are not VIRTUAL allocations.
    # This profile assumes no pre-asset allocations in other blocks.
    reader = PrefixReader(data, start, start - 64, virtual_limit)
    name_pointer, count, pairs_pointer = reader.words(3)  # TEMP struct
    if name_pointer != 0xffffffff:
        raise ValueError('metadata name must be an inline string')
    name = reader.string(name_pointer)
    if count and pairs_pointer != 0xffffffff:
        raise ValueError('unresolved metadata entry table pointer')
    if not count and pairs_pointer:
        raise ValueError('non-null empty metadata entry table')
    if count > (len(data) - reader.offset) // 12:
        raise ValueError('truncated metadata entry table')
    if count:
        reader.reserve(count * 12, alignment=4)
    raw_entries = [reader.words(3) for _ in range(count)]
    entries = [
        {'key_hash': key, 'namespace_hash': namespace, 'value': reader.string(pointer)}
        for key, namespace, pointer in raw_entries
    ]
    next_asset = None
    if len(index['records']) > 1:
        next_asset = {'index': 1, 'type_id': index['records'][1]['type_id'], 'file_offset': reader.offset}
    return {
        'schema': 1,
        'profile': 'experimental-ps3-type52-metadata-prefix',
        'source_sha256': hashlib.sha256(data).hexdigest(),
        'metadata': {'name': name, 'entries': entries},
        'source_range': {'start': start, 'end_exclusive': reader.offset},
        'next_asset': next_asset,
        'complete_asset_conversion': False,
        'world_geometry_verified': False,
        'engine_semantics_verified': False,
        'limitation': 'One metadata layout only. No general PS3 asset-type mapping, nested world parser, or runtime is implemented.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decoded', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        with args.decoded.open('rb') as stream:
            data = stream.read(256 * 1024 * 1024 + 1)
        if len(data) > 256 * 1024 * 1024:
            raise ValueError('input exceeds 256 MiB inspection budget')
        result = inspect_prefix(data)
        write_report(result, args.report, args.decoded)
        print(json.dumps({k: v for k, v in result.items() if k != 'metadata'}, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f'Metadata prefix inspection failed: {error}\n')


if __name__ == '__main__':
    main()
