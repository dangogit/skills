"""Render a branded Hebrew proposal HTML to PDF with headless Chrome.

Embeds the logo when one is given, isolates Latin runs so they keep their order in RTL text, refuses em dashes
and unreplaced [bracket] placeholders, then prints to A4 PDF.

Usage:
    python3 -I -B render_branded_pdf.py <proposal.html> <out.pdf> [--logo logo.png] [--chrome PATH]
"""
import argparse
import base64
import re
import subprocess
import sys
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LATIN = re.compile(r"((?:[א-ת]{1,2}-)?[A-Za-z][A-Za-z0-9.@\-]*(?: [A-Za-z][A-Za-z0-9.\-]*)*)")


def isolate_latin(body: str) -> str:
    parts = re.split(r"(<[^>]+>)", body)
    out, depth = [], 0
    for part in parts:
        if part.startswith("<"):
            if re.match(r'<span class="(en|num)"', part):
                depth += 1
            elif part == "</span>" and depth:
                depth -= 1
            out.append(part)
        else:
            out.append(part if depth else LATIN.sub(r'<span class="en">\1</span>', part))
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("html", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--logo", type=Path, help="PNG logo; without it the logo is left out")
    ap.add_argument("--chrome", default=CHROME, help="path to the Chrome or Chromium binary")
    args = ap.parse_args()

    src = args.html.read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", src, flags=re.S)
    if "\u2014" in text:
        print("refused: em dash in the document", file=sys.stderr)
        return 2
    left = re.findall(r"\[[^\]]{1,40}\]", re.sub(r"<[^>]+>", " ", text.split("<body>", 1)[-1]))
    if left:
        print(f"refused: unreplaced placeholders: {sorted(set(left))[:5]}", file=sys.stderr)
        return 2
    if args.out.exists():
        print(f"refused: {args.out} exists", file=sys.stderr)
        return 2

    head, body = src.split("<body>", 1)
    html = head + "<body>" + isolate_latin(body)
    if args.logo:
        html = html.replace("{{LOGO}}", base64.b64encode(args.logo.read_bytes()).decode())
    else:
        html = re.sub(r'<img[^>]*\{\{LOGO\}\}[^>]*>', "", html)
    built = args.out.with_suffix(".build.html")
    built.write_text(html, encoding="utf-8")

    res = subprocess.run(
        [args.chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--virtual-time-budget=8000", f"--print-to-pdf={args.out}", built.resolve().as_uri()],
        capture_output=True, text=True,
    )
    if res.returncode != 0 or not args.out.exists():
        print(f"chrome failed with status {res.returncode}", file=sys.stderr)
        return 1
    print(f"pdf: {args.out}\nhtml: {built}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
