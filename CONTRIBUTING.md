# Editing the RECSL website

The website at https://www.xiaocatalysis.com is built automatically from this
repository. You edit a content file here on GitHub, commit, and about two
minutes later the change is live. There is no separate upload step.

## How the site is built

Each page is a small `.php` file that glues together three parts:
`Header.html` (menu) + a **content fragment** + `Footer.html`.
You edit only the content fragment. The build (GitHub Actions, see the
"Actions" tab) renders the pages, checks links, and publishes them.

## Which file to edit

| Page on the website | Edit this file |
|---|---|
| Home – recent news box | `News_recent.html` |
| Home – welcome text | `Welcome.html` |
| Home – funding logos | `Funding.html` |
| Home – slideshow | `Slides.html` |
| News (full list) | `News.html` |
| PI: Dr. Xiao | `Biography.html` |
| Postdocs | `Associates.html` |
| Graduate Students | `Graduate_Members.html` |
| UG Students | `UG_Members.html` |
| Alumni | `Alumni.html` |
| Research | `Research.html` |
| Journal Articles (also shown on Publications) | `Journal_Articles.html` |
| Conference Presentations | `Conference_Presentations.html` |
| Licensed / Granted Patents, Applications | `Licensed_Patents.html`, `Granted_Patents.html`, `Patent_Applications.html` |
| Resources | `Resources.html` |
| Teaching | `Courses.html` |
| Group Photos / Media Reports / Outreach | `Group_photos.html`, `Media_reports.html`, `Outreach.html` |
| Contact | `Contact.html` |

Images go in `assets/img/…`, PDFs in `PDF/`. Link to them with relative
paths exactly like the existing entries do (`PDF/Xiao2026a.pdf`,
`assets/img/members/name.jpg`).

## Do NOT edit

- `Header.html`, `Footer.html` (menu and footer, shared by every page) – ask Dr. Xiao
- any `.php` file, `tools/`, `.github/`, `build.sh`
- anything in `_retired_generated/` (old files, not used)
- files ending in `2.html`, `3.html`, `(copy).html` – old drafts, not published

Links inside content files point to `.php` pages (e.g. `Biography.php`).
Keep it that way; the build converts them to `.html` automatically.

## How to make a change on GitHub

1. Open the file in the table above and click the pencil icon ("Edit this file").
2. Make your change. Copy an existing entry and modify it rather than typing
   HTML from scratch; keep the tags balanced (`<li> … </li>`).
3. Click **Commit changes**, write a short message such as
   `Add Smith et al. 2026 to journal articles`, and commit to `main`.
4. Open the **Actions** tab. The newest run "Build and deploy site" should turn
   green within about two minutes. Red means the build found a broken link:
   click the run, read the message, fix the file.
5. Reload the website (Ctrl+Shift+R to bypass the cache) and check your change.

To add a photo or PDF: open the target folder (`assets/img/…` or `PDF/`),
click **Add file → Upload files**, upload, commit. Then reference it from the
content file.

## If something goes wrong

Nothing is lost: every version is kept. Open the **Commits** list (clock icon
on the repository front page), find the bad commit, click the `…` menu and
choose **Revert**, then commit the revert. The previous version is republished
automatically. Or simply tell Dr. Xiao which commit to undo.

## Checklist before committing

- [ ] I edited a content fragment from the table, not Header/Footer/PHP.
- [ ] Names, dates, titles and DOIs are correct.
- [ ] New images/PDFs are uploaded and the path matches exactly (case matters).
- [ ] I copied an existing entry's HTML structure.
