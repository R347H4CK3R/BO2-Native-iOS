import struct
import unittest

from Tools.t6_metadata_prefix import PrefixReader
from Tools.t6_asset_prefix import read_texture_list, read_skinned_descriptor, read_string_table, inspect_known_prefix


def reader(data, capacity=10000):
    return PrefixReader(data, 0, 0, capacity)


class PrefixIntegrationTests(unittest.TestCase):
    def fixture(self):
        body = struct.pack('>6I', 0, 0, 0, 0, 5, 0xffffffff)
        body += b''.join(struct.pack('>2I', kind, 0xffffffff) for kind in (52, 49, 57, 44, 9))
        body += struct.pack('>3I', 0xffffffff, 0, 0) + b'zone\0'
        body += struct.pack('>7I', 0xffffffff, 1, 0xffffffff, 0, 0, 0, 0) + b'textures\0' + struct.pack('>I', 123)
        body += struct.pack('>6I', 0xffffffff, 100, *([0xffffffff] * 4)) + b'skin\0'
        body += struct.pack('>5I', 0xffffffff, 1, 1, 0xffffffff, 0xffffffff) + b'strings\0'
        body += struct.pack('>2I', 0xa0000029, 42) + struct.pack('>H', 0)
        return struct.pack('>10I', len(body), 0, *([0] * 5 + [4096, 0, 0])) + body

    def test_cross_asset_alias_and_unknown_boundary(self):
        data = self.fixture()
        result = inspect_known_prefix(data)
        self.assertEqual(result['parsed_prefix_count'], 4)
        self.assertEqual(result['assets'][3]['payload']['cells'][0]['string'], 'zone')
        self.assertEqual(result['next_asset']['index'], 4)
        self.assertEqual(result['next_asset']['type_id'], 9)
        self.assertEqual(result['next_asset']['file_offset'], len(data))
        self.assertFalse(result['complete_asset_conversion'])

    def test_supported_type_with_external_reference_stops(self):
        data = bytearray(self.fixture())
        struct.pack_into('>I', data, 76, 0xa0000001)
        result = inspect_known_prefix(bytes(data))
        self.assertEqual(result['parsed_prefix_count'], 1)
        self.assertEqual(result['next_asset']['index'], 1)


class TextureListTests(unittest.TestCase):
    def test_three_arrays_and_virtual_alignment(self):
        data = struct.pack('>7I', 0xffffffff, 2, 0xffffffff, 1, 0xffffffff, 0, 0)
        data += b'table\0' + struct.pack('>3I', 123, 456, 789)
        stream = reader(data)
        result = read_texture_list(stream)
        self.assertEqual(result['name'], 'table')
        self.assertEqual(result['uint32_lists'], [[123, 456], [789], []])
        self.assertEqual(stream.offset, len(data))
        self.assertEqual(stream.virtual_offset, 20)

    def test_unresolved_array_does_not_consume_unrelated_bytes(self):
        data = struct.pack('>7I', 0xffffffff, 1, 0xa0000401, 0, 0, 0, 0) + b'table\0'
        with self.assertRaisesRegex(ValueError, 'array pointer'):
            read_texture_list(reader(data))

    def test_truncated_array(self):
        data = struct.pack('>7I', 0xffffffff, 3, 0xffffffff, 0, 0, 0, 0) + b'table\0' + bytes(4)
        with self.assertRaisesRegex(ValueError, 'truncated'):
            read_texture_list(reader(data))


class SkinnedDescriptorTests(unittest.TestCase):
    def test_preserves_runtime_pointers_without_claiming_geometry(self):
        pointers = [0xffffffff] * 4
        data = struct.pack('>6I', 0xffffffff, 100, *pointers) + b'buffer\0'
        stream = reader(data)
        result = read_skinned_descriptor(stream)
        self.assertEqual(result['vertex_capacity'], 100)
        self.assertEqual(result['runtime_pointers'], pointers)
        self.assertFalse(result['runtime_buffers_resolved'])
        self.assertEqual(stream.offset, len(data))


class StringTableTests(unittest.TestCase):
    def table(self, indices=(1, 2, 0), third_pointer=1):
        # Name starts at VIRTUAL address 0, so pointer 1 aliases it.
        # Real aliases also carry VIRTUAL's block bits.
        data = struct.pack('>5I', 0xffffffff, 3, 1, 0xffffffff, 0xffffffff)
        data += b'table\0'
        data += struct.pack('>6I', 0xffffffff, 300, 0xffffffff, 100, 0xa0000000 | third_pointer, 200)
        data += b'one\0two\0' + struct.pack('>3H', *indices)
        return data

    def test_inline_cells_alias_and_lookup_permutation(self):
        data = self.table()
        stream = reader(data)
        result = read_string_table(stream)
        self.assertEqual(result['columns'], 3)
        self.assertEqual(result['rows'], 1)
        self.assertEqual([c['string'] for c in result['cells']], ['one', 'two', 'table'])
        self.assertEqual(result['lookup_index'], [1, 2, 0])
        self.assertEqual(stream.offset, len(data))

    def test_rejects_missing_string_alias(self):
        with self.assertRaisesRegex(ValueError, 'unresolved string alias'):
            read_string_table(reader(self.table(third_pointer=1000)))

    def test_rejects_out_of_range_lookup(self):
        with self.assertRaisesRegex(ValueError, 'lookup index'):
            read_string_table(reader(self.table(indices=(0, 1, 3))))

    def test_rejects_duplicate_lookup(self):
        with self.assertRaisesRegex(ValueError, 'lookup index'):
            read_string_table(reader(self.table(indices=(0, 0, 1))))

    def test_rejects_cell_count_beyond_uint16_index_space(self):
        data = struct.pack('>5I', 0xffffffff, 65537, 1, 0xffffffff, 0xffffffff) + b'table\0'
        with self.assertRaisesRegex(ValueError, 'cell count'):
            read_string_table(reader(data))

    def test_rejects_truncated_lookup(self):
        with self.assertRaisesRegex(ValueError, 'truncated'):
            read_string_table(reader(self.table()[:-1]))

    def test_empty_table(self):
        data = struct.pack('>5I', 0xffffffff, 0, 0, 0, 0) + b'empty\0'
        result = read_string_table(reader(data))
        self.assertEqual(result['cells'], [])
        self.assertEqual(result['lookup_index'], [])


if __name__ == '__main__':
    unittest.main()
