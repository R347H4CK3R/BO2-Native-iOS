import struct
import unittest

from Tools.t6_metadata_prefix import inspect_prefix


def fixture(entries=None, first_type=52):
    # Virtual block starts at the asset table (offset zero in this fixture).
    # Two records occupy 16 virtual bytes. Asset structs live in TEMP.
    if entries is None:
        entries = [(1, 2, 0xffffffff), (3, 2, 0xa0000011)]
    body = struct.pack('>6I', 0, 0, 0, 0, 2, 0xffffffff)
    body += struct.pack('>4I', first_type, 0xffffffff, 49, 0xffffffff)
    body += struct.pack('>3I', 0xffffffff, len(entries), 0xffffffff)
    body += b'synthetic_zone\0'
    body += b''.join(struct.pack('>3I', *entry) for entry in entries)
    body += b'value\0' * sum(e[2] == 0xffffffff for e in entries)
    return struct.pack('>10I', len(body), 0, *([0] * 5 + [4096, 0, 0])) + body


class MetadataPrefixTests(unittest.TestCase):
    def test_parses_inline_values_and_virtual_name_alias(self):
        result = inspect_prefix(fixture())
        self.assertEqual(result['metadata']['name'], 'synthetic_zone')
        self.assertEqual([e['value'] for e in result['metadata']['entries']], ['value', 'synthetic_zone'])
        self.assertEqual(result['metadata']['entries'][1]['key_hash'], 3)
        self.assertEqual(result['next_asset']['type_id'], 49)
        self.assertFalse(result['complete_asset_conversion'])
        self.assertFalse(result['world_geometry_verified'])

    def test_rejects_unknown_type_instead_of_scanning(self):
        with self.assertRaisesRegex(ValueError, 'first asset type'):
            inspect_prefix(fixture(first_type=6))

    def test_rejects_unresolved_virtual_alias(self):
        with self.assertRaisesRegex(ValueError, 'unresolved string alias'):
            inspect_prefix(fixture([(1, 2, 0xa0000101)]))

    def test_rejects_nonvirtual_alias(self):
        with self.assertRaisesRegex(ValueError, 'unresolved string alias'):
            inspect_prefix(fixture([(1, 2, 0x80000011)]))

    def test_rejects_truncated_inline_string(self):
        data = bytearray(fixture())
        data.pop()
        struct.pack_into('>I', data, 0, len(data) - 40)
        with self.assertRaisesRegex(ValueError, 'unterminated'):
            inspect_prefix(bytes(data))

    def test_rejects_declared_virtual_block_overrun(self):
        data = bytearray(fixture())
        struct.pack_into('>I', data, 28, 8)
        with self.assertRaisesRegex(ValueError, 'virtual block'):
            inspect_prefix(bytes(data))

    def test_rejects_noninline_first_asset(self):
        data = bytearray(fixture())
        struct.pack_into('>I', data, 68, 0xa0000011)
        with self.assertRaisesRegex(ValueError, 'first asset pointer'):
            inspect_prefix(bytes(data))

    def test_rejects_truncated_entries(self):
        data = bytearray(fixture())
        struct.pack_into('>I', data, 84, 100000)
        with self.assertRaisesRegex(ValueError, 'entry table'):
            inspect_prefix(bytes(data))


if __name__ == '__main__':
    unittest.main()
