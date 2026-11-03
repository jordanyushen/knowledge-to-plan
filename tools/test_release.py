"""Release regression tests: determinism, newly added inputs and tampering."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from build_release import build_release
from release_common import collect_files, sha256, write_json
from verify_release import verify_release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ktp-release-test-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'source'
        skill = self.root / 'knowledge-to-plan'
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('test skill\n', encoding='utf-8')
        (skill / 'requirements.txt').write_text('tzdata==2025.2\n', encoding='utf-8')
        (self.root / 'LICENSE').write_text('Test license\n', encoding='utf-8')
        self.output = self.base / 'output'

    def build(self):
        return build_release(self.root, self.output, '2026-11-04')

    def test_reproducible_bytes_and_dynamic_inputs(self):
        first = self.build()
        archive = self.output / first['archive']
        original = archive.read_bytes()
        # Neither source file timestamps nor modes influence the archive.
        source = self.root / 'knowledge-to-plan' / 'SKILL.md'
        source.touch()
        source.chmod(0o600)
        self.assertEqual(self.build(), first)
        self.assertEqual(archive.read_bytes(), original)
        self.assertEqual(len(first['files']), 3)
        self.assertTrue(verify_release(self.root, self.output)['verified'])
        (self.root / 'knowledge-to-plan' / 'new-policy.json').write_text('{}\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            verify_release(self.root, self.output)
        self.assertEqual(len(self.build()['files']), 4)

    def test_changed_source_and_archive_are_rejected(self):
        manifest = self.build()
        (self.root / 'LICENSE').write_text('changed\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'hashes'):
            verify_release(self.root, self.output)
        manifest = self.build()
        archive = self.output / manifest['archive']
        archive.write_bytes(archive.read_bytes() + b'tampered')
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            verify_release(self.root, self.output)

    def test_duplicate_or_extra_archive_entry_is_rejected(self):
        manifest = self.build()
        archive = self.output / manifest['archive']
        with zipfile.ZipFile(archive, 'a') as bundle:
            bundle.writestr('unexpected.txt', b'extra')
        # Even if someone updates outer hashes, the source/ZIP inventory must match.
        manifest['archive_sha256'] = sha256(archive.read_bytes())
        write_json(self.output / 'manifest.json', manifest)
        (self.output / 'dist' / 'SHA256SUMS').write_text(
            manifest['archive_sha256'] + '  ' + archive.name + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'ZIP entries'):
            verify_release(self.root, self.output)

    def test_checksum_file_and_unsafe_archive_paths_are_rejected(self):
        self.build()
        (self.output / 'dist' / 'SHA256SUMS').write_text('wrong\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'SHA256SUMS'):
            verify_release(self.root, self.output)
        manifest = self.build()
        manifest['archive'] = '../outside.zip'
        write_json(self.output / 'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            verify_release(self.root, self.output)

    def test_caches_are_excluded_and_symbolic_links_rejected(self):
        cache = self.root / 'knowledge-to-plan' / '__pycache__'
        cache.mkdir()
        (cache / 'cache.pyc').write_bytes(b'cache')
        self.assertEqual(len(collect_files(self.root)), 3)
        link = self.root / 'knowledge-to-plan' / 'outside.txt'
        try:
            link.symlink_to(self.root / 'LICENSE')
        except OSError:
            self.skipTest('Creating symbolic links is unavailable for this account')
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            collect_files(self.root)

    def test_license_is_a_release_gate_with_explicit_local_override(self):
        (self.root / 'LICENSE').unlink()
        drafts = self.root / 'docs'
        drafts.mkdir()
        (drafts / 'LICENSE-MIT.proposed.txt').write_text('unadopted draft', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'No adopted LICENSE'):
            self.build()
        build_release(self.root, self.output, '2026-11-04', allow_unlicensed=True)
        with self.assertRaisesRegex(ValueError, 'No adopted LICENSE'):
            verify_release(self.root, self.output)
        self.assertFalse(verify_release(self.root, self.output, allow_unlicensed=True)['release_ready'])


if __name__ == '__main__':
    unittest.main()
