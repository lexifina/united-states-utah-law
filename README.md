# Git for the Utah Code

The Utah Code, section by section, as a git history from 2026-05-12 to 2026-10-28. **Each commit is a change
taking effect**: its author is the chapter of the Laws of Utah that made it, and its date is the day the change took
effect, wherever the Legislature's own publications give that day.

| The question | The command |
| --- | --- |
| What did Utah Code § 76-5-203 say on 1 May 2022? | `python tools/ut.py on 2022-05-01 title-76/76-5-203.md` |
| Which law wrote each line? | `git blame title-76/76-5-203.md` |
| What changed between two dates? | `python tools/ut.py diff 2019-01-01 2024-01-01 title-76/76-5-203.md --words` |
| Every change to a section, with its dates | `python tools/ut.py log title-76/76-5-203.md` |
| Everything one chapter of the Laws of Utah changed | `python tools/ut.py law "2019, ch. 16"` |
| The most amended sections of a title | `git log --format= --name-only -- title-59 \| sort \| uniq -c \| sort -rn \| head` |

`tools/ut.py` needs only Python 3 and git, and picks the text by each commit's `In-force:` date, so the answer does not
depend on your time zone or the time of day.

## What is here

28391 section files in 96 titles, and 503 commits: the starting text, 78 commits
credited to a chapter of the Laws of Utah and dated by its effective date, 415 credited to a chapter but
dated by the archive that first prints the text, 3 text differences that name no new chapter,
5 commits removing repealed or renumbered sections, and the documentation. Each section is one Markdown
file, `title-<n>/<section>.md`: the catchline, then one paragraph or numbered provision per line, indented by its
depth, then the section's history note as the Legislature prints it ("Amended by Chapter 324, 2010 General Session").

## How a change is dated and credited

The text comes from the Legislature's code archive (a PDF of every title on each of 2 dates from 2026-05-12)
and from today's code, as XML. The oldest archive is the starting point. After it, each new text of a section is dated
by, in order:

1. **The code's own effective date.** When a change is pending, the code prints the section twice, "(Superseded
   07/01/19)" and "(Effective 07/01/19)", and the XML marks the date. (990 texts.)
2. **The chapter's effective date.** The history note names the chapters of the Laws of Utah that last amended the
   section; each chapter's heading in the Laws of Utah gives its effective date ("Effective May 14, 2019"). Where the
   heading notes an exception clause, the bill's own effective-date section is read for the section in question.
   (487 texts.)
3. **Otherwise the archive.** The first archive that prints the text, and the commit says so in its subject ("dated by
   the archive") and its message. (2589 texts.) This covers changes made by the 2026 General
   Session, whose Laws of Utah volume is not yet published, and texts whose history note names no new chapter.

The author is the chapter named; `Law:` trailers list every chapter credited. Commits are dated at noon UTC.

## What it does not show

- **Before 2026-05-12.** The history starts from the oldest archive. Each section's history note still names the law
  that last changed it before then.
- **Texts between two archives.** The archives are snapshots. A section amended twice between two of them shows only
  the second text, credited to the chapters its history note names (the note lists every chapter of the latest
  session that amended it).
- **Exact dates for every change.** See above: where no source gives the effective date, the archive date is used.
- **Future changes.** Only changes in force by 2026-10-28 are here; versions the code prints as taking effect later
  are left out.
- **Which act repealed a section.** A section that disappears is kept as a one-line note, dated by the date the code
  printed for its repeal or renumbering, or by the first archive without it.
- **Official status.** The Office of Legislative Research and General Counsel publishes the official Utah Code. This
  is an unofficial arrangement of its text; for anything that matters, read the code.

## How it is built

From le.utah.gov, within its robots.txt (one request every 10.5 seconds; it sets a crawl delay of 10). The build
script is in [`build/`](build/), with the checksums of every response it read; it makes no network requests when it
writes the history, and the same responses give the same commits. [REPRODUCE.md](REPRODUCE.md) records the sources,
the commands, the software and what AI models did and did not do; [CHANGES.md](CHANGES.md) records how the history
changes.

Lexifina keeps the US Code in the same form, [lexifina/united-states-law](https://github.com/lexifina/united-states-law),
and both are part of [lexifina/global-law](https://github.com/lexifina/global-law).

Built by [Lexifina](https://lexifina.com). For corrections, open an issue.

## License

See [LICENSE.md](LICENSE.md): the Legislature claims no copyright in the code's text; the history, messages, tools and
documentation are released under CC BY 4.0.
