# RECSL website → GitHub Pages: recovery + build toolkit

This is **not** a repaired copy of your HTML files. It cannot be: 22 of the
pages you sent me contain no content (see `ANALYSIS.md`), and the content
only exists in your Git history, in your backup, or on the live PHP site.
Nothing I generate can replace it. What this toolkit does instead:

1. **recovers the original content fragments from Git** (dry‑run first),
2. **builds the static site into a separate `build/` folder** from the
   untouched PHP + HTML sources, rewriting only page links,
3. **validates the result over HTTP** before anything is deployed,
4. **deploys only the validated output** with GitHub Actions.

Every script prints what it would do before it does anything, never edits
a source file, and never runs `reset --hard`, `clean`, or `push --force`.
The pipeline was tested end‑to‑end on a replica of your repository (the
replica reproduced your damaged 21 772‑byte files byte‑for‑byte, which is
how the cause was confirmed).

```
tools/recover_fragments.sh   restore destroyed fragments from commit df8402c (dry‑run by default)
tools/build.py               PHP sources -> build/  (dry‑run available, writes a JSON report)
tools/check_site.py          crawls build/ over HTTP, fails on broken links/.php links/shell pages
build.sh                     build + check in one command
.github/workflows/pages.yml  CI build + deploy (Pages source must be "GitHub Actions")
.gitignore.additions         lines to append to your .gitignore
ANALYSIS.md                  what I found in the 96 HTML files you sent
```

## Step 0 — install into the repo (copies only, nothing else changes)

```bash
cd ~/Documents/Xiao-Research-Group
unzip -o ~/Downloads/recsl-migration-toolkit.zip -d /tmp/toolkit
cp -r /tmp/toolkit/tools /tmp/toolkit/build.sh .
cat /tmp/toolkit/.gitignore.additions >> .gitignore
mv fix_recsl_links.py ~/Documents/fix_recsl_links.py.retired 2>/dev/null || true
git status -sb
```

If `git status` shows modified files from the earlier incident, park them
first so nothing is lost: `git stash push -m "pre-recovery working tree"`.

## Step 1 — confirm the originals are in Git (read‑only)

```bash
bash tools/recover_fragments.sh
```

Read the `WOULD RESTORE` table. Healthy originals have **different, realistic
sizes** (a few KB to tens of KB). If the “original” column is also 21 772 /
21 817 bytes, or files are missing from `df8402c`, stop and use the fallback
at the end of this file. Send me the output if anything looks odd.

## Step 2 — recover, on a new branch

```bash
bash tools/recover_fragments.sh --apply       # creates branch recovery/restore-fragments
git diff --cached --stat
git commit -m "Restore original HTML fragments from df8402c; retire generated pages"
```

`_retired_generated/` holds the pages the old conversion produced
(`index.html`, etc.). They are not needed any more and can be deleted in a
later commit once the build is proven.

## Step 3 — build and test locally (needs `php-cli`: `sudo apt install php-cli`)

```bash
python3 tools/build.py --dry-run             # what would be rendered / rewritten / unresolved
./build.sh                                   # build into ./build and check it
python3 -m http.server -d build 8000         # open http://localhost:8000/ and click through
```

`build/build-report.json` lists every link rewrite and every link that was
left alone. The checker must end with `RESULT: OK`. Expected notes:

* `Count_Visitor/Count_Visitor.php` is never rendered (it is an endpoint,
  not a page). `Footer.html` already uses third‑party JavaScript counters,
  so the site loses nothing. If the checker reports a link to it, tell me
  and we decide what that link should do.
* Theme demo pages (`features-*`, `pages-*`, `portfolio-*`, `blog-*`) and
  drafts (`*2.html`, `*3.html`, `Biography (copy).html`, …) are not
  published because no `.php` page includes them. They stay in the repo.

Optional but strongly recommended golden comparison against the live site:

```bash
mkdir -p ~/Documents/live-mirror && cd ~/Documents/live-mirror
wget --mirror --no-parent --adjust-extension --page-requisites --convert-links \
     --wait=1 https://www.xiaocatalysis.com/
cd ~/Documents/Xiao-Research-Group
python3 tools/check_site.py build --golden ~/Documents/live-mirror/www.xiaocatalysis.com
```

`0 differ in visible text` proves the migrated pages show the same content
as the live PHP site.

## Step 4 — deploy (after you are happy with the local preview)

1. Copy the workflow: `mkdir -p .github/workflows && cp /tmp/toolkit/.github/workflows/pages.yml .github/workflows/`
2. On GitHub: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
   (Deploying from the root of `main` cannot work with this site: a rendered
   `Biography.html` would overwrite the `Biography.html` content fragment,
   which is exactly what destroyed the pages the first time.)
3. `git add .github tools build.sh .gitignore && git commit -m "Add static-site build and Pages workflow"`
4. Merge/push: `git switch main && git merge recovery/restore-fragments && git push`
5. Watch **Actions → Build and deploy site**. The deploy step only runs if
   `check_site.py` passes. Then test https://xiaocatalysis.github.io/Xiao-Research-Group/.

Rollback at any time: `git revert <commit> && git push` (the workflow
redeploys the previous state).

## Future updates

Edit the fragment (e.g. `News_recent.html`, `Journal_Articles.html`),
run `./build.sh`, preview, commit, push. Nothing else.

## Custom domain (Step 5, only after the Pages site is validated)

Add a `CNAME` file containing `www.xiaocatalysis.com` to the repo root (the
build copies it), set the custom domain in Settings → Pages, then update
Name.com DNS. I will walk you through the DNS records at that stage after we
look at your current records together.

## Fallback if `df8402c` does not contain the fragments

The live site still serves every page. The mirror from Step 3 contains fully
rendered pages; the content fragments can be cut out of them between the
`<!-- === END HEADER === -->` and `<!-- === BEGIN FOOTER === -->` markers.
Send me the mirror (or the `wget` output) and I will prepare that extraction
as a reviewable, dry‑run script — it is mechanical, but I want to see the
real files before writing it.
