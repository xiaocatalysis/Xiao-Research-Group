#!/usr/bin/env bash
# Recover the HTML content fragments that were destroyed by the original
# `php X.php > X.html` conversion (commit bbd1601), using the last commit that
# still contained the originals (default: df8402c).
#
#   bash tools/recover_fragments.sh            # DRY RUN: only prints what would happen
#   bash tools/recover_fragments.sh --apply    # does it, on a NEW branch, nothing deleted
#
# What --apply does (and nothing else):
#   1. refuses to run if the working tree has uncommitted changes
#   2. creates branch  recovery/restore-fragments  from the current HEAD
#   3. for every *.html tracked in GOOD_COMMIT whose content differs now:
#        git restore --source=GOOD_COMMIT -- FILE      (brings back the original)
#   4. for every tracked *.html that did NOT exist in GOOD_COMMIT (i.e. pages the
#      conversion generated): git mv FILE _retired_generated/FILE
#      (kept in the repo, out of the way; delete later once the build is proven)
#   5. prints `git status` and a diffstat; it does NOT commit. You review, then commit.
set -euo pipefail
GOOD_COMMIT="${GOOD_COMMIT:-df8402c}"
BRANCH="recovery/restore-fragments"
APPLY=0; [[ "${1:-}" == "--apply" ]] && APPLY=1

cd "$(git rev-parse --show-toplevel)"
git cat-file -e "${GOOD_COMMIT}^{commit}" || { echo "commit $GOOD_COMMIT not found"; exit 1; }

echo "Reference commit: $(git log --oneline -n1 "$GOOD_COMMIT")"
echo "Current HEAD    : $(git log --oneline -n1 HEAD)"
echo

restore=(); retire=(); same=()
while IFS= read -r f; do
  if git cat-file -e "$GOOD_COMMIT:$f" 2>/dev/null; then
    if git show "$GOOD_COMMIT:$f" | cmp -s - "$f"; then same+=("$f"); else restore+=("$f"); fi
  else
    retire+=("$f")
  fi
done < <(git ls-files '*.html')

printf 'WOULD RESTORE from %s (%d files):\n' "$GOOD_COMMIT" "${#restore[@]}"
for f in "${restore[@]}"; do
  printf '  %-36s now %7s bytes  ->  original %7s bytes\n' "$f" "$(wc -c <"$f")" "$(git show "$GOOD_COMMIT:$f" | wc -c)"
done
echo
printf 'WOULD MOVE to _retired_generated/ (not in %s, created by the conversion) (%d files):\n' "$GOOD_COMMIT" "${#retire[@]}"
for f in "${retire[@]}"; do printf '  %s\n' "$f"; done
echo
printf 'Unchanged since %s: %d files\n' "$GOOD_COMMIT" "${#same[@]}"
echo

if [[ $APPLY -eq 0 ]]; then
  echo "DRY RUN ONLY. Nothing was changed. Re-run with --apply to perform the above on branch $BRANCH."
  exit 0
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree not clean. Commit or stash first (git stash push -m 'pre-recovery'). Nothing done."
  exit 1
fi
git switch -c "$BRANCH"
for f in "${restore[@]}"; do git restore --source="$GOOD_COMMIT" --worktree --staged -- "$f"; done
if [[ ${#retire[@]} -gt 0 ]]; then
  mkdir -p _retired_generated
  for f in "${retire[@]}"; do git mv "$f" "_retired_generated/$f"; done
fi
echo; git status --short | head -80; echo
echo "Done on branch $BRANCH (nothing committed). Review with:  git diff --cached --stat"
echo "Then commit:  git commit -m 'Restore original HTML fragments from $GOOD_COMMIT; retire generated pages'"
