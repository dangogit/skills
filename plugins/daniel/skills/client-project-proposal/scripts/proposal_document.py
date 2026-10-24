#!/usr/bin/env python3
"""Validate an explicit proposal JSON and render a Hebrew RTL DOCX.

Uses only the standard library and python-docx. No network or implicit prices.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
import json
from pathlib import Path
import sys
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


class ProposalError(ValueError):
    """Invalid proposal content or unsafe output destination."""


@dataclass(frozen=True)
class Totals:
    total_days: Decimal
    reserve_days: Decimal
    base_days: Decimal
    amount: Decimal


TOP_FIELDS = {
    "title", "client", "summary", "status", "timeline", "tax_note", "currency",
    "pricing", "reserve_days", "scope", "milestones", "assumptions", "excluded",
    "acceptance", "terms", "options", "third_party", "maintenance", "author",
}


def _object(value: Any, field: str, allowed: set[str]) -> dict:
    if not isinstance(value, dict):
        raise ProposalError(f"{field}: expected an object")
    extra = set(value) - allowed
    if extra:
        raise ProposalError(f"{field}: unknown fields: {', '.join(sorted(extra))}")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProposalError(f"{field}: expected nonempty text")
    if any((ord(char) < 32 and char not in "\n\t") or
           0xD800 <= ord(char) <= 0xDFFF or ord(char) in (0xFFFE, 0xFFFF)
           for char in value):
        raise ProposalError(f"{field}: unsupported XML character")
    return value


def _number(value: Any, field: str, *, positive: bool = False,
            money: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ProposalError(f"{field}: expected a decimal number, not a boolean")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ProposalError(f"{field}: invalid decimal number") from exc
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ProposalError(f"{field}: must be finite and {'positive' if positive else 'nonnegative'}")
    digits = number.as_tuple().digits
    exponent = number.as_tuple().exponent
    if len(digits) > 30 or abs(exponent) > 12:
        raise ProposalError(f"{field}: number exceeds supported precision (30 digits, exponent between -12 and 12)")
    fractional_places = max(0, -exponent)
    for digit in reversed(digits):
        if digit != 0 or not fractional_places:
            break
        fractional_places -= 1
    if money and fractional_places > 2:
        raise ProposalError(f"{field}: money must have at most two fractional digits")
    return number


def _exact(left: Decimal, right: Decimal, operation: str) -> Decimal:
    with localcontext() as context:
        context.prec = max(80, len(left.as_tuple().digits) + len(right.as_tuple().digits) +
                           abs(left.as_tuple().exponent) + abs(right.as_tuple().exponent) + 4)
        if operation == "add":
            return left + right
        if operation == "subtract":
            return left - right
        return left * right


def _texts(value: Any, field: str, *, required: bool = False) -> list[str]:
    if not isinstance(value, list) or (required and not value):
        raise ProposalError(f"{field}: expected {'a nonempty' if required else 'an'} array of text")
    for index, text in enumerate(value):
        _text(text, f"{field}[{index}]")
    return value


def _reject_constant(value: str) -> None:
    raise ProposalError(f"Nonfinite JSON number: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProposalError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load_proposal(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal,
                          parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProposalError(f"Cannot read proposal JSON: {exc}") from exc


def validate_proposal(data: Any) -> Totals:
    data = _object(data, "proposal", TOP_FIELDS)
    for key in ("title", "client", "summary", "timeline", "tax_note", "currency"):
        _text(data.get(key), key)
    if data.get("status") not in ("draft", "proposal"):
        raise ProposalError("status: expected draft or proposal")
    if "author" in data:
        _text(data["author"], "author")
    _texts(data.get("scope"), "scope", required=True)
    for field in ("assumptions", "excluded", "acceptance", "third_party", "maintenance"):
        if field in data:
            _texts(data[field], field)
    milestones = data.get("milestones")
    if not isinstance(milestones, list) or not milestones:
        raise ProposalError("milestones: expected a nonempty array")
    total_days = Decimal(0)
    row_reserve = Decimal(0)
    for index, row in enumerate(milestones):
        prefix = f"milestones[{index}]"
        row = _object(row, prefix, {"title", "days", "timing", "deliverable", "is_reserve", "reserve_days"})
        for key in ("title", "deliverable"):
            _text(row.get(key), f"{prefix}.{key}")
        if "timing" in row:
            _text(row["timing"], f"{prefix}.timing")
        days = _number(row.get("days"), f"{prefix}.days", positive=True)
        if "is_reserve" in row and not isinstance(row["is_reserve"], bool):
            raise ProposalError(f"{prefix}.is_reserve: expected a boolean")
        reserve = _number(row.get("reserve_days", 0), f"{prefix}.reserve_days")
        if row.get("is_reserve", False):
            raise ProposalError(f"{prefix}: reserve-only rows are not customer delivery milestones; embed reserve within a deliverable")
        if reserve > days:
            raise ProposalError(f"{prefix}.reserve_days: cannot exceed row days")
        if reserve == days:
            raise ProposalError(f"{prefix}: reserve-only rows are not customer delivery milestones; reserve_days must be less than days")
        total_days = _exact(total_days, days, "add")
        row_reserve = _exact(row_reserve, reserve, "add")
    declared_reserve = _number(data.get("reserve_days", row_reserve), "reserve_days")
    if declared_reserve != row_reserve:
        raise ProposalError("reserve_days: must equal reserve included in milestone rows; do not add it to the total")
    pricing = _object(data.get("pricing"), "pricing", {"mode", "rate", "amount", "expected_total"})
    if pricing.get("mode") == "daily":
        if "amount" in pricing:
            raise ProposalError("pricing: daily mode takes rate, not amount")
        rate = _number(pricing.get("rate"), "pricing.rate", positive=True, money=True)
        amount = _exact(total_days, rate, "multiply")
        _number(amount, "computed total", money=True)
        for index, row in enumerate(milestones):
            row_amount = _exact(_number(row["days"], f"milestones[{index}].days"), rate, "multiply")
            _number(row_amount, f"milestones[{index}] computed amount", money=True)
    elif pricing.get("mode") == "fixed":
        if "rate" in pricing:
            raise ProposalError("pricing: fixed mode takes amount, not rate")
        amount = _number(pricing.get("amount"), "pricing.amount", positive=True, money=True)
    else:
        raise ProposalError("pricing.mode: expected daily or fixed")
    if "expected_total" in pricing:
        expected = _number(pricing["expected_total"], "pricing.expected_total", positive=True, money=True)
        if expected != amount:
            raise ProposalError(f"pricing.expected_total: {expected} does not match computed total {amount}")
    terms = data.get("terms", [])
    if not isinstance(terms, list):
        raise ProposalError("terms: expected an array")
    for index, term in enumerate(terms):
        term = _object(term, f"terms[{index}]", {"heading", "text"})
        for key in ("heading", "text"):
            _text(term.get(key), f"terms[{index}].{key}")
    options = data.get("options", [])
    if not isinstance(options, list):
        raise ProposalError("options: expected an array")
    for index, option in enumerate(options):
        prefix = f"options[{index}]"
        option = _object(option, prefix, {"title", "description", "days", "amount", "note"})
        for key in ("title", "description"):
            _text(option.get(key), f"{prefix}.{key}")
        if "note" in option:
            _text(option["note"], f"{prefix}.note")
        if "days" in option:
            _number(option["days"], f"{prefix}.days", positive=True)
        if "amount" in option:
            _number(option["amount"], f"{prefix}.amount", money=True)
    return Totals(total_days, declared_reserve, _exact(total_days, declared_reserve, "subtract"), amount)


def number_text(value: Decimal) -> str:
    return format(value, ",f").rstrip("0").rstrip(".") if "." in format(value, ",f") else format(value, ",f")


def money_text(value: Decimal, currency: str) -> str:
    label = {"ILS": "₪", "USD": "$", "EUR": "€"}.get(currency, currency)
    return f"{number_text(value)} {label}"


def _set_child(parent, tag: str, value: str):
    child = parent.find(qn(tag))
    if child is None:
        child = OxmlElement(tag)
        parent.append(child)
    child.set(qn("w:val"), value)
    return child


def _font(properties, size: float = 11.5):
    fonts = properties.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        properties.insert(0, fonts)
    for key in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme", "csTheme"):
        fonts.attrib.pop(qn(f"w:{key}"), None)
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn(f"w:{key}"), "Arial")
    _set_child(properties, "w:sz", str(round(size * 2)))
    _set_child(properties, "w:szCs", str(round(size * 2)))


def _paragraph_rtl(paragraph):
    properties = paragraph._p.get_or_add_pPr()
    _set_child(properties, "w:bidi", "1")
    _set_child(properties, "w:jc", "start")
    paragraph.paragraph_format.line_spacing = 1.14
    paragraph.paragraph_format.space_after = Pt(7)
    return paragraph


def _run(paragraph, text: str, *, size: float = 11.5, bold: bool = False,
         ltr: bool = False):
    run = paragraph.add_run(text)
    _font(run._r.get_or_add_rPr(), size)
    run.font.color.rgb = RGBColor.from_string("000000")
    run.bold = bold
    _set_child(run._r.get_or_add_rPr(), "w:rtl", "0" if ltr else "1")
    if bold:
        _set_child(run._r.get_or_add_rPr(), "w:bCs", "1")
    return run


def _paragraph(document, text: str, *, style=None, size: float = 11.5,
               bold: bool = False, ltr: bool = False):
    paragraph = _paragraph_rtl(document.add_paragraph(style=style))
    _run(paragraph, text, size=size, bold=bold, ltr=ltr)
    return paragraph


def _heading(document, text: str):
    paragraph = _paragraph(document, text, style="Heading 1", size=15, bold=True)
    paragraph.paragraph_format.space_before = Pt(15)
    paragraph.paragraph_format.space_after = Pt(7)
    paragraph.paragraph_format.keep_with_next = True
    return paragraph


def _text_section(document, heading: str, texts: list[str]):
    if texts:
        _heading(document, heading)
        for text in texts:
            _paragraph(document, text)


def _table(document, data: dict, totals: Totals):
    rows = data["milestones"]
    has_timing = any("timing" in row for row in rows)
    daily = data["pricing"]["mode"] == "daily"
    headers = ["אבן דרך", "ימי עבודה"] + (["סכום"] if daily else []) + (["מועד משוער"] if has_timing else []) + ["תוצר למסירה"]
    if daily:
        widths = [1.05, 0.62, 1.02, 0.9, 3.08] if has_timing else [1.43, 0.62, 1.02, 3.60]
    else:
        widths = [1.45, 0.66, 0.88, 3.68] if has_timing else [1.72, 0.74, 4.21]
    table = document.add_table(rows=1, cols=len(headers))
    table.autofit = False
    for column, width in zip(table.columns, widths):
        column.width = Inches(width)
    properties = table._tbl.tblPr
    table_width = _set_child(properties, "w:tblW", str(round(sum(widths) * 1440)))
    table_width.attrib.pop(qn("w:val"), None)
    table_width.set(qn("w:w"), str(round(sum(widths) * 1440)))
    table_width.set(qn("w:type"), "dxa")
    _set_child(properties, "w:bidiVisual", "1")
    _set_child(properties, "w:jc", "right")
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        edge = OxmlElement(f"w:{side}")
        for key, value in (("val", "single"), ("sz", "4"), ("color", "D9D9D9")):
            edge.set(qn(f"w:{key}"), value)
        borders.append(edge)
    properties.append(borders)
    margins = OxmlElement("w:tblCellMar")
    for side in ("top", "left", "bottom", "right"):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), "110")
        node.set(qn("w:type"), "dxa")
        margins.append(node)
    properties.append(margins)
    _set_child(table.rows[0]._tr.get_or_add_trPr(), "w:tblHeader", "1")

    def fill(row, values, header=False, total=False):
        _set_child(row._tr.get_or_add_trPr(), "w:cantSplit", "1")
        for index, (cell, text) in enumerate(zip(row.cells, values)):
            cell.width = Inches(widths[index])
            cell.vertical_alignment = 1
            paragraph = _paragraph_rtl(cell.paragraphs[0])
            paragraph.paragraph_format.space_after = Pt(2)
            _run(paragraph, text, size=10.5, bold=header or total,
                 ltr=not header and (index == 1 or (daily and index == 2)))
            if header or total:
                shade = OxmlElement("w:shd")
                shade.set(qn("w:fill"), "F1F4F6" if header else "F8FAFB")
                cell._tc.get_or_add_tcPr().append(shade)

    fill(table.rows[0], headers, header=True)
    for item in rows:
        values = [item["title"], number_text(_number(item["days"], "days"))]
        if daily:
            row_amount = _exact(_number(item["days"], "days"), _number(data["pricing"]["rate"], "rate"), "multiply")
            values.append(money_text(row_amount, data["currency"]))
        if has_timing:
            values.append(item.get("timing", ""))
        values.append(item["deliverable"])
        fill(table.add_row(), values)
    values = ["סה״כ", number_text(totals.total_days)]
    if daily:
        values.append(money_text(totals.amount, data["currency"]))
    if has_timing:
        values.append("")
    values.append("כולל הרזרבה המפורטת באבני הדרך" if totals.reserve_days else "")
    fill(table.add_row(), values, total=True)


def build_document(data: dict, totals: Totals | None = None):
    totals = totals or validate_proposal(data)
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(0.7)
    section.left_margin = section.right_margin = Inches(0.8)
    for name, size in (("Normal", 11.5), ("Title", 25), ("Heading 1", 15), ("Heading 2", 12)):
        style = document.styles[name]
        _font(style.element.get_or_add_rPr(), size)
        _set_child(style.element.get_or_add_pPr(), "w:bidi", "1")
        _set_child(style.element.get_or_add_pPr(), "w:jc", "start")
        style.font.color.rgb = RGBColor.from_string("000000")
    title_properties = document.styles["Title"].element.get_or_add_pPr()
    for border in list(title_properties.findall(qn("w:pBdr"))):
        title_properties.remove(border)
    paragraph = _paragraph(document, "טיוטה לבדיקה" if data["status"] == "draft" else "הצעת מחיר", size=10)
    paragraph.paragraph_format.space_after = Pt(5)
    title = _paragraph(document, data["title"], style="Title", size=25, bold=True)
    title.paragraph_format.space_after = Pt(9)
    _paragraph(document, f"לכבוד {data['client']}", bold=True)
    _paragraph(document, data["summary"])
    _heading(document, "מחיר ולוח זמנים")
    price = _paragraph(document, money_text(totals.amount, data["currency"]), size=23, bold=True, ltr=True)
    price.paragraph_format.space_after = Pt(3)
    _paragraph(document, data["tax_note"], size=10.5)
    _paragraph(document, data["timeline"], bold=True)
    _paragraph(document, f"היקף העבודה: {number_text(totals.total_days)} ימי עבודה.")
    if totals.reserve_days:
        _paragraph(document, f"בתוך ההיקף כלולים {number_text(totals.reserve_days)} ימי רזרבה להתאמות ולתיקונים.", size=10.5)
    _text_section(document, "מה כלול", data["scope"])
    _heading(document, "אבני דרך ותוצרים")
    _table(document, data, totals)
    _text_section(document, "הנחות שעליהן מבוססת ההצעה", data.get("assumptions", []))
    _text_section(document, "מה אינו כלול", data.get("excluded", []))
    _text_section(document, "בדיקה ואישור התוצרים", data.get("acceptance", []))
    if data.get("terms"):
        _heading(document, "תנאי ההתקשרות")
        for term in data["terms"]:
            _paragraph(document, term["heading"], bold=True)
            _paragraph(document, term["text"])
    if data.get("options"):
        _heading(document, "אפשרויות נוספות במחיר נפרד")
        for option in data["options"]:
            _paragraph(document, option["title"], bold=True)
            _paragraph(document, option["description"])
            if "amount" in option:
                _paragraph(document, money_text(_number(option["amount"], "amount"), data["currency"]), bold=True, ltr=True)
            if "days" in option:
                _paragraph(document, f"היקף משוער: {number_text(_number(option['days'], 'days'))} ימי עבודה.")
            if "note" in option:
                _paragraph(document, option["note"], size=10.5)
    _text_section(document, "עלויות ספקים ושירותים חיצוניים", data.get("third_party", []))
    _text_section(document, "תחזוקה ותמיכה", data.get("maintenance", []))
    footer = _paragraph_rtl(section.footer.paragraphs[0])
    if data.get("author"):
        _run(footer, data["author"] + "  |  ", size=9)
    _run(footer, "עמוד ", size=9)
    run = footer.add_run()
    _font(run._r.get_or_add_rPr(), 9)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    run._r.addnext(field)
    document.core_properties.title = data["title"]
    document.core_properties.author = data.get("author", "")
    document.core_properties.subject = "הצעת מחיר"
    return document


def summary_data(data: dict, totals: Totals) -> dict:
    summary = {"status": data["status"], "currency": data["currency"],
            "pricing_mode": data["pricing"]["mode"], "total_days": str(totals.total_days),
            "base_days": str(totals.base_days), "reserve_days": str(totals.reserve_days),
            "amount": str(totals.amount), "optional_items": len(data.get("options", [])),
            "options_included_in_amount": False}
    if data["pricing"]["mode"] == "daily":
        rate = _number(data["pricing"]["rate"], "pricing.rate")
        summary["milestone_amounts"] = [
            {"title": row["title"], "days": str(_number(row["days"], "days")),
             "amount": str(_exact(_number(row["days"], "days"), rate, "multiply"))}
            for row in data["milestones"]
        ]
    return summary


def write_outputs(data: dict, out: Path, summary_out: Path | None = None) -> Totals:
    totals = validate_proposal(data)
    destinations = [out] + ([summary_out] if summary_out else [])
    if len({path.resolve() for path in destinations}) != len(destinations):
        raise ProposalError("DOCX and summary destinations must differ")
    for destination in destinations:
        if destination.exists() or destination.is_symlink():
            raise ProposalError(f"Refusing to overwrite existing output: {destination}")
        if not destination.parent.is_dir():
            raise ProposalError(f"Output parent directory does not exist: {destination.parent}")
    document = build_document(data, totals)
    created = []
    try:
        with out.open("xb") as handle:
            created.append(out)
            document.save(handle)
        if summary_out:
            with summary_out.open("x", encoding="utf-8") as handle:
                created.append(summary_out)
                json.dump(summary_data(data, totals), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
    except (OSError, ValueError) as exc:
        for destination in created:
            destination.unlink(missing_ok=True)
        raise ProposalError(f"Cannot write outputs: {exc}") from exc
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Proposal JSON")
    parser.add_argument("--out", type=Path, help="New DOCX output path")
    parser.add_argument("--summary-out", type=Path, help="Optional new calculation-summary JSON path")
    parser.add_argument("--validate-only", action="store_true", help="Validate and print totals without writing files")
    args = parser.parse_args(argv)
    if not args.validate_only and not args.out:
        parser.error("--out is required unless --validate-only is used")
    try:
        data = load_proposal(args.input)
        totals = validate_proposal(data)
        if not args.validate_only:
            for destination in (args.out, args.summary_out):
                if destination and destination.resolve() == args.input.resolve():
                    raise ProposalError("Output must differ from input JSON")
            write_outputs(data, args.out, args.summary_out)
        print(json.dumps(summary_data(data, totals), ensure_ascii=False, indent=2))
    except ProposalError as exc:
        print(f"Invalid proposal: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
