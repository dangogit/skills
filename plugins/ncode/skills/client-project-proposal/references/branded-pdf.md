# Branded Hebrew PDF

The default deliverable for a new proposal: a Hebrew RTL PDF with the user's logo and brand color.
Use the DOCX helper or Google Docs only when an editable document is requested; the DOCX helper
prints workdays per milestone, which `defaults.md` keeps out of client copy.

## Files

- `assets/branded-proposal-template.html`: page skeleton and styles. Copy it into the case
  directory, replace every `[bracket]` with real content and the business details from
  `defaults.md`, delete sections that do not apply, and keep `{{LOGO}}` where the logo goes.
- `scripts/render_branded_pdf.py`: embeds the logo, isolates English runs inside Hebrew lines,
  refuses em dashes and leftover placeholders, prints A4 with headless Chrome. Without `--logo`
  it renders without a logo.

Brand: set the accent in the template's `:root` (`--accent`, `--accent-dark`, `--accent-soft`)
to the color in `defaults.md`. The font is Heebo from Google Fonts, which needs network at render
time; any installed Hebrew font works as the fallback. Headings stay black; the accent is for
markers, bars and the price box label.

Requirements: Google Chrome, and poppler (`pdftoppm`, `pdftotext`) for checking pages.
`--chrome` sets the Chrome path when it is not the macOS default.

## Render and check

```sh
python3 -I -B scripts/render_branded_pdf.py <case>/proposal.html <case>/proposal.pdf --logo <logo.png>
pdftoppm -r 90 -png <case>/proposal.pdf <case>/pages/p
```

- View every page image one at a time. Check that no heading or table is split from its content,
  the title fits one line, digits and English words keep their order inside Hebrew lines, and
  page breaks leave no large gaps. Use `class="page-break"` on an `h2` and `class="keep"` on blocks.
- Wrap every number, date and amount in `<span class="num">`. Avoid starting a line with a
  number followed by English; isolate it.
- Check arithmetic: the two payments sum to the total, VAT is computed at the current rate, and
  the total with VAT is right.
- Extract the text (`pdftotext`) and grep for anything `defaults.md` keeps out of client copy:
  workday counts, per-stage prices, the AI tools you build with.
- Save the final PDF in the folder named in `defaults.md` as
  `הצעת מחיר - <לקוח> - <נושא>.pdf`, with the built HTML next to it.
