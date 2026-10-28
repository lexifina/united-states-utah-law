# How this history was made, and how to make it again

## Short version

```sh
cd build
python fetch.py                  # read every source again (cached; one request every 10.5 seconds: about 4 hours)
sha256sum -c DATA-SHA256SUMS     # the responses are the ones this history was built from (paths as in fetch's cache)
python build.py repo ../../rebuilt
git -C ../../rebuilt log --format=%H    # the same commits, with the same hashes
```

The build reads PDFs with PyMuPDF (1.25.5); Lexifina ran it in its backend container (Python 3.14.10). The
last change commit is `fbfda02fff8ddf97ea49a5199c19a795e1442e10`. The current code changes as laws take effect, so a fetch made later reads newer
XML; the checksums say which responses differ.

## Sources

All on le.utah.gov, published by the Office of Legislative Research and General Counsel, retrieved 28 October 2026.

| What | Where | Requests |
| --- | --- | ---: |
| robots.txt, the code index, the archive page and each archive's list of title PDFs with MD5 hashes | `https://le.utah.gov/robots.txt`, `https://le.utah.gov/xcode/C_1800010118000101.html`, `https://le.utah.gov/codeArchives.jsp`, `https://le.utah.gov/xcode/Archives/<YYYYMMDD>/<YYYYMMDD>.html` | 20 |
| The archived titles: one PDF per title on each of 2 dates from 2026-05-12 to 2026-07-20 | `https://le.utah.gov/xcode/Archives/<YYYYMMDD>/Title<N>.pdf` | 167 |
| The current code, one XML file per title | `https://le.utah.gov/xcode/Title<N>/C<N>_<version>.xml` | 96 |
| The Laws of Utah, one volume a year (8 published; 3545 chapter headings read) | `https://le.utah.gov/documents/Sessionlaws/laws<YYYY>.pdf` | 9 |

292 responses, 578,646,322 bytes. An archive title whose published MD5 equals one already downloaded is the
same file and was not downloaded again. Each PDF is checked against its published MD5; all matched. A file the Legislature does not
have answers 404 and is recorded as absent (the 2026 volume of the Laws of Utah). Every response is listed with its
sha256 in `build/DATA-SHA256SUMS` (sha256 of that list: `a68c2505003989fcdb07c14a76bd375300d7ef980a341de67213fa06e983d38f`).

**robots.txt, checked 28 October 2026.** For every user agent (and, in identical blocks, for archive.org_bot and
Slurp):

```
User-agent: *
Crawl-delay: 10
Disallow: /templates/ # This is an infinite virtual URL space
Disallow: /ASP/
Disallow: /asp/
Disallow: /includes/
Disallow: /JSP/
Disallow: /RSS/
Disallow: /lfa/cobi/t3$t/
Disallow: /lfa/dashboard_dev/
Disallow: /lfa/devTest/
```

No rule names ClaudeBot, anthropic-ai or Claude-Web. The paths used (`/xcode/`, `/documents/`, `/codeArchives.jsp`) are
allowed. The crawl delay is obeyed: one request at a time, at least 10.5 seconds apart, with the user agent
`Mozilla/5.0 (compatible; Lexifina state law history; +https://lexifina.com/watch)`. The site answered from outside the
United States without a challenge. The per-section "Historical Utah Code" form is not used: it is one request per
section and version.

## The build, step by step

1. `python fetch.py` read every source above, detached in a container from Lexifina's backend image.
2. `python build.py repo <out>` parsed the archived PDFs (by the position, indent and weight of each line: Apache FOP
   sets each provision on its own line, indented by depth), the current XML and the chapter headings of the Laws of
   Utah, and wrote the history with `git fast-import` (git 2.46.0.windows.1): the 2026-05-12 archive, then every later text
   in date order, then the documentation commit, dated 2026-10-28.
3. `python build.py check` compared every rendered section with the words of its source.

`build/build.py` has git blob `5321651d1f41f4d3349e8b9baa7b09fcb0a18881`, the same file as `scripts/state-law/ut/build.py` in Lexifina's repository.

## Decisions made by hand

1. **Dates.** A commit is dated by the effective date the code prints for a version (990 texts), or else
   by the effective date in the Laws of Utah of the chapters its history note newly names (487), or
   else by the first archive that prints it (2589), at noon UTC. A date that would not fall after
   the section's previous text is replaced by the archive date, and the commit says so.
2. **Several chapters.** When a section's new history note names several chapters, the text is the result of all of
   them, so it is dated by the latest of their effective dates and credited first to that chapter.
3. **Exception clauses.** Where a chapter's heading notes an exception clause, the bill's "Effective date" section is
   read: if one of its numbered items names the code section, that item's date is used; if none does, the chapter's
   main date is used; if the clause names no code sections at all (it refers to sections of the bill), the date is
   left to the archive.
4. **Retrospective operation.** A chapter noted "(Retrospective operation to ...)" is dated by its effective date, and
   the commit notes the retrospective operation.
5. **The archive dates.** An archive's date is the day it was posted; its PDFs may have been typeset earlier. The
   creation date of one title PDF (Title 76) in each archive:

| Archive | Title 76 PDF created |
| --- | --- |
| 2026-05-12 | not recorded |
| 2026-07-20 | 2026-07-02 |

6. **The same text.** Two printings are the same text when their catchline, words and history note match, ignoring
   spacing. A text that matches today's XML is written from the XML (its paragraphs are exact); older texts are
   written from the PDF. The PDF's lines are joined into paragraphs by indent; a line break after a hyphen is joined
   without a space.
7. **Repealed and renumbered sections** stay as a one-line note. 288 pending versions printed
   in an archive never appear as the text in force in a later source and are left out.
8. **Not included:** the code's editorial notes are not used; only the section text and the Legislature's history note.

## What AI models did

This repository was built on 28 October 2026 in **Claude Code**, Anthropic's coding tool, by the model **Claude Opus
5.5** (model id `claude-opus-5-5`), from a goal set by the user at Lexifina: to bring US state law into git, in the same
form as the US Code history. The model wrote the build scripts, `tools/ut.py` and these documents, and ran the commands
above. **No model wrote or edited any legal text, and no model is called when the history is built.** Every word comes
from the Legislature's archive PDFs and XML; every date from the code itself, the Laws of Utah or the archive dates. The
work has not been reviewed line by line by a lawyer.
