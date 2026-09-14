import struct
import unittest

from Tools.t6_metadata_prefix import PrefixReader
from Tools.t6_models import read_model_reference


class ModelReferenceTests(unittest.TestCase):
    def test_reference_retains_dependency_without_geometry_claim(self):
        data = struct.pack('>I', 0xffffffff) + bytes(240) + b',test_model\0'
        reader = PrefixReader(data, 0, 3, 4096)
        result = read_model_reference(reader)
        self.assertEqual(result['dependency_name'], 'test_model')
        self.assertFalse(result['geometry_available'])
        self.assertEqual(reader.offset, len(data))
        self.assertEqual(reader.virtual_offset, 15)

    def test_populated_model_rejected(self):
        data = struct.pack('>I', 0xffffffff) + b'\1' + bytes(239) + b'model\0'
        with self.assertRaisesRegex(ValueError, 'populated model'):
            read_model_reference(PrefixReader(data, 0, 0, 4096))

    def test_ordinary_name_not_assumed_reference(self):
        data = struct.pack('>I', 0xffffffff) + bytes(240) + b'model\0'
        with self.assertRaisesRegex(ValueError, 'dependency name'):
            read_model_reference(PrefixReader(data, 0, 0, 4096))

    def test_truncated_header(self):
        with self.assertRaisesRegex(ValueError, 'truncated'):
            read_model_reference(PrefixReader(bytes(243), 0, 0, 4096))
