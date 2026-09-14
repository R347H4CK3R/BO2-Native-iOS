import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from Tools.dump_inventory import inventory, write_report


class DumpInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'PS3_GAME'
        self.usr = self.root / 'USRDIR'
        self.usr.mkdir(parents=True)

    def test_inventory_preserves_source_and_does_not_claim_conversion(self):
        payload = b'TAff0100' + bytes(24)
        source = self.usr / 'zm_test.ff'
        source.write_bytes(payload)
        result = inventory(self.root)
        self.assertEqual(source.read_bytes(), payload)
        self.assertEqual(result['file_count'], 1)
        record = result['files'][0]
        self.assertEqual(record['path'], 'USRDIR/zm_test.ff')
        self.assertEqual(record['sha256'], hashlib.sha256(payload).hexdigest())
        self.assertEqual(record['native_conversion'], 'not_implemented')
        self.assertFalse(result['ready_for_packaging'])
        self.assertEqual(result['native_assets_converted'], 0)

    def test_requires_game_root_and_content(self):
        with self.assertRaisesRegex(ValueError, 'USRDIR'):
            inventory(self.base)
        with self.assertRaisesRegex(ValueError, 'empty'):
            inventory(self.root)

    def test_report_cannot_overwrite_source_or_live_in_repo(self):
        source = self.usr / 'test.ff'
        source.write_bytes(b'original')
        result = inventory(self.root)
        with self.assertRaisesRegex(ValueError, 'source'):
            write_report(result, source, self.root)
        repo = Path(__file__).resolve().parents[2]
        with self.assertRaisesRegex(ValueError, 'repository'):
            write_report(result, repo / 'forbidden-report.json', self.root)
        self.assertEqual(source.read_bytes(), b'original')

    def test_existing_report_is_not_replaced(self):
        (self.usr / 'test.ff').write_bytes(b'original')
        result = inventory(self.root)
        target = self.base / 'report.json'
        write_report(result, target, self.root)
        self.assertEqual(json.loads(target.read_text())['file_count'], 1)
        with self.assertRaises(FileExistsError):
            write_report(result, target, self.root)

    def test_unknown_extension_stays_unconverted(self):
        (self.usr / 'mystery.xyz').write_bytes(b'unknown')
        result = inventory(self.root)
        self.assertEqual(result['files'][0]['native_conversion'], 'not_implemented')
        self.assertEqual(result['extension_counts'], {'.xyz': 1})

    def test_rejects_link_outside_source(self):
        outside = self.base / 'outside.bin'
        outside.write_bytes(b'outside')
        try:
            (self.usr / 'linked.ff').symlink_to(outside)
        except OSError:
            self.skipTest('symlink creation unavailable on this host')
        with self.assertRaisesRegex(ValueError, 'link'):
            inventory(self.root)


if __name__ == '__main__':
    unittest.main()
