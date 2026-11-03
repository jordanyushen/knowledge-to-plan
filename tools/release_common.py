"""Shared, dependency-free release inventory and deterministic archive helpers."""
import datetime as dt
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRS = {'__pycache__', '.git', '.venv', 'node_modules'}
IGNORED_FILES = {'.DS_Store'}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or '\\' in value or path.as_posix() != value:
        raise ValueError('Unsafe release path: ' + str(value))
    return path


def collect_files(root):
    """Package the installable skill, plus root licensing/runtime prerequisites."""
    root = Path(root).resolve()
    skill = root / 'knowledge-to-plan'
    if not (skill / 'SKILL.md').is_file():
        raise ValueError('Missing knowledge-to-plan/SKILL.md')
    paths = []
    for path in skill.rglob('*'):
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative.parts) or path.name in IGNORED_FILES or path.suffix in {'.pyc', '.pyo'}:
            continue
        if path.is_symlink():
            raise ValueError('Release inputs must not be symbolic links: ' + relative.as_posix())
        if path.is_file():
            paths.append(path)
    for pattern in ('LICENSE*', 'NOTICE*', 'COPYING*', 'requirements*.txt', 'VERSION'):
        for path in root.glob(pattern):
            if path.is_symlink():
                raise ValueError('Release inputs must not be symbolic links: ' + path.name)
            if path.is_file():
                paths.append(path)
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(set(paths), key=lambda path: path.relative_to(root).as_posix())}


def file_entries(files):
    return [{'path': path, 'bytes': len(content), 'sha256': sha256(content)}
            for path, content in files.items()]


def has_license(files):
    return any(path in files for path in ('LICENSE', 'LICENSE.md', 'LICENSE.txt',
                                         'knowledge-to-plan/LICENSE',
                                         'knowledge-to-plan/LICENSE.md',
                                         'knowledge-to-plan/LICENSE.txt'))


def write_archive(path, files):
    """ZIP_STORED also avoids differences between platform zlib versions."""
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, content)


def release_date(value):
    try:
        if dt.date.fromisoformat(value).isoformat() == value:
            return value
    except (TypeError, ValueError):
        pass
    raise ValueError('release_date must be YYYY-MM-DD')


def write_json(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
