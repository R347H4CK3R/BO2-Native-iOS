import struct
import unittest

from Tools.t6_metadata_prefix import PrefixReader
from Tools.t6_techniques import read_technique_set, shader


def fixture(shader_words=(0, 0, 0), arg_type=3):
    # 32 technique slots; the second references the first at VIRTUAL offset 8.
    data = struct.pack('>I', 0xffffffff) + bytes((0, 1, 0, 0))
    data += struct.pack('>32I', 0xffffffff, 0xa0000009, *([0] * 30))
    data += b'techset\0'
    data += struct.pack('>IHH', 0xffffffff, 0x84, 1)
    data += struct.pack('>3I', 0xffffffff, 0xffffffff, 0xffffffff)
    data += bytes((1, 1, 0, 0)) + bytes(20) + struct.pack('>I', 0xffffffff)
    data += struct.pack('>4I', 0xffffffff, *shader_words) + b',vs\0'
    data += bytes((1, 0)) + bytes(32)
    data += struct.pack('>4I', 0xffffffff, 0, 0, 0) + b',ps\0'
    data += struct.pack('>HHIHHI', arg_type, 4, 123, 3, 0, 456)
    data += b'pass\0'
    return data


class TechniqueTests(unittest.TestCase):
    def test_referenced_shaders_and_shared_technique(self):
        data = fixture()
        reader = PrefixReader(data, 0, 0, 4096)
        result = read_technique_set(reader)
        self.assertEqual(result['name'], 'techset')
        self.assertEqual(len(result['techniques']), 32)
        self.assertIsNone(result['techniques'][2])
        tech = result['techniques'][0]
        self.assertEqual(tech['name'], 'pass')
        self.assertEqual(tech['passes'][0]['vertex_shader']['name'], ',vs')
        self.assertEqual(tech['passes'][0]['pixel_shader']['name'], ',ps')
        self.assertFalse(tech['passes'][0]['vertex_shader']['program_available'])
        self.assertEqual(tech['passes'][0]['arguments'][0]['value'], 123)
        self.assertEqual(result['techniques'][1], tech)
        self.assertEqual(reader.offset, len(data))

    def test_nonempty_shader_program_is_not_skipped(self):
        with self.assertRaisesRegex(ValueError, 'shader program'):
            read_technique_set(PrefixReader(fixture(shader_words=(1, 0, 0)), 0, 0, 4096))

    def test_unknown_argument_kind_rejected(self):
        with self.assertRaisesRegex(ValueError, 'argument type'):
            read_technique_set(PrefixReader(fixture(arg_type=99), 0, 0, 4096))

    def test_truncation_rejected(self):
        data = fixture()[:-1]
        with self.assertRaisesRegex(ValueError, 'unterminated'):
            read_technique_set(PrefixReader(data, 0, 0, 4096))

    def test_unresolved_technique_alias_rejected(self):
        data = bytearray(fixture())
        struct.pack_into('>I', data, 12, 0xa0009999)
        with self.assertRaisesRegex(ValueError, 'unresolved technique'):
            read_technique_set(PrefixReader(bytes(data), 0, 0, 4096))


class ShaderPayloadTests(unittest.TestCase):
    def test_split_pixel_payload_uses_only_descriptor_in_virtual_block(self):
        program = bytes(range(48))
        descriptor = bytes(range(16))
        data = struct.pack('>4I', 0xffffffff, 0xffffffff, 0xffffffff, 0x00020880)
        data += b'ps\0' + program + descriptor
        reader = PrefixReader(data, 0, 0, 4096)
        result = shader(reader, 0xffffffff, 'pixel_shader', 0)
        self.assertEqual(bytes.fromhex(result['ps3_program_hex']), program)
        self.assertEqual(bytes.fromhex(result['cached_descriptor_hex']), descriptor)
        self.assertEqual(reader.offset, len(data))
        self.assertEqual(reader.virtual_offset, 32)
        self.assertFalse(result['physical_relocation_verified'])

    def test_split_pixel_truncation_rejected(self):
        data = struct.pack('>4I', 0xffffffff, 0xffffffff, 0xffffffff, 0x00020880)
        data += b'ps\0' + bytes(63)
        with self.assertRaisesRegex(ValueError, 'truncated'):
            shader(PrefixReader(data, 0, 0, 4096), 0xffffffff, 'pixel_shader', 0)

    def test_split_pixel_zero_units_still_has_fixed_payload(self):
        data = struct.pack('>4I', 0xffffffff, 0xffffffff, 0xffffffff, 0x00000880)
        data += b'ps\0' + bytes(32)
        reader = PrefixReader(data, 0, 0, 4096)
        result = shader(reader, 0xffffffff, 'pixel_shader', 0)
        self.assertEqual(result['program_bytes'], 16)
        self.assertEqual(reader.offset, len(data))

    def test_pixel_uncompressed_payload_is_preserved(self):
        raw = bytes(range(28))
        data = struct.pack('>4I', 0xffffffff, 0xffffffff, 0, 0x00020001) + b'ps\0' + raw
        reader = PrefixReader(data, 0, 0, 4096)
        result = shader(reader, 0xffffffff, 'pixel_shader', 0)
        self.assertEqual(result['ps3_program_hex'], raw.hex())
        self.assertEqual(result['program_bytes'], 28)
        self.assertTrue(result['program_available'])
        self.assertFalse(result['metal_translation_available'])
        self.assertEqual(reader.virtual_offset, 44)
        self.assertEqual(reader.offset, len(data))

    def test_pixel_compressed_payload_size(self):
        raw = bytes(range(19))
        data = struct.pack('>4I', 0xffffffff, 0xffffffff, 0, 0x00028001) + b'ps\0' + raw
        reader = PrefixReader(data, 0, 0, 4096)
        result = shader(reader, 0xffffffff, 'pixel_shader', 0)
        self.assertEqual(result['program_bytes'], 19)
        self.assertEqual(reader.offset, len(data))

    def test_vertex_payload_word_count(self):
        raw = bytes(range(28))
        data = struct.pack('>4I', 0xffffffff, 0xffffffff, 0, 0x00030007) + b'vs\0' + raw
        reader = PrefixReader(data, 0, 0, 4096)
        result = shader(reader, 0xffffffff, 'vertex_shader', 0)
        self.assertEqual(result['ps3_program_hex'], raw.hex())
        self.assertEqual(reader.offset, len(data))

    def test_truncated_program_rejected(self):
        data = struct.pack('>4I', 0xffffffff, 0xffffffff, 0, 0x00020001) + b'ps\0' + bytes(27)
        with self.assertRaisesRegex(ValueError, 'truncated'):
            shader(PrefixReader(data, 0, 0, 4096), 0xffffffff, 'pixel_shader', 0)


if __name__ == '__main__':
    unittest.main()
