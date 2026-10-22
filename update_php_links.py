#!/usr/bin/env python3
"""Rewrite local .php URLs to .html in generated HTML files.

Run from the website repository root. Original PHP files are not changed.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
# Match .php only at the end of a URL path, before query/fragment or a quote.
PATTERN = re.compile(r'\.php(?=($|[?#\s"\'<>]))', re.IGNORECASE)


def main():
    total = 0
    for path in sorted(ROOT.rglob('*.html')):
        if '.git' in path.parts:
            continue
        original = path.read_text(encoding='utf-8')
        updated, count = PATTERN.subn('.html', original)
        if count:
            path.write_text(updated, encoding='utf-8')
            print(f'{path.relative_to(ROOT)}: updated {count} reference(s)')
            total += count
    print(f'Done. Updated {total} reference(s). Original PHP files were not modified.')


if __name__ == '__main__':
    main()
