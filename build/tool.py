#!/usr/bin/env python3
"""Read the Utah Code history by date. Needs Python 3.8 or later and git; run it inside the repository.

  python tools/ut.py on 2022-05-01 title-76/76-5-203.md          the text in force on a date
  python tools/ut.py diff 2019-01-01 2024-01-01 title-76/76-5-203.md [--words]
  python tools/ut.py log title-76/76-5-203.md                    every change to a section, with its dates
  python tools/ut.py law "2019, ch. 16"                          every change one chapter of the Laws of Utah made
                                                                 (special sessions: "2018, Special Session 3, ch. 1")

A commit's date is its In-force: trailer: the day its change took effect, or, where the sources give no effective date,
the day of the first archive that prints it (the commit says which). The text on a date is the file in the last commit
dated on or before it, so the answer does not depend on your time zone or the time of day.
"""
import re
import subprocess
import sys


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def history():
    fmt = "%H%x1f%ad%x1f%an%x1f%s%x1f%(trailers:key=In-force,valueonly,separator=%x2c)%x1e"
    out = []
    for rec in git("log", "--reverse", "--date=short", "--format=" + fmt, "HEAD").split("\x1e"):
        rec = rec.strip("\n")
        if rec:
            commit, authored, author, subject, in_force = rec.split("\x1f")
            out.append(((in_force.strip().split(",")[0] or authored), commit, author, subject))
    return out


def day(text):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        sys.exit("Dates are written YYYY-MM-DD, not %r." % text)
    return text


def commit_on(date):
    hist = history()
    chosen = [h for h in hist if h[0] <= date]
    if not chosen:
        sys.exit("%s is before this history starts (%s)." % (date, hist[0][0]))
    return chosen[-1]


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "on" and len(argv) == 4:
        try:
            sys.stdout.write(git("show", "%s:%s" % (commit_on(day(argv[2]))[1], argv[3])))
            return 0
        except subprocess.CalledProcessError:
            print("%s was not in the Utah Code on %s (or is before this history starts)." % (argv[3], argv[2]))
            return 1
    if cmd == "log" and len(argv) == 3:
        dates = {h[1]: h[0] for h in history()}
        for line in git("log", "--reverse", "--format=%H%x1f%an%x1f%s", "--", argv[2]).splitlines():
            commit, author, subject = line.split("\x1f")
            print("%s  %s  %s\n            %s" % (dates.get(commit, "?"), commit[:10], author, subject))
        return 0
    if cmd == "diff" and len(argv) in (5, 6):
        a, b = commit_on(day(argv[2]))[1], commit_on(day(argv[3]))[1]
        sys.stdout.write(git("diff", *(["--word-diff"] if argv[-1] == "--words" else []), a, b, "--", argv[4]))
        return 0
    if cmd == "law" and len(argv) == 3:
        sys.stdout.write(git("log", "-E", "--stat", "--format=%n%ad  %an%n  %s", "--date=short",
                             "--author=^Laws of Utah " + re.sub(r"([.()\[\]*+?])", r"\\\1", argv[2]) + "( |$)"))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
