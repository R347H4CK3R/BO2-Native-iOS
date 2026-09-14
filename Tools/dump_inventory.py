"""Read-only source inventory. Does not convert assets or establish dump completeness."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path


def _inside(path, root):
    return path == root or root in path.parents


def _link(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def inventory(root: Path, progress=None) -> dict:
    root = Path(root)
    if _link(root):
        raise ValueError('source root is a link')
    root = root.resolve(strict=True)
    if not (root / 'USRDIR').is_dir():
        raise ValueError('source must be PS3_GAME containing USRDIR')
    records = []
    counts = Counter()
    def walk_error(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs.sort()
        for name in dirs + files:
            if _link(Path(directory) / name):
                raise ValueError(f'source contains a link: {name}')
        for name in sorted(files):
            path = Path(directory) / name
            if not _inside(path.resolve(strict=True), root):
                raise ValueError('source file escapes root')
            before = path.stat()
            digest = hashlib.sha256()
            size = 0
            with path.open('rb') as stream:
                header = stream.read(16)
                digest.update(header)
                size += len(header)
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                    size += len(chunk)
                    digest.update(chunk)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or size != before.st_size:
                raise ValueError(f'source changed during inventory: {name}')
            extension = path.suffix.lower()
            counts[extension] += 1
            records.append({
                'path': path.relative_to(root).as_posix(),
                'bytes': size,
                'sha256': digest.hexdigest(),
                'header_hex': header.hex(),
                'extension': extension,
                'native_conversion': 'not_implemented',
            })
            if progress:
                progress(len(records), size, path.relative_to(root).as_posix())
    if not records or not any(r['path'].startswith('USRDIR/') for r in records):
        raise ValueError('source USRDIR is empty')
    return {
        'schema': 1,
        'operation': 'source_inventory_only',
        'file_count': len(records),
        'total_bytes': sum(r['bytes'] for r in records),
        'extension_counts': dict(sorted(counts.items())),
        'source_completeness_verified': False,
        'native_assets_converted': 0,
        'ready_for_packaging': False,
        'limitation': 'File presence and hashes do not establish complete assets, native conversion, or gameplay.',
        'files': sorted(records, key=lambda r: r['path']),
    }


def write_report(report: dict, target: Path, source: Path):
    target = Path(target).resolve()
    source = Path(source).resolve()
    repository = Path(__file__).resolve().parents[1]
    if _inside(target, source):
        raise ValueError('report must be outside source dump')
    if _inside(target, repository):
        raise ValueError('report must be outside repository')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = inventory(args.source, lambda count, size, name: print(f'{count}: {name} ({size} bytes)', flush=True))
        write_report(result, args.report, args.source)
        print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f'Inventory failed: {error}\n')


if __name__ == '__main__':
    main()
