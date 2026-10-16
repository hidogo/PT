# -*- coding: utf-8 -*-
"""Convert an HTML page (markdown-body wrapper) to Markdown."""
import sys, re
from bs4 import BeautifulSoup
SRC, OUT = sys.argv[1], sys.argv[2]
NL = chr(10); TAB = chr(9); FENCE = chr(96) * 3
soup = BeautifulSoup(open(SRC, encoding="utf-8").read(), "html.parser")
for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
    tag.decompose()
body = None
for cls in ["markdown-body", "help-content", "content", "article"]:
    body = soup.find(lambda t: t.name == "div" and cls in (t.get("class") or []))
    if body: break
if body is None:
    body = soup
out = []
def esc_text(s):
    return re.sub("[" + " " + TAB + "]+", " ", s).strip()
def tbl(t):
    rows = t.find_all("tr")
    md = []
    for tr in rows:
        cells = [esc_text(td.get_text(" ", strip=True)) for td in tr.find_all(["th", "td"])]
        md.append("| " + " | ".join(cells) + " |")
    if not md: return []
    cols = md[0].count("|") - 1
    return [NL, md[0], "|" + ("---|" * cols)] + md[1:] + [NL]
for el in body.descendants:
    n = getattr(el, "name", None)
    if n in ("h1", "h2", "h3", "h4", "h5", "h6"):
        txt = esc_text(el.get_text(" ", strip=True))
        if txt:
            out.append(NL + ("#" * int(n[1])) + " " + txt + NL)
    elif n == "p":
        txt = esc_text(el.get_text(" ", strip=True))
        if txt and len(txt) > 1:
            out.append(txt + NL)
    elif n == "pre":
        if el.find("pre") is None:
            out.append(NL + FENCE + NL + el.get_text().rstrip(NL) + NL + FENCE + NL)
    elif n == "table":
        out.extend(tbl(el))
    elif n in ("li", "dt"):
        txt = esc_text(el.get_text(" ", strip=True))
        if txt:
            out.append("- " + txt + NL)
text = NL.join(out)
while (NL * 3) in text:
    text = text.replace(NL * 3, NL * 2)
open(OUT, "w", encoding="utf-8").write(text)
print("wrote", OUT)
