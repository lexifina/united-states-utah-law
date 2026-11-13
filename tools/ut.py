#!/usr/bin/env python3
"""Read the Utah Code history by date. Needs Python 3.8 or later and git; run it inside the repository.

  python tools/ut.py on 2022-05-01 title-76/76-5-203.md          the text in force on a date
  python tools/ut.py diff 2019-01-01 2024-01-01 title-76/76-5-203.md [--words]
  python tools/ut.py log title-76/76-5-203.md                    every change to a section, with its dates
  python tools/ut.py law "2019, ch. 16"                          every change one chapter of the Laws of Utah made
                                                                 (special sessions: "2018, Special Session 3, ch. 1")

A commit's date is its In-force: trailer, corrected by any later Lexifina Redates: trailer. Redates: ... no-date
means the source gives no effective date; the reader keeps the version selectable from the first archive that prints
it and shows it as text as of that day. A section's text on a date is selected from that section's latest dated or
text-as-of version, including historical corrections appended after newer commits.
A correction with Files: and Supersedes: replaces only the named section versions.
Restoration commits keep the tree at current text but do not supply a new effective date.
"""
import re
import subprocess
import sys

BASELINE_SHA = "8253d4b362de506c25a4e1c2ee841e85c6cea567"
BASELINE_DAY = "2026-05-12"


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def git_path(path):
    return path.replace("\\", "/")


def redates():
    fmt = "%H%x1f%an%x1f%(trailers:only,unfold)%x1e"
    out = {}
    for rec in git("log", "--reverse", "--format=" + fmt, "HEAD").split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        commit, author, trailers = rec.split("\x1f", 2)
        if author != "Lexifina":
            continue
        for target, when in re.findall(r"(?m)^Redates:\s*([0-9a-f]{7,40})\s+(\d{4}-\d{2}-\d{2}|no-date)\s*$", trailers):
            out[target] = when
    return out


def redate_for(commit, mapping):
    return mapping.get(commit) or next((when for prefix, when in mapping.items() if commit.startswith(prefix)), "")


def superseded(path):
    if not path:
        return set()
    targets = set()
    fmt = "%an%x1f%(trailers:only,unfold)%x1e"
    for rec in git("log", "--format=" + fmt, "HEAD").split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        author, trailers = rec.split("\x1f", 1)
        if author != "Lexifina" or not re.search(r"(?m)^Kind:\s*correction\s*$", trailers):
            continue
        files = re.findall(r"(?m)^Files:\s*(.+)$", trailers)
        if git_path(path) not in {f.strip() for line in files for f in line.split(",")}:
            continue
        for line in re.findall(r"(?m)^Supersedes:\s*(.+)$", trailers):
            targets.update(re.findall(r"\b[0-9a-f]{40}\b", line))
    return targets


def history(path=None):
    fmt = "%H%x1f%ad%x1f%an%x1f%s%x1f%(trailers:key=In-force,valueonly,separator=%x2c)%x1e"
    mapping = redates()
    replaced = superseded(path)
    out = []
    args = ["log", "--reverse", "--date=short", "--format=" + fmt, "HEAD"]
    if path:
        args += ["--", git_path(path)]
    for rec in git(*args).split("\x1e"):
        rec = rec.strip("\n")
        if rec:
            commit, authored, author, subject, in_force = rec.split("\x1f")
            if commit in replaced:
                continue
            if subject.startswith(("Restore May 2026", "Restore the May 2026")):
                continue
            recorded = in_force.strip().split(",")[0] or authored
            fixed = redate_for(commit, mapping)
            if fixed == "no-date":
                out.append((recorded, f"text as of {recorded}", commit, author, subject))
            elif fixed:
                out.append((fixed, fixed, commit, author, subject))
            else:
                out.append((recorded, recorded, commit, author, subject))
    return out


def day(text):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        sys.exit("Dates are written YYYY-MM-DD, not %r." % text)
    return text


def commit_on(date, path):
    path = git_path(path)
    hist = history(path)
    chosen = [(h[0], i, h) for i, h in enumerate(hist) if h[0] <= date]
    # The baseline also records absence: paths missing from its tree have no
    # path-specific git log entry, but must be absent again by this day.
    if not chosen and BASELINE_DAY <= date:
        chosen.append((BASELINE_DAY, -1, (BASELINE_DAY, BASELINE_DAY, BASELINE_SHA, "", "baseline")))
    if not chosen:
        sys.exit("%s is before this section's recorded history." % date)
    return max(chosen)[2]


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "on" and len(argv) == 4:
        path = git_path(argv[3])
        try:
            sys.stdout.write(git("show", "%s:%s" % (commit_on(day(argv[2]), path)[2], path)))
            return 0
        except subprocess.CalledProcessError:
            print("%s was not in the Utah Code on %s (or is before this history starts)." % (argv[3], argv[2]))
            return 1
    if cmd == "log" and len(argv) == 3:
        path = git_path(argv[2])
        dates = {h[2]: h[1] for h in history()}
        for line in git("log", "--reverse", "--format=%H%x1f%an%x1f%s", "--", path).splitlines():
            commit, author, subject = line.split("\x1f")
            print("%s  %s  %s\n            %s" % (dates.get(commit, "?"), commit[:10], author, subject))
        return 0
    if cmd == "diff" and len(argv) in (5, 6):
        path = git_path(argv[4])
        a, b = commit_on(day(argv[2]), path)[2], commit_on(day(argv[3]), path)[2]
        sys.stdout.write(git("diff", *(["--word-diff"] if argv[-1] == "--words" else []), a, b, "--", path))
        return 0
    if cmd == "law" and len(argv) == 3:
        sys.stdout.write(git("log", "-E", "--stat", "--format=%n%ad  %an%n  %s", "--date=short",
                             "--author=^Laws of Utah " + re.sub(r"([.()\[\]*+?])", r"\\\1", argv[2]) + "( |$)"))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
