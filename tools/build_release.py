#!/usr/bin/env python3
"""Build a reproducible install ZIP, manifest.json and dist/SHA256SUMS."""
import argparse
import json
from pathlib import Path
import sys

from release_common import ROOT, collect_files, file_entries, has_license, release_date, sha256, write_archive, write_json


def build_release(root, output, date, allow_unlicensed=False):
    files = collect_files(root)
    if not has_license(files) and not allow_unlicensed:
        raise ValueError('No adopted LICENSE found; confirm licensing before release. '
                         '--allow-unlicensed is only for local integrity checks.')
    date = release_date(date)
    output = Path(output).resolve()
    dist = output / 'dist'
    dist.mkdir(parents=True, exist_ok=True)
    archive = dist / ('knowledge-to-plan-' + date + '.zip')
    write_archive(archive, files)
    digest = sha256(archive.read_bytes())
    manifest = {'release_date': date, 'archive': archive.relative_to(output).as_posix(),
                'archive_sha256': digest, 'files': file_entries(files)}
    write_json(output / 'manifest.json', manifest)
    (dist / 'SHA256SUMS').write_bytes((digest + '  ' + archive.name + '\n').encode('utf-8'))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT, help='Source repository')
    parser.add_argument('--output', type=Path, help='Artifact directory; defaults to --root')
    parser.add_argument('--release-date', help='YYYY-MM-DD; defaults to the existing manifest date')
    parser.add_argument('--allow-unlicensed', action='store_true', help='Local integrity checks only; the result is not release-ready')
    args = parser.parse_args()
    try:
        date = args.release_date
        if date is None:
            date = json.loads((args.root / 'manifest.json').read_text(encoding='utf-8'))['release_date']
        manifest = build_release(args.root, args.output or args.root, date, args.allow_unlicensed)
    except (OSError, ValueError, KeyError) as error:
        print('Release build failed: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps({'built': True, 'files': len(manifest['files']),
                      'archive': manifest['archive'], 'sha256': manifest['archive_sha256'],
                      'release_ready': has_license(collect_files(args.root))}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
