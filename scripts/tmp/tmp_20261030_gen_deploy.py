# -*- coding: utf-8 -*-
"""Generate strategy_deploy.py (comment-stripped) from strategy.py via tokenize."""
import ast
import io
import tokenize
from pathlib import Path

ROOT = Path(r"D:\PROJ\PT\strategies\buysell_core")
SRC = ROOT / "strategy.py"
DST = ROOT / "strategy_deploy.py"


def strip_comments(source: str) -> str:
    # tokenize 的 start/end 是 (行号, 列号)，必须按真实行字符长度换算绝对偏移；
    # 之前按 \n 计数在 CRLF 文件上错位，导致部署版内容损坏。
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    toks = list(tokenize.generate_tokens(io.StringIO(source).readline))
    parts = []
    prev_end = 0
    for tok in toks:
        if tok.type in (tokenize.ENCODING, tokenize.ENDMARKER):
            continue
        start = offsets[tok.start[0] - 1] + tok.start[1]
        end = offsets[tok.end[0] - 1] + tok.end[1]
        if tok.type == tokenize.COMMENT:
            parts.append(source[prev_end:start] + " " * (end - start))
        else:
            parts.append(source[prev_end:end])
        prev_end = end
    parts.append(source[prev_end:])
    return "".join(parts)


def compress_blank_lines(text: str) -> str:
    # 部署版规范：连续空行压缩为 1 行（对齐历史 strategy_deploy 形态）
    out = []
    prev_blank = False
    for line in text.split("\n"):
        if not line.strip():
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        out.append(line)
    return "\n".join(out)


def main():
    src = SRC.read_text(encoding="utf-8")
    gen = strip_comments(src)
    gen = compress_blank_lines(gen)
    DST.write_bytes(gen.encode("utf-8"))
    a1 = ast.parse(src)
    a2 = ast.parse(DST.read_text(encoding="utf-8"))
    if ast.dump(a1) != ast.dump(a2):
        raise SystemExit("AST mismatch after comment strip")
    print("deploy regenerated ok lines=%d" % gen.count("\n"))


if __name__ == "__main__":
    main()
