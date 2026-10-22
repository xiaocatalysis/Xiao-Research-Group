#!/usr/bin/env python3
"""
RECSL static-site builder for GitHub Pages.

Renders every top-level *.php page with the PHP CLI into a SEPARATE output
directory (default: ./build), so source fragments are never overwritten.
Then, in the rendered output only, rewrites internal links:

  * href/src/action values ending in ".php" that correspond to a rendered page
    -> the ".html" page (query string and #anchor preserved)
  * the old university homepage (http(s)://www2.latech.edu/~yxiao/)
    -> index.html

Nothing else in the markup is touched (attribute-level substitution; the
document is not re-serialised). External links, mailto:, tel:, #anchors,
javascript:, PDFs and images are left exactly as they are.

Assets are copied from the source tree while preserving relative paths.

Usage:
  python3 tools/build.py --dry-run          # report only, writes nothing
  python3 tools/build.py                    # build into ./build
  python3 tools/build.py --out /tmp/site    # build somewhere else

Source files are NEVER modified by this script.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

# ---------------------------------------------------------------- configuration
# Directories / files copied verbatim into the output (if they exist).
ASSET_DIRS = ["assets", "PDF", "lib"]
EXTRA_FILES = [
    "favicon.ico",
    ".nojekyll",
    "CNAME",
    "googleff32f4c808c91e16.html",  # Google Search Console verification
    "VisitorCounter.html",          # loaded by Footer.html in an iframe
    "VisitorGlobe.html",            # loaded by Footer.html in an iframe
    "404.html",
]
# PHP files that are NOT pages (endpoints, counters) -> never rendered.
PHP_EXCLUDE = {"Count_Visitor/Count_Visitor.php"}
# Old homepage URLs that should point at the new homepage.
OLD_HOME = {
    "http://www2.latech.edu/~yxiao/", "https://www2.latech.edu/~yxiao/",
    "http://www2.latech.edu/~yxiao", "https://www2.latech.edu/~yxiao",
    "http://www2.latech.edu/~yxiao/index.php",
    "https://www2.latech.edu/~yxiao/index.php",
}
ATTR_RE = re.compile(r"""(?P<attr>\b(?:href|src|action)\s*=\s*)(?P<q>["'])(?P<val>[^"']*)(?P=q)""", re.I)
# ------------------------------------------------------------------------------


def log(msg=""):
    print(msg, flush=True)


def find_php_pages(src: Path):
    pages = []
    for p in sorted(src.glob("*.php")):
        rel = p.relative_to(src).as_posix()
        if rel in PHP_EXCLUDE:
            continue
        pages.append(p)
    return pages


def render(php_bin, src: Path, page: Path):
    """Render page with cwd = src so relative includes resolve. Returns (html, stderr)."""
    proc = subprocess.run(
        [php_bin, "-n", "-d", "display_errors=stderr", "-d", "error_reporting=E_ALL", page.name],
        cwd=str(src), capture_output=True, text=True, errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"php exited {proc.returncode} for {page.name}: {proc.stderr.strip()[:500]}")
    return proc.stdout, proc.stderr


def rewrite_links(html: str, page_names: set, report: dict, page_label: str):
    """Rewrite attribute values only. Collect what was changed / what is unresolved."""

    def repl(m):
        val = m.group("val")
        new = val
        stripped = val.strip()

        if stripped in OLD_HOME:
            new = "index.html"
        else:
            parsed = urllib.parse.urlsplit(stripped)
            if parsed.scheme or stripped.startswith("//") or stripped.startswith("#") or not stripped:
                return m.group(0)  # external, anchor, protocol-relative, empty
            path = parsed.path
            if path.lower().endswith(".php"):
                base = path[:-4]
                target = base + ".html"
                # only rewrite links to pages that this build actually produces
                if os.path.basename(target) in page_names and "/" not in base.strip("./"):
                    new = urllib.parse.urlunsplit(("", "", target, parsed.query, parsed.fragment))
                else:
                    report["unresolved_php_links"].setdefault(stripped, []).append(page_label)
                    return m.group(0)
        if new != val:
            report["rewrites"].setdefault(f"{val} -> {new}", []).append(page_label)
            return f"{m.group('attr')}{m.group('q')}{new}{m.group('q')}"
        return m.group(0)

    return ATTR_RE.sub(repl, html)


def copy_tree(src: Path, dst: Path, dry: bool, report: dict):
    count = 0
    for root, _dirs, files in os.walk(src):
        for f in files:
            s = Path(root) / f
            rel = s.relative_to(src.parent)
            d = dst / rel
            count += 1
            if not dry:
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, d)
    report["assets_copied"][src.name] = count


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=".", help="source directory (the Git checkout)")
    ap.add_argument("--out", default="build", help="output directory (must not be the source dir)")
    ap.add_argument("--php", default=os.environ.get("PHP_BIN", "php"), help="php binary")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    ap.add_argument("--report", default=None, help="write JSON report to this path (default: <out>/build-report.json, or stdout in dry-run)")
    args = ap.parse_args()

    src = Path(args.src).resolve()
    out = Path(args.out).resolve()
    dry = args.dry_run

    if out == src or src in out.parents and out.name in ("", "."):
        sys.exit("ERROR: output directory must be different from the source directory")
    if src in out.parents:
        log(f"NOTE: output {out} is inside the source tree; make sure it is in .gitignore")

    if shutil.which(args.php) is None and not Path(args.php).exists():
        sys.exit(f"ERROR: php binary not found: {args.php}  (install php-cli or set --php)")

    pages = find_php_pages(src)
    page_names = {p.stem + ".html" for p in pages}
    report = {
        "mode": "dry-run" if dry else "build",
        "source": str(src), "output": str(out),
        "pages_rendered": [], "pages_failed": {}, "php_warnings": {},
        "rewrites": {}, "unresolved_php_links": {}, "assets_copied": {}, "extra_files": [],
        "source_html_fragments_overwritten": [],
    }

    # Safety: a rendered page must never overwrite a same-named source fragment.
    for p in pages:
        frag = src / (p.stem + ".html")
        if frag.exists() and (out / (p.stem + ".html")).resolve() == frag.resolve():
            report["source_html_fragments_overwritten"].append(frag.name)
    if report["source_html_fragments_overwritten"]:
        sys.exit("ERROR: output would overwrite source fragments: " + ", ".join(report["source_html_fragments_overwritten"]))

    if not dry:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)

    log(f"{'DRY RUN: ' if dry else ''}rendering {len(pages)} PHP pages from {src}")
    for p in pages:
        label = p.stem + ".html"
        try:
            html, err = render(args.php, src, p)
        except Exception as e:  # noqa: BLE001
            report["pages_failed"][label] = str(e)
            log(f"  FAIL  {p.name}: {e}")
            continue
        if err.strip():
            report["php_warnings"][label] = err.strip()[:1000]
        size_before = len(html)
        html2 = rewrite_links(html, page_names, report, label)
        report["pages_rendered"].append({"page": label, "bytes": size_before, "bytes_after": len(html2)})
        log(f"  ok    {p.name:32s} -> {label:32s} {size_before:7d} bytes" + ("  (php warnings)" if err.strip() else ""))
        if not dry:
            (out / label).write_text(html2, encoding="utf-8")

    for d in ASSET_DIRS:
        sd = src / d
        if sd.is_dir():
            copy_tree(sd, out, dry, report)
    for f in EXTRA_FILES:
        sf = src / f
        if sf.is_file():
            report["extra_files"].append(f)
            if not dry:
                shutil.copy2(sf, out / f)
    if not dry and not (out / ".nojekyll").exists():
        (out / ".nojekyll").write_text("")

    # ---- summary
    log()
    log("Summary")
    log(f"  pages rendered : {len(report['pages_rendered'])}")
    log(f"  pages failed   : {len(report['pages_failed'])}")
    log(f"  php warnings   : {len(report['php_warnings'])}")
    log(f"  link rewrites  : {sum(len(v) for v in report['rewrites'].values())} occurrences, {len(report['rewrites'])} distinct")
    log(f"  unresolved .php: {len(report['unresolved_php_links'])} distinct")
    log(f"  assets copied  : {report['assets_copied']}")
    log(f"  extra files    : {report['extra_files']}")
    if report["unresolved_php_links"]:
        log("\nUNRESOLVED .php links (left unchanged, need a decision):")
        for k, v in report["unresolved_php_links"].items():
            log(f"  {k}   in {sorted(set(v))[:5]}{' ...' if len(set(v)) > 5 else ''}")
    if report["php_warnings"]:
        log("\nPHP warnings/notices (check these pages):")
        for k, v in report["php_warnings"].items():
            log(f"  {k}: {v.splitlines()[0][:160]}")
    if report["pages_failed"]:
        log("\nFAILED pages:")
        for k, v in report["pages_failed"].items():
            log(f"  {k}: {v}")

    rp = args.report or (None if dry else str(out / "build-report.json"))
    if rp:
        Path(rp).write_text(json.dumps(report, indent=2))
        log(f"\nreport written to {rp}")
    elif dry:
        log("\n(dry run: nothing written; pass --report FILE to save this report)")

    return 1 if report["pages_failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
