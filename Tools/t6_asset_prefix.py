"""Read a bounded sequence of observed PS3 asset layouts, stopping on unknowns.

No byte scanning, enum extrapolation, shader translation, or world conversion.
Raw runtime buffer descriptors are preserved but not allocated or resolved.
"""
import argparse
import json
from pathlib import Path
import struct

from Tools.dump_inventory import write_report
from Tools.t6_metadata_prefix import prefix_reader, read_metadata
from Tools.t6_techniques import read_technique_set
from Tools.t6_models import read_model_reference


def inline_array(pointer, count):
    if count and pointer != 0xffffffff:
        raise ValueError(f'unresolved array pointer 0x{pointer:08x}')
    if not count and pointer:
        raise ValueError('non-null empty array pointer')


def read_texture_list(reader):
    name_ptr, n0, p0, n1, p1, n2, p2 = reader.words(7)
    name = reader.string(name_ptr)
    arrays = []
    for count, pointer in ((n0, p0), (n1, p1), (n2, p2)):
        inline_array(pointer, count)
        if count:
            reader.reserve(count * 4, alignment=4)
        arrays.append(list(reader.words(count)))
    return {'name': name, 'uint32_lists': arrays, 'list_semantics_verified': False}


def read_skinned_descriptor(reader):
    name_ptr, capacity, *pointers = reader.words(6)
    if any(p not in (0, 0xffffffff) for p in pointers):
        raise ValueError('unsupported runtime buffer pointer in skinned descriptor')
    return {
        'name': reader.string(name_ptr),
        'vertex_capacity': capacity,
        'runtime_pointers': pointers,
        'runtime_buffers_resolved': False,
    }


def read_string_table(reader):
    name_ptr, columns, rows, cells_ptr, indices_ptr = reader.words(5)
    count = columns * rows
    if count > 65536:
        raise ValueError('cell count exceeds uint16 lookup index space')
    inline_array(cells_ptr, count)
    inline_array(indices_ptr, count)
    name = reader.string(name_ptr)
    if count > (len(reader.data) - reader.offset) // 8:
        raise ValueError('truncated string table cells')
    if count:
        reader.reserve(count * 8, alignment=4)
    raw = [reader.words(2) for _ in range(count)]
    cells = [{'string': reader.string(pointer), 'hash': key} for pointer, key in raw]
    if count > (len(reader.data) - reader.offset) // 2:
        raise ValueError('truncated string table lookup index')
    if count:
        reader.reserve(count * 2, alignment=2)
    indices = list(struct.unpack_from(f'>{count}H', reader.data, reader.offset))
    reader.offset += count * 2
    if len(set(indices)) != count or any(i >= count for i in indices):
        raise ValueError('invalid string table lookup index permutation')
    return {'name': name, 'columns': columns, 'rows': rows, 'cells': cells, 'lookup_index': indices}


READERS = {
    5: ('model_dependency', read_model_reference),
    9: ('technique_set', read_technique_set),
    52: ('metadata', read_metadata),
    49: ('three_uint32_lists', read_texture_list),
    57: ('skinned_runtime_descriptor', read_skinned_descriptor),
    44: ('string_table', read_string_table),
}


def inspect_known_prefix(data):
    index, reader = prefix_reader(data)
    assets = []
    next_asset = None
    for record in index['records']:
        kind = record['type_id']
        offset = reader.offset
        if kind not in READERS or record['serialized_pointer'] != 'ffffffff':
            next_asset = {
                'index': record['index'], 'type_id': kind, 'file_offset': offset,
                'reason': 'unsupported type or non-inline asset reference',
            }
            break
        label, read = READERS[kind]
        try:
            payload = read(reader)
        except ValueError as error:
            raise ValueError(f'asset {record["index"]}, raw type {kind}, offset {offset}: {error}') from error
        assets.append({
            'index': record['index'], 'raw_type': kind, 'layout': label,
            'file_start': offset, 'file_end_exclusive': reader.offset, 'payload': payload,
        })
    return {
        'schema': 1,
        'profile': 'experimental-ps3-prefix-layouts',
        'source_sha256': index['source_sha256'],
        'declared_asset_count': index['asset_count'],
        'parsed_prefix_count': len(assets),
        'assets': assets,
        'next_asset': next_asset,
        'complete_asset_conversion': False,
        'world_geometry_verified': False,
        'engine_semantics_verified': False,
        'limitation': 'Observed prefix layouts only; runtime buffers, geometry and gameplay are not implemented.',
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
        result = inspect_known_prefix(data)
        write_report(result, args.report, args.decoded)
        print(json.dumps({k: v for k, v in result.items() if k != 'assets'}, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, f'Asset prefix inspection failed: {error}\n')


if __name__ == '__main__':
    main()
