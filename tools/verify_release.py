#!/usr/bin/env python3
"""Verify complete source inventory, manifest hashes, ZIP bytes and SHA256SUMS."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

from release_common import ROOT, collect_files, file_entries, has_license, release_date, safe_path, sha256


def verify_release(root, release_root, allow_unlicensed=False):
    release_root = Path(release_root).resolve()
    manifest = json.loads((release_root / 'manifest.json').read_text(encoding='utf-8'))
    release_date(manifest['release_date'])
    files = collect_files(root)
    licensed = has_license(files)
    if not licensed and not allow_unlicensed:
        raise ValueError('No adopted LICENSE found; --allow-unlicensed is only for local integrity checks')
    expected = file_entries(files)
    if manifest.get('files') != expected:
        raise ValueError('Manifest file inventory, sizes or hashes differ from source; rebuild the release')
    relative_archive = safe_path(manifest['archive'])
    if relative_archive.parts[0] != 'dist' or relative_archive.suffix != '.zip':
        raise ValueError('Archive must be a ZIP in dist/')
    archive_path = release_root.joinpath(*relative_archive.parts)
    digest = sha256(archive_path.read_bytes())
    if digest != manifest.get('archive_sha256'):
        raise ValueError('Archive SHA256 does not match manifest')
    sums = (archive_path.parent / 'SHA256SUMS').read_text(encoding='utf-8')
    if sums != digest + '  ' + archive_path.name + '\n':
        raise ValueError('dist/SHA256SUMS differs from the selected release archive')
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or sorted(names) != list(files):
            raise ValueError('ZIP entries differ from source inventory, or contain duplicate names')
        for name in names:
            safe_path(name)
            if archive.read(name) != files[name]:
                raise ValueError('ZIP content differs from source: ' + name)
        bad = archive.testzip()
        if bad:
            raise ValueError('ZIP CRC failure: ' + bad)
    return {'verified': True, 'release_ready': licensed, 'files': len(files), 'archive': manifest['archive'], 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='Source repository')
    parser.add_argument('--release-root', type=Path, help='Manifest/dist directory; defaults to --root')
    parser.add_argument('--allow-unlicensed', action='store_true', help='Verify local integrity only; do not assert release readiness')
    args = parser.parse_args()
    try:
        result = verify_release(args.root, args.release_root or args.root, args.allow_unlicensed)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print('Release verification failed: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
