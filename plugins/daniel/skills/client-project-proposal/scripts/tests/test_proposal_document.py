"""Financial and artifact contract tests using synthetic proposal data."""
import contextlib
from copy import deepcopy
from decimal import Decimal
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET


SCRIPT = Path(__file__).resolve().parents[1] / "proposal_document.py"
spec = importlib.util.spec_from_file_location("proposal_document", SCRIPT)
proposal = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = proposal
spec.loader.exec_module(proposal)
EXAMPLE = SCRIPT.parent.parent / "assets" / "proposal-example.json"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


class ProposalDocumentTests(unittest.TestCase):
    def setUp(self):
        self.data = proposal.load_proposal(EXAMPLE)

    def test_daily_total_and_embedded_reserve(self):
        totals = proposal.validate_proposal(self.data)
        self.assertEqual(totals.total_days, Decimal("12"))
        self.assertEqual(totals.reserve_days, Decimal("2"))
        self.assertEqual(totals.base_days, Decimal("10"))
        self.assertEqual(totals.amount, Decimal("14400"))
        amounts = proposal.summary_data(self.data, totals)["milestone_amounts"]
        self.assertEqual([row["amount"] for row in amounts], ["2400", "6000", "6000"])
        self.assertEqual(sum(Decimal(row["amount"]) for row in amounts), totals.amount)

    def test_whole_reserve_row_rejected(self):
        self.data["milestones"][2]["reserve_days"] = 5
        self.data["milestones"][2]["is_reserve"] = True
        self.data["reserve_days"] = 5
        with self.assertRaisesRegex(proposal.ProposalError, "reserve-only rows"):
            proposal.validate_proposal(self.data)
        self.data["milestones"][2]["is_reserve"] = False
        with self.assertRaisesRegex(proposal.ProposalError, "reserve-only rows"):
            proposal.validate_proposal(self.data)
        self.data["milestones"][2]["reserve_days"] = 2
        self.data["reserve_days"] = 2
        self.assertEqual(proposal.validate_proposal(self.data).amount, Decimal("14400"))

    def test_options_excluded_from_base_price(self):
        self.data["options"][0]["amount"] = "999999.99"
        self.data["options"][0]["days"] = 200
        totals = proposal.validate_proposal(self.data)
        self.assertEqual(totals.amount, Decimal("14400"))
        self.assertFalse(proposal.summary_data(self.data, totals)["options_included_in_amount"])

    def test_fixed_price_explicit_and_independent_of_days(self):
        self.data["pricing"] = {"mode": "fixed", "amount": "17000.50", "expected_total": "17000.50"}
        self.assertEqual(proposal.validate_proposal(self.data).amount, Decimal("17000.50"))
        self.assertNotIn("milestone_amounts", proposal.summary_data(self.data, proposal.validate_proposal(self.data)))
        document = proposal.build_document(self.data)
        headers = [cell.text for cell in document.tables[0].rows[0].cells]
        self.assertEqual(headers, ["אבן דרך", "ימי עבודה", "מועד משוער", "תוצר למסירה"])
        self.assertNotIn("סכום", headers)

    def test_subcent_row_amount_rejected_even_if_aggregate_is_valid(self):
        self.data["pricing"] = {"mode": "daily", "rate": "1", "expected_total": "0.01"}
        self.data["reserve_days"] = 0
        self.data["milestones"] = [
            {"title": "א", "days": "0.005", "deliverable": "תוצר"},
            {"title": "ב", "days": "0.005", "deliverable": "תוצר"}
        ]
        with self.assertRaisesRegex(proposal.ProposalError, "computed amount"):
            proposal.validate_proposal(self.data)

    def test_decimal_calculation_has_no_float_error(self):
        self.data["pricing"] = {"mode": "daily", "rate": "10.10", "expected_total": "1.01"}
        self.data["milestones"] = [{"title": "דוגמה", "days": "0.1", "deliverable": "תוצר"}]
        self.data["reserve_days"] = 0
        self.assertEqual(proposal.validate_proposal(self.data).amount, Decimal("1.010"))

    def test_mismatched_and_double_counted_totals_rejected(self):
        for wrong_total in ("14401", "16800"):
            with self.subTest(total=wrong_total):
                self.data["pricing"]["expected_total"] = wrong_total
                with self.assertRaisesRegex(proposal.ProposalError, "does not match"):
                    proposal.validate_proposal(self.data)

    def test_reserve_must_be_included_in_rows(self):
        self.data["reserve_days"] = 3
        with self.assertRaisesRegex(proposal.ProposalError, "reserve included in milestone"):
            proposal.validate_proposal(self.data)
        self.data["reserve_days"] = 6
        self.data["milestones"][2]["reserve_days"] = 6
        with self.assertRaisesRegex(proposal.ProposalError, "cannot exceed"):
            proposal.validate_proposal(self.data)

    def test_malformed_numeric_inputs_rejected(self):
        for value in (True, False, -1, "NaN", "Infinity", float("inf"), "bad", [], None, "1e999"):
            with self.subTest(value=value):
                data = deepcopy(self.data)
                data["pricing"]["rate"] = value
                with self.assertRaises(proposal.ProposalError):
                    proposal.validate_proposal(data)
        for value in (0, True, -1, "NaN"):
            with self.subTest(days=value):
                data = deepcopy(self.data)
                data["milestones"][0]["days"] = value
                with self.assertRaises(proposal.ProposalError):
                    proposal.validate_proposal(data)

    def test_money_precision_and_ambiguous_pricing_rejected(self):
        self.data["pricing"]["rate"] = "10.001"
        with self.assertRaisesRegex(proposal.ProposalError, "two fractional"):
            proposal.validate_proposal(self.data)
        self.data["pricing"] = {"mode": "fixed", "amount": 10, "rate": 10}
        with self.assertRaisesRegex(proposal.ProposalError, "not rate"):
            proposal.validate_proposal(self.data)

    def test_required_fields_and_unknown_fields(self):
        for key in ("title", "client", "scope", "pricing", "milestones"):
            data = deepcopy(self.data)
            del data[key]
            with self.subTest(key=key), self.assertRaises(proposal.ProposalError):
                proposal.validate_proposal(data)
        self.data["hidden_markup"] = "unexpected"
        with self.assertRaisesRegex(proposal.ProposalError, "unknown fields"):
            proposal.validate_proposal(self.data)

    def test_invalid_xml_text_rejected_before_writing(self):
        for text in ("bad\x00", "bad\ud800", "bad\ufffe"):
            data = deepcopy(self.data)
            data["summary"] = text
            with self.subTest(text=repr(text)), self.assertRaisesRegex(proposal.ProposalError, "XML character"):
                proposal.validate_proposal(data)

    def test_json_nonfinite_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for text in ('{"rate": NaN}', '{"rate": 1, "rate": 2}'):
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(proposal.ProposalError):
                    proposal.load_proposal(path)

    def test_validate_only_creates_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "test.docx"
            summary = Path(directory) / "summary.json"
            with contextlib.redirect_stdout(io.StringIO()):
                status = proposal.main([str(EXAMPLE), "--validate-only", "--out", str(out), "--summary-out", str(summary)])
            self.assertEqual(status, 0)
            self.assertFalse(out.exists())
            self.assertFalse(summary.exists())

    def test_existing_output_and_summary_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "test.docx"
            summary = Path(directory) / "summary.json"
            out.write_bytes(b"original")
            with self.assertRaisesRegex(proposal.ProposalError, "overwrite"):
                proposal.write_outputs(self.data, out)
            self.assertEqual(out.read_bytes(), b"original")
            out.unlink()
            summary.write_text("original", encoding="utf-8")
            with self.assertRaisesRegex(proposal.ProposalError, "overwrite"):
                proposal.write_outputs(self.data, out, summary)
            self.assertFalse(out.exists())
            self.assertEqual(summary.read_text(), "original")

    def test_invalid_data_never_writes_artifact(self):
        self.data["pricing"]["expected_total"] = "1"
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "test.docx"
            with self.assertRaises(proposal.ProposalError):
                proposal.write_outputs(self.data, out)
            self.assertFalse(out.exists())

    def test_docx_direction_styles_table_and_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "test.docx"
            summary = Path(directory) / "summary.json"
            proposal.write_outputs(self.data, out, summary)
            self.assertEqual(json.loads(summary.read_text())["amount"], "14400")
            with ZipFile(out) as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
                styles = ET.fromstring(archive.read("word/styles.xml"))
            self.assertTrue(root.findall(".//w:pStyle[@w:val='Heading1']", NS))
            self.assertTrue(styles.findall(".//w:style[@w:styleId='Heading1']", NS))
            self.assertIsNone(styles.find(".//w:style[@w:styleId='Title']/w:pPr/w:pBdr", NS))
            paragraphs = root.findall(".//w:p", NS)
            for paragraph in paragraphs:
                self.assertIsNotNone(paragraph.find("w:pPr/w:bidi[@w:val='1']", NS))
                self.assertIsNotNone(paragraph.find("w:pPr/w:jc[@w:val='start']", NS))
            self.assertIsNotNone(root.find(".//w:tblPr/w:bidiVisual[@w:val='1']", NS))
            self.assertIsNotNone(root.find(".//w:trPr/w:tblHeader", NS))
            self.assertIsNotNone(root.find(".//w:tblBorders/w:insideH", NS))
            grid_widths = [int(node.get(proposal.qn("w:w"))) for node in root.findall(".//w:tblGrid/w:gridCol", NS)]
            self.assertEqual(len(grid_widths), 5)
            self.assertLess(grid_widths[1], grid_widths[0])
            self.assertLess(grid_widths[2], grid_widths[-1])
            for row in root.findall(".//w:tbl/w:tr", NS):
                cell_widths = [int(node.get(proposal.qn("w:w"))) for node in row.findall("w:tc/w:tcPr/w:tcW", NS)]
                self.assertEqual(cell_widths, grid_widths)
            table_rows = root.findall(".//w:tbl/w:tr", NS)
            amounts = ["".join(row.findall("w:tc", NS)[2].itertext()) for row in table_rows[1:]]
            self.assertEqual(amounts, ["2,400 ₪", "6,000 ₪", "6,000 ₪", "14,400 ₪"])
            for fonts in root.findall(".//w:rFonts", NS):
                self.assertEqual(fonts.get(proposal.qn("w:cs")), "Arial")
                self.assertFalse(any("Theme" in key or "theme" in key for key in fonts.attrib))
            text = "".join(root.itertext())
            self.assertIn("14,400 ₪", text)
            self.assertIn(self.data["summary"], text)
            self.assertNotIn("Codex", text)
            for color in root.findall(".//w:rPr/w:color", NS):
                self.assertEqual(color.get(proposal.qn("w:val")), "000000")


if __name__ == "__main__":
    unittest.main()
