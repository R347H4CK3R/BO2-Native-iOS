import importlib.util
import struct
import unittest
from pathlib import Path


class AssetIndexTests(unittest.TestCase):
    def test_declared_table_after_script_strings(self):
        # 40-byte XFile, 24-byte list, three string slots (including null),
        # two strings, alignment, two asset records. No searching is needed.
        module_path = Path(__file__).parents[1] / 't6_asset_index.py'
        self.assertTrue(module_path.exists(), 'deterministic asset index is missing')
        spec = importlib.util.spec_from_file_location('t6_asset_index', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        body = struct.pack('>6I', 3, 0xffffffff, 0, 0, 2, 0xffffffff)
        body += struct.pack('>3I', 0, 0xffffffff, 0xffffffff)
        body += b'alpha\0beta\0' + b'\0'
        body += struct.pack('>4I', 17, 0xffffffff, 6, 0xa0000001)
        payload = struct.pack('>10I', len(body), 0, *([0]*8)) + body
        result = module.inspect(payload)
        self.assertEqual(result['table_offset'], 88)
        self.assertEqual(result['asset_data_offset'], 104)
        self.assertEqual(result['type_counts'], {'6': 1, '17': 1})
        self.assertEqual(result['inline_asset_count'], 1)
        self.assertEqual(result['referenced_asset_count'], 1)

    def load_inspector(self):
        path = Path(__file__).parents[1] / 't6_asset_index.py'
        self.assertTrue(path.exists(), 'deterministic asset index is missing')
        spec = importlib.util.spec_from_file_location('t6_asset_index', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.inspect

    def fixture(self, body):
        return struct.pack('>10I', len(body), 0, *([0]*8)) + body

    def test_rejects_short_declared_table(self):
        inspect = self.load_inspector()
        data = self.fixture(struct.pack('>6I', 0, 0, 0, 0, 2, 0xffffffff) + struct.pack('>2I', 17, 0xffffffff))
        with self.assertRaisesRegex(ValueError, 'truncated asset table'):
            inspect(data)

    def test_does_not_search_past_invalid_table(self):
        inspect = self.load_inspector()
        data = self.fixture(struct.pack('>6I', 0, 0, 0, 0, 1, 0xffffffff) + struct.pack('>4I', 999, 0xffffffff, 17, 0xffffffff))
        with self.assertRaisesRegex(ValueError, 'asset type'):
            inspect(data)

    def test_rejects_unresolved_string_reference(self):
        inspect = self.load_inspector()
        data = self.fixture(struct.pack('>6I', 1, 0xffffffff, 0, 0, 0, 0) + struct.pack('>I', 0xa0000001))
        with self.assertRaisesRegex(ValueError, 'unresolved string'):
            inspect(data)

    def test_rejects_xfile_size_mismatch(self):
        inspect = self.load_inspector()
        with self.assertRaisesRegex(ValueError, 'XFile size'):
            inspect(bytes(64))


if __name__ == '__main__':
    unittest.main()
