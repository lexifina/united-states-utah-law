"""The chapters of the Laws of Utah: for each chapter, its bill, short title and effective date, read from the chapter
headings of the annual volumes (/documents/Sessionlaws/laws<YYYY>.pdf). A heading reads:

    CHAPTER 16
    H. B. 11
    Passed February 20, 2019
    Approved March 13, 2019
    Effective March 13, 2019
    (Retrospective operation to January 1, 2019)
    PROPERTY TAX AMENDMENTS
    Chief Sponsor: ...

and the running head of its page names the session ("General Session - 2019", "Third Special Session - 2018").
Where the heading notes an exception clause, the bill's own "Effective date" section is kept, so a section of the code
can be matched with the date the clause gives it.
"""

from __future__ import annotations

import re
from datetime import datetime

_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE = re.compile(rf"({_MONTHS})\s+(\d{{1,2}}),\s*(\d{{4}})")
_ORD = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5, "Sixth": 6, "Seventh": 7, "Eighth": 8}
_SESSION = re.compile(r"^(General|(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth) Special) Session\s*-\s*(\d{4})$", re.M)
_HEAD = re.compile(r"(?m)^\s*CHAPTER (\d+)\s*\n\s*((?:[HS]\.\s*[A-Z. ]*?\d+))\s*\n\s*Passed (.*?)\n((?:(?![^\n]*Effective)[^\n]*\n){0,3})([^\n]*Effective[^\n]*)\n")
_EFFSEC = re.compile(r"Section\s+(\d+)\.\s+Effective dates?\.(.*?)(?=\nSection\s+\d+\.\s|\Z)", re.S)


def _iso(text: str) -> str:
    m = _DATE.search(text or "")
    if not m:
        return ""
    return datetime.strptime(f"{m.group(1)} {int(m.group(2))} {m.group(3)}", "%B %d %Y").date().isoformat()


def session_code(kind: str, ordinal: str, year: str) -> str:
    """"2019GS", "2018S3": the code's own key for a session (the sess attribute of its history notes)."""
    return f"{year}GS" if kind == "General" else f"{year}S{_ORD[ordinal]}"


def chapters(pdf_bytes: bytes) -> dict[str, dict]:
    """"2019GS-16" -> {bill, title, passed, approved, effective, note, effective_text}."""
    import pymupdf

    out: dict[str, dict] = {}
    if not pdf_bytes:
        return out
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    texts = [p.get_text() for p in doc]
    heads = []   # (page, match, session)
    for i, text in enumerate(texts):
        sm = _SESSION.search("\n".join(text.split("\n")[:4]))
        for m in _HEAD.finditer(text):
            if not sm:
                continue
            # The session's year is the year the bill passed: a running head can carry a misprinted year
            # ("General Session - 2022" over chapters of 2024).
            year = (_iso(m.group(3)) or sm.group(3))[:4]
            heads.append((i, m, session_code(sm.group(1).split()[0], sm.group(2) or "", year)))
    for n, (i, m, sess) in enumerate(heads):
        rest = texts[i][m.end():]
        lines = [x.strip() for x in rest.split("\n")]
        note = ""
        if lines and lines[0].startswith("("):
            note_lines = []
            while lines and not note.endswith(")"):
                note_lines.append(lines.pop(0))
                note = " ".join(note_lines)
        title = []
        for x in lines:
            if x.startswith("Chief Sponsor") or x.startswith("Senate Sponsor") or x.startswith("House Sponsor") or x == "LONG TITLE":
                break
            if x:
                title.append(x)
        key = f"{sess}-{int(m.group(1))}"
        entry = {
            "bill": re.sub(r"\s+", " ", m.group(2)).strip(), "title": " ".join(w[:1].upper() + w[1:].lower() for w in " ".join(title).split()),
            "passed": _iso(m.group(3)), "approved": _iso(m.group(4)) if "Approved" in m.group(4) else "", "passage_note": re.sub(r"\s+", " ", m.group(4)).strip(), "effective": _iso(m.group(5)) if m.group(5).strip().startswith("Effective ") else "",
            "effective_raw": m.group(5).strip(), "note": note, "effective_text": "",
        }
        if note:
            # The chapter's text runs to the next chapter heading; keep its effective-date section.
            j_end = heads[n + 1][0] if n + 1 < len(heads) else len(texts)
            body = texts[i][m.end():] + "\n" + "\n".join(texts[i + 1:j_end + 1] if j_end > i else [])
            if n + 1 < len(heads) and heads[n + 1][0] == j_end:
                cut = body.find(f"CHAPTER {heads[n + 1][1].group(1)}\n")
                if cut > 0:
                    body = body[:cut]
            found = list(_EFFSEC.finditer(body))
            if found:
                entry["effective_text"] = re.sub(r"\s+", " ", found[-1].group(2)).strip()
        if key not in out:
            out[key] = entry
    return out


_SID = r"\d+[A-Z]?-\d+[a-z]?-\d+(?:\.\d+)?"


def date_for(entry: dict, sid: str) -> tuple[str, str]:
    """The date a chapter's change to one section took effect, and why; ("", reason) when the record does not say."""
    if not entry.get("effective"):
        return "", f"the chapter heading gives no date ({entry.get('effective_raw', '')})"
    note = entry.get("note", "")
    if not note or note.lower().startswith("(retrospective"):
        return entry["effective"], ""
    text = entry.get("effective_text", "")
    if not text:
        return "", f"the chapter takes effect {entry['effective']} with an exception clause that was not found"
    if not re.search(_SID, text):
        return "", f"the chapter takes effect {entry['effective']} with an exception clause that does not name code sections"
    # Items "(1) ... (2) ..." of the clause; the item naming this section gives its date.
    items = re.split(r"\(\d+\)\s", text)
    for item in items:
        if re.search(rf"(?<![\w.-]){re.escape(sid)}(?![\w-]|\.\d)", item):
            d = _iso(item)
            if d:
                return d, f"the chapter's exception clause gives this section {d}"
            return "", "the chapter's exception clause names this section without a date"
    return entry["effective"], "the chapter's exception clause does not name this section"
