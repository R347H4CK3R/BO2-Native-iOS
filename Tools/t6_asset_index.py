"""Read a declared big-endian T6 XAssetList; never scan for plausible tables.

This inventories records, not their nested payloads. It does not resolve
GfxWorld or establish that a map can be rendered.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct


INLINE = {0xffffffff, 0xfffffffe}


def inspect(data: bytes) -> dict:
    if len(data) < 64:
        raise ValueError('truncated XFile/XAssetList header')
    word = lambda offset: struct.unpack_from('>I', data, offset)[0]
    if word(0) + 40 != len(data):
        raise ValueError('XFile size does not match complete payload')
    script_count, script_ptr, depend_count, depend_ptr, asset_count, asset_ptr = struct.unpack_from('>6I', data, 40)
    cursor = 64

    def strings(count, pointer):
        nonlocal cursor
        if count == 0:
            if pointer != 0:
                raise ValueError('non-null empty string array is unsupported')
            return
        if pointer not in INLINE:
            raise ValueError('unresolved string array reference')
        if count > (len(data) - cursor) // 4:
            raise ValueError('truncated string pointer table')
        start = cursor
        cursor += count * 4
        for index in range(count):
            value = word(start + 4 * index)
            if value == 0:
                continue
            if value not in INLINE:
                raise ValueError('unresolved string reference')
            end = data.find(b'\0', cursor)
            if end < 0:
                raise ValueError('unterminated inline string')
            cursor = end + 1
        cursor = (cursor + 3) & ~3

    strings(script_count, script_ptr)
    strings(depend_count, depend_ptr)
    if asset_count and asset_ptr not in INLINE:
        raise ValueError('unresolved asset table reference')
    if not asset_count and asset_ptr:
        raise ValueError('non-null empty asset table is unsupported')
    if asset_count > (len(data) - cursor) // 8:
        raise ValueError('truncated asset table')
    table_offset = cursor
    counts = Counter()
    inline_count = referenced_count = null_count = 0
    records = []
    for index in range(asset_count):
        kind, pointer = struct.unpack_from('>2I', data, cursor)
        if kind >= 64:
            raise ValueError(f'invalid asset type {kind} at offset {cursor}')
        counts[str(kind)] += 1
        inline_count += pointer in INLINE
        null_count += pointer == 0
        referenced_count += pointer != 0 and pointer not in INLINE
        records.append({'index': index, 'type_id': kind, 'serialized_pointer': f'{pointer:08x}'})
        cursor += 8
    return {
        'schema': 1, 'source_sha256': hashlib.sha256(data).hexdigest(),
        'decoded_bytes': len(data), 'script_string_count': script_count,
        'dependency_count': depend_count, 'asset_count': asset_count,
        'table_offset': table_offset, 'asset_data_offset': cursor,
        'type_counts': dict(sorted(counts.items(), key=lambda item: int(item[0]))),
        'inline_asset_count': inline_count, 'referenced_asset_count': referenced_count,
        'null_asset_count': null_count, 'records': records,
        'world_geometry_verified': False,
        'limitation': 'Asset records only. Nested asset layouts and block-relative pointers are not resolved.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decoded', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.decoded.resolve() == args.report.resolve():
        parser.error('report must not overwrite decoded source')
    try:
        # Bound file allocation as well as fields inside the file.
        with args.decoded.open('rb') as stream:
            data = stream.read(256 * 1024 * 1024 + 1)
        if len(data) > 256 * 1024 * 1024:
            raise ValueError('decoded input exceeds 256 MiB inspection limit')
        report = inspect(data)
        with args.report.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
        print(json.dumps({k: v for k, v in report.items() if k != 'records'}, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f'Asset index failed: {error}\n')


if __name__ == '__main__':
    main()
