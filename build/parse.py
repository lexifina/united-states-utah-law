"""Sections of the Utah Code from the Legislature's title XML and from its archived title PDFs, in one form.

A section version is a dict:
    sid      section number, e.g. "76-5-203"
    heading  the catchline, e.g. "Murder."
    lines    [(depth, text)]: depth -1 for an undesignated paragraph of the section, d >= 0 for a designated
             provision at designation depth d (its text starts with the designation, "(1) ..."), and d + 0.5 for an
             undesignated paragraph inside a provision of depth d
    history  the history note lines, e.g. ["Amended by Chapter 378, 2010 General Session"]
    eff      the effective date the source gives this version ("YYYY-MM-DD"), or ""
    end      the date the source says this version stops applying, or ""
    end_kind what happens then: "superseded", "renumbered", "repealed", or ""
    words    the words of the source, in order, for the render check
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

_WS = re.compile(r"\s+")
_MD = re.compile(r"([\\*_`<])")


def _tidy(s: str) -> str:
    return _WS.sub(" ", s).strip()


def mdy(s: str) -> str:
    """"1/1/2027" or "07/01/19" -> "2027-01-01" / "2019-07-01"."""
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\s*", s)
    if not m:
        return ""
    mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return ""


# ---- XML ----

_END_KIND = {"SC": "superseded", "RN": "renumbered", "SN": "repealed", "RP": "repealed"}


class _Lines:
    """Collects text into paragraphs: a paragraph ends at <eol/> or where a provision starts or ends."""

    def __init__(self) -> None:
        self.lines: list[tuple[float, str]] = []
        self.buf: list[str] = []
        self.depth: float = -1

    def flush(self) -> None:
        text = _tidy("".join(self.buf))
        if text:
            self.lines.append((self.depth, text))
        self.buf = []

    def start(self, depth: float, prefix: str = "") -> None:
        self.flush()
        self.depth = depth
        if prefix:
            self.buf.append(prefix + " ")


def _designation(number: str) -> tuple[int, str]:
    parts = re.findall(r"\(([^)]*)\)", number)
    return len(parts) - 1, f"({parts[-1]})" if parts else ""


def _one(c: ET.Element, out: _Lines, depth: float) -> None:
    """One element inside a paragraph, and its tail, with line breaks at <eol/>."""
    if c.tag == "eol":
        d = out.depth
        out.start(d + 0.5 if d >= 0 and d == int(d) else d)
    elif c.tag in ("tab", "marker", "contingent", "effdate", "enddate"):
        pass
    elif c.tag == "char":
        out.buf.append("•")   # the code's bullet character (Wingdings set 4, char 3)
    elif c.tag in ("right", "center"):
        out.buf.append(" ")
        out.buf.append(c.text or "")
        for x in c:
            _one(x, out, depth)
        out.buf.append(" ")
    elif c.tag == "tbl":
        out.start(depth)
        for row in c:
            if row.tag != "row":
                continue
            cells = [_tidy(" ".join(x.itertext())) for x in row if x.tag == "cell"]
            if any(cells):
                out.lines.append((depth, " | ".join(x for x in cells if x)))
        out.start(depth)
    else:   # xref, format and anything else inline: its text
        out.buf.append(c.text or "")
        for x in c:
            _one(x, out, depth)
    out.buf.append(c.tail or "")


def _walk(e: ET.Element, out: _Lines, depth: float) -> None:
    """A section or provision: its own text, then its provisions."""
    out.buf.append(e.text or "")
    for c in e:
        if c.tag in ("histories", "catchline"):
            out.buf.append(c.tail or "")
        elif c.tag == "subsection":
            d, label = _designation(c.get("number", ""))
            out.start(d, label)
            _walk(c, out, d)
            out.start(d + 0.5)
            out.buf.append(c.tail or "")
        else:
            _one(c, out, out.depth)


def xml_sections(data: bytes) -> list[dict]:
    """Every section version in a title XML (a section can appear twice: the version in force and a future one)."""
    if not data:
        return []
    root = ET.fromstring(data)
    out = []
    for sec in root.iter("section"):
        sid = sec.get("number", "").strip()
        cat = sec.find("catchline")
        heading = _tidy("".join(cat.itertext())) if cat is not None else ""
        history = [_tidy("".join(h.itertext())) for h in sec.iter("history")]
        eff = sec.find("effdate")
        end = sec.find("enddate")
        lines = _Lines()
        _walk(sec, lines, -1)
        lines.flush()
        # The render check reads every text node of the section other than the catchline, history and dates.
        words = _xml_words(sec)
        out.append({
            "sid": sid, "heading": heading, "lines": lines.lines, "history": history,
            "eff": mdy(eff.text or "") if eff is not None else "",
            "end": mdy(end.text or "") if end is not None else "",
            "end_kind": _END_KIND.get(end.get("type", ""), "ended") if end is not None else "",
            "words": words,
        })
    return out


_SKIP_TEXT = {"histories", "catchline", "effdate", "enddate"}


def _xml_words(sec: ET.Element) -> list[str]:
    parts: list[str] = []

    def go(e: ET.Element) -> None:
        if e.tag in _SKIP_TEXT:
            return
        if e.tag == "subsection":
            parts.append(" " + _designation(e.get("number", ""))[1] + " ")
        if e.tag == "char":
            parts.append(" • ")
        if e.tag in ("right", "center", "cell"):
            parts.append(" ")
        parts.append(e.text or "")
        for c in e:
            go(c)
            parts.append(c.tail or "")
        if e.tag in ("eol", "cell", "row", "right", "center"):
            parts.append(" ")

    go(sec)
    return "".join(parts).split()


# ---- Rendering ----

def esc(s: str) -> str:
    return _MD.sub(r"\\\1", s)


def render(v: dict) -> str:
    head = f"# Utah Code § {v['sid']}" + (f". {esc(v['heading'])}" if v["heading"] else "")
    body = []
    for depth, text in v["lines"]:
        if depth < 0:
            body.append(esc(text))
        elif depth == int(depth):
            body.append("  " * int(depth) + "- " + esc(text))
        else:
            body.append("  " * (int(depth) + 1) + esc(text))
    out = [head, ""] + body
    if v["history"]:
        out += [""] + [esc(h) + "  " if i < len(v["history"]) - 1 else esc(h) for i, h in enumerate(v["history"])]
    return "\n".join(out).rstrip() + "\n"


def rendered_words(v: dict) -> list[str]:
    return [w for w in " ".join(t for _, t in v["lines"]).split() if w != "|"]


def key(v: dict) -> str:
    """What makes two versions the same: heading, words and history, ignoring spacing, paragraph breaks, the length
    of a rule of underscores and the bullet character (the PDFs draw bullets as graphics, without text)."""
    words = re.sub(r"_+", "_", "".join(rendered_words(v)).replace("•", ""))
    return "\x1f".join([v["heading"].replace(" ", ""), words, "|".join(h.replace(" ", "") for h in v["history"])])


# ---- PDF (the archived titles, typeset by Apache FOP) ----

_HIST = re.compile(r"^(Amended|Enacted|Renumbered|Repealed|Technically|No Change|Sunset|Revised|Re-?enacted|Recodified|Effective|Contingently)\b.*\b(by|Since|Chapter|Session|Section)\b")
_DESIG = re.compile(r"^\((\d+[a-z]?|[a-z]{1,2}|[ivxl]+|[A-Z]{1,2}|[IVXL]+|[A-Z][a-z]|[IVX]+[ivx]+)\)")
_SEC_HEAD = re.compile(r"^(\d+[A-Za-z]?-\d+[a-zA-Z]?-\d+(?:\.\d+)?)(?:\s+\((Effective|Superseded|Repealed|Renumbered|Contingently [A-Za-z]+|Repealed and Reenacted|Effective until|Effective upon[^)]*?)\s*([\d/]+)?\))?\s*(.*)$")
_MARK_KIND = {"Superseded": "superseded", "Repealed": "repealed", "Renumbered": "renumbered"}


def _pdf_lines(doc) -> list[dict]:
    """Every text line of the body, in reading order, without the running head and page number."""
    out = []
    for pno, page in enumerate(doc):
        height = page.rect.height
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                spans = [s for s in l["spans"] if s["text"]]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans)
                y = l["bbox"][1]
                if (y < 25 and text.strip() == "Utah Code") or (y > height - 45 and re.fullmatch(r"\s*Page \d+\s*", text)):
                    continue
                out.append({
                    "page": pno, "x": l["bbox"][0], "y": y, "x1": l["bbox"][2], "text": text,
                    "bold": all("Bold" in s["font"] for s in spans if s["text"].strip()),
                    "size": max(s["size"] for s in spans),
                    "font": spans[-1]["font"],
                })
    return out


def pdf_sections(data: bytes) -> list[dict]:
    """Every section version printed in an archived title PDF."""
    import pymupdf

    if not data:
        return []
    doc = pymupdf.open(stream=data, filetype="pdf")
    lines = _pdf_lines(doc)
    right = max((l["x1"] for l in lines if not l["bold"]), default=570.0)
    out: list[dict] = []
    i = 0
    n = len(lines)
    marker = None
    while i < n:
        l = lines[i]
        if not (l["bold"] and l["size"] < 12.5 and _SEC_HEAD.match(l["text"].strip())):
            if l["bold"] and "Oblique" in l["font"]:
                _, mk = _split_marker([l])
                marker = mk or marker
            i += 1
            continue
        # The heading: one or more bold lines.
        head = [l]
        i += 1
        while i < n and lines[i]["bold"] and lines[i]["size"] < 12.5 and not _SEC_HEAD.match(lines[i]["text"].strip()) and lines[i]["y"] - head[-1]["y"] < 20 and lines[i]["page"] == head[-1]["page"]:
            head.append(lines[i])
            i += 1
        body = []
        while i < n and not (lines[i]["bold"] and (lines[i]["size"] >= 12.5 or _SEC_HEAD.match(lines[i]["text"].strip()))):
            body.append(lines[i])
            i += 1
        body, next_marker = _split_marker(body)
        out.append(_pdf_section(head, body, right, marker))
        marker = next_marker
    return out


def _gap(a: dict, b: dict) -> float:
    return b["y"] - a["y"] if a["page"] == b["page"] else 14.4


def _split_marker(body: list[dict]) -> tuple[list[dict], tuple[str, str] | None]:
    """A version printed twice is preceded by a bold oblique line, "Effective 7/1/2027", "Superseded 7/1/2027" or
    "Contingently Effective 1/1/2027", set just before its heading, so at the end of the body before it. A line
    "(Contingently Repealed)" carries no date and is left out."""
    marker = None
    while body:
        t = body[-1]["text"].strip()
        if re.fullmatch(r"\(?Contingently [A-Za-z]+\)?", t):
            body = body[:-1]
            continue
        mm = re.match(r"^(?:Contingently\s+)?(Effective|Superseded|Repealed|Renumbered)\s+([\d/]+)\s*$", t)
        if mm and body[-1]["bold"] and "Oblique" in body[-1]["font"] and marker is None:
            marker = (mm.group(1), mm.group(2))
            body = body[:-1]
            continue
        break
    return body, marker


def _pdf_section(head: list[dict], body: list[dict], right: float, marker: tuple[str, str] | None = None) -> dict:
    htext = _tidy(" ".join(h["text"] for h in head))
    m = _SEC_HEAD.match(htext)
    sid, mark, mdate, heading = m.group(1), m.group(2) or "", m.group(3) or "", _tidy(m.group(4))
    first, _, rest = sid.partition("-")
    sid = first.upper() + "-" + rest   # a title's letter is a capital ("26b-2-902" is a misprint of 26B-2-902)
    if marker:
        mark, mdate = marker
    # The history note: the lines after the last wide gap that read like history notes.
    hist_start = len(body)
    for k in range(len(body) - 1, -1, -1):
        if _HIST.match(body[k]["text"].strip()):
            hist_start = k
            if k > 0 and _gap(body[k - 1], body[k]) > 20:
                break
        else:
            hist_start = k + 1
            break
    hist_lines, body = body[hist_start:], body[:hist_start]
    history: list[str] = []
    for h in hist_lines:
        t = _tidy(re.sub(r"\s*\(Contingently [A-Za-z]+\)\s*$", "", h["text"]))
        if not t:
            continue
        if history and not _HIST.match(t):
            history[-1] += " " + t
        else:
            history.append(t)

    paras: list[list] = []   # [depth, start_x, cont_x, [texts], label]
    last_top = 0             # the last number designating a provision at depth 0
    for ln in body:
        raw = ln["text"]
        text = raw.strip()
        tab = raw.startswith("  ")
        x = ln["x"]
        desig = _DESIG.match(text)
        cur = paras[-1] if paras else None
        if cur is not None and not tab:
            cont = False
            if cur[2] is not None and abs(x - cur[2]) < 2.5:
                # A line at the continuation indent; at 43 points it may instead start a provision of depth 0
                # after an undesignated paragraph, when it carries the next number.
                top = desig and abs(x - 43) < 2.5 and cur[0] < 0 and desig.group(1).isdigit() and int(desig.group(1)) == last_top + 1
                cont = not top
            elif cur[2] is None and not desig and cur[0] != int(cur[0]) or (cur[2] is None and not desig and cur[0] < 0):
                cur[2] = x
                cont = True
            if cont:
                cur[3].append(raw)
                continue
        if desig and not tab:
            depth: float = max(0, round((x - 43) / 9))
            if depth == 0 and desig.group(1).isdigit():
                last_top = int(desig.group(1))
            paras.append([depth, x, x + 18, [raw], desig.group(0)])
        elif tab and x < 30:
            paras.append([-1, x, 43.0, [raw], ""])
        else:
            parent = next((p[0] for p in reversed(paras) if p[0] >= 0 and p[0] == int(p[0])), None)
            depth = -1 if parent is None else parent + 0.5
            paras.append([depth, x, None, [raw], ""])
    out_lines = []
    for depth, _, _, texts, _ in paras:
        joined = ""
        for t in texts:
            t = t.strip()
            if not joined:
                joined = t
            elif joined.endswith("-") and not joined.endswith("--") and re.search(r"[A-Za-z0-9]-$", joined):
                joined += t
            elif joined.endswith(")") and re.match(r"\([0-9a-zA-Z]{1,6}\)", t) and re.search(r"\([0-9a-zA-Z]{1,6}\)$", joined):
                joined += t
            else:
                joined += " " + t
        joined = _tidy(joined)
        if depth >= 0 and depth == int(depth):
            joined = re.sub(r"^(\([^)\s]+\))(?=\S)", r" ", joined)
        out_lines.append((depth, joined))
    words = " ".join(_tidy(l["text"]) for l in body).split()
    eff = end = kind = ""
    if mark.startswith("Effective"):
        eff = mdy(mdate)
    elif mark:
        end, kind = mdy(mdate), _MARK_KIND.get(mark.split()[0], "ended")
    return {"sid": sid, "heading": heading, "lines": out_lines, "history": history, "eff": eff, "end": end,
            "end_kind": kind, "mark": mark, "mark_date": mdate, "words": words}
