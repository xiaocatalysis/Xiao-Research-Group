#!/usr/bin/env python3
"""
Validate a built static site before deploying it.

Starts a local HTTP server on the build directory, starts at index.html, and
follows every internal link / asset reference (href, src, action, iframe src,
CSS url(...)) reachable from the navigation, checking each with a real HTTP
request. Reports:

  * broken internal links and missing assets (HTTP != 200)
  * any remaining internal link to a .php file
  * any remaining link to the old university homepage
  * pages whose body text is suspiciously identical to another page
    (the "header+header+footer" shell symptom)
  * (optional) --golden DIR : compare the visible text of each page with a
    reference copy, e.g. a `wget --mirror` of the live PHP site, to prove
    content was not changed by the migration

Usage:
  python3 tools/check_site.py build
  python3 tools/check_site.py build --golden /path/to/mirror/www.xiaocatalysis.com
Exit code 0 = no problems found.
"""
import argparse
import hashlib
import html as htmlmod
import http.server
import os
import re
import socketserver
import sys
import threading
import urllib.parse
import urllib.request
from pathlib import Path

ATTR_RE = re.compile(r"""\b(?:href|src|action)\s*=\s*["']([^"']*)["']""", re.I)
CSS_URL_RE = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", re.I)
TEXT_SKIP_RE = re.compile(r"<(script|style)\b.*?</\1>|<!--.*?-->", re.S | re.I)


def visible_text(doc: str) -> str:
    t = TEXT_SKIP_RE.sub("", doc)
    t = re.sub(r"<head\b.*?</head>", "", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", htmlmod.unescape(t)).strip()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass


def serve(directory: str):
    handler = lambda *a, **k: QuietHandler(*a, directory=directory, **k)  # noqa: E731
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    srv.daemon_threads = True
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, srv.server_address[1]


def classify(ref: str):
    s = ref.strip()
    if not s or s.startswith("#"):
        return "anchor"
    p = urllib.parse.urlsplit(s)
    if p.scheme in ("mailto", "tel", "javascript", "data"):
        return "special"
    if p.scheme or s.startswith("//"):
        return "external"
    return "internal"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("build_dir")
    ap.add_argument("--start", default="index.html")
    ap.add_argument("--golden", default=None, help="directory holding reference copies of the pages (same file names)")
    ap.add_argument("--max", type=int, default=5000)
    args = ap.parse_args()

    bdir = str(Path(args.build_dir).resolve())
    srv, port = serve(bdir)
    base = f"http://127.0.0.1:{port}/"

    problems = []
    seen = {}
    queue = [args.start]
    pages_text = {}
    php_links, old_home = {}, {}
    external = set()

    def fetch(url):
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                ctype = r.headers.get("Content-Type", "")
                body = r.read() if ("text/html" in ctype or "text/css" in ctype) else b""
                return r.status, ctype, body
        except urllib.error.HTTPError as e:
            return e.code, "", b""
        except Exception as e:  # noqa: BLE001
            return 0, str(e), b""

    while queue and len(seen) < args.max:
        rel = queue.pop(0)
        rel = rel.split("#", 1)[0]
        if not rel or rel in seen:
            continue
        status, ctype, body = fetch(urllib.parse.urljoin(base, urllib.parse.quote(rel, safe="/:?=&%+")))
        seen[rel] = status
        if status != 200:
            continue
        if "text/html" in ctype:
            doc = body.decode("utf-8", "replace")
            pages_text[rel] = visible_text(doc)
            refs = ATTR_RE.findall(doc)
        elif "text/css" in ctype:
            refs = CSS_URL_RE.findall(body.decode("utf-8", "replace"))
        else:
            continue
        for ref in refs:
            kind = classify(ref)
            if kind == "external":
                external.add(ref)
                if "www2.latech.edu/~yxiao" in ref:
                    old_home.setdefault(ref, set()).add(rel)
                continue
            if kind != "internal":
                continue
            path = urllib.parse.urlsplit(ref.strip()).path
            target = urllib.parse.urljoin(rel, path)
            if target.lower().endswith(".php"):
                php_links.setdefault(target, set()).add(rel)
            if target not in seen:
                queue.append(target)
            seen.setdefault("__from__" + target, rel)

    srv.shutdown()

    # ---- report
    missing = {k: v for k, v in seen.items() if not k.startswith("__from__") and v != 200}
    print(f"Checked {len([k for k in seen if not k.startswith('__from__')])} internal URLs from {args.start}")
    print(f"  HTML pages      : {len(pages_text)}")
    print(f"  external links  : {len(external)} (not fetched)")

    if missing:
        problems.append(f"{len(missing)} broken internal references")
        print(f"\nBROKEN internal references ({len(missing)}):")
        for k, v in sorted(missing.items()):
            print(f"  [{v:>3}] {k}    (first linked from {seen.get('__from__' + k, '?')})")
    if php_links:
        problems.append(f"{len(php_links)} links still point to .php")
        print(f"\nLinks still pointing to .php ({len(php_links)}):")
        for k, v in sorted(php_links.items()):
            print(f"  {k}   from {sorted(v)[:4]}")
    if old_home:
        problems.append("old university homepage still linked")
        print("\nOld homepage links remaining:")
        for k, v in old_home.items():
            print(f"  {k}   from {sorted(v)[:4]}")

    # identical-body detection (shell pages)
    by_hash = {}
    for k, t in pages_text.items():
        if len(t) < 200:  # widget/iframe documents have no visible text
            continue
        by_hash.setdefault(hashlib.md5(t.encode()).hexdigest(), []).append(k)
    dups = [v for v in by_hash.values() if len(v) > 1]
    if dups:
        problems.append("pages with identical visible text (empty shells?)")
        print("\nPages with IDENTICAL visible text (probably missing content):")
        for grp in dups:
            print("  " + ", ".join(sorted(grp)))

    if args.golden:
        g = Path(args.golden)
        diffs, compared = [], 0
        for k, t in pages_text.items():
            cand = [g / k, g / (k[:-5] + ".php") if k.endswith(".html") else None]
            cand = [c for c in cand if c and c.is_file()]
            if not cand:
                continue
            compared += 1
            gt = visible_text(cand[0].read_text(encoding="utf-8", errors="replace"))
            if gt != t:
                diffs.append(k)
        print(f"\nGolden comparison: {compared} pages compared, {len(diffs)} differ in visible text")
        for d in diffs:
            print(f"  DIFFERS: {d}")
        if diffs:
            problems.append(f"{len(diffs)} pages differ from golden copy")

    print()
    if problems:
        print("RESULT: PROBLEMS FOUND -> " + "; ".join(problems))
        return 1
    print("RESULT: OK - no broken links, no .php links, no old homepage links, no duplicate pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
