# -*- coding: utf-8 -*-
import re
from bs4 import BeautifulSoup
SRC = "D:/PROJ/PT/reference/ptrade-wiki.html"
OUT = "D:/PROJ/PT/reference/ptrade-wiki-API参考.md"
NL = chr(10)
TAB = chr(9)
FENCE = chr(96) * 3
raw = open(SRC, encoding="utf-8").read()
soup = BeautifulSoup(raw, "html.parser")
for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
    tag.decompose()
mbody = soup.find("div", class_="markdown-body")
if mbody is None:
    raise SystemExit("markdown-body not found; check page")
body = mbody
out = []
def esc_text(s):
    return re.sub("[" + " " + TAB + "]+", " ", s).strip()
def table_block(tbl):
    rows = tbl.find_all("tr")
    md = []
    for tr in rows:
        cells = [esc_text(td.get_text(" ", strip=True)) for td in tr.find_all(["th", "td"])]
        md.append("| " + " | ".join(cells) + " |")
    if not md:
        return []
    cols = md[0].count("|") - 1
    sep = "|" + ("---|" * cols)
    lines = [NL, md[0], sep]
    lines.extend(md[1:])
    lines.append(NL)
    return lines
for el in body.descendants:
    if getattr(el, "name", None) not in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "li", "dt", "table"):
        continue
    n = el.name
    if n == "table":
        out.extend(table_block(el))
        continue
    if n in ("h1", "h2", "h3", "h4", "h5", "h6"):
        txt = esc_text(el.get_text(" ", strip=True))
        if not txt:
            continue
        out.append(NL + ("#" * int(n[1])) + " " + txt + NL)
    elif n == "p":
        txt = esc_text(el.get_text(" ", strip=True))
        if txt and len(txt) > 1:
            out.append(txt + NL)
    elif n == "pre":
        if el.find("pre") is None:
            out.append(NL + FENCE + NL + el.get_text().rstrip(NL) + NL + FENCE + NL)
    elif n in ("li", "dt"):
        txt = esc_text(el.get_text(" ", strip=True))
        if txt:
            out.append("- " + txt + NL)
text = NL.join(out)
while (NL * 3) in text:
    text = text.replace(NL * 3, NL * 2)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(text)
print("wrote", OUT)
