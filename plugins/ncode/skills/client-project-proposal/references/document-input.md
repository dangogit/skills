# Proposal document input

The helper validates explicit proposal data and creates a Hebrew RTL DOCX. It does not infer a price, contact clients, fetch sources, render a PDF, or install dependencies. It needs a Python with `python-docx` (`python3 -m pip install python-docx`). If that is unavailable, keep the validated JSON and report the limitation.

## Commands

From the skill directory:

```sh
python3 -B scripts/proposal_document.py /absolute/path/proposal.json --validate-only
python3 -B scripts/proposal_document.py /absolute/path/proposal.json --out /absolute/path/proposal.docx --summary-out /absolute/path/totals.json
python3 -B -m unittest discover -s scripts/tests -v
```

`--validate-only` prints the calculation summary and writes nothing, even when output flags are present. `--out` is required otherwise. `--summary-out` is optional. Output parent directories must already exist. Existing files, symlinks, identical output destinations, and output paths matching the input file are rejected. Invalid input exits with status 2. Unknown schema fields and duplicate JSON keys are rejected so data is not silently ignored.

## Required fields

| Field | Type and meaning |
|---|---|
| `title` | Nonempty client-facing document title. |
| `client` | Nonempty client name, as text. |
| `summary` | Nonempty explanation of the problem and proposed outcome. |
| `status` | `draft` or `proposal`. Drafts receive the visible label `טיוטה לבדיקה`. |
| `timeline` | Nonempty client-facing calendar estimate and start conditions. It is not calculated from workdays. |
| `tax_note` | Nonempty explicit tax wording. No tax percentage is inferred. |
| `currency` | Nonempty currency label; `ILS`, `USD`, and `EUR` display their symbols. Other labels display verbatim. |
| `pricing` | One of the two explicit pricing objects below. |
| `scope` | Nonempty array of nonempty client-facing scope paragraphs. |
| `milestones` | Nonempty array of milestone objects. |

Daily pricing:

```json
{"mode": "daily", "rate": "1200", "expected_total": "14400"}
```

Fixed pricing:

```json
{"mode": "fixed", "amount": "14400", "expected_total": "14400"}
```

`expected_total` is optional, but if supplied it must equal the derived daily total or explicit fixed amount. Daily pricing cannot also specify `amount`; fixed pricing cannot specify `rate`. Rate and fixed amount must be positive. Monetary values may have at most two effective fractional digits. Strings are recommended for decimal inputs; JSON decimal numbers are also parsed as Decimal. Booleans, negative values and nonfinite numbers are rejected. Numbers support at most 30 digits and an exponent between -12 and 12.

## Milestones and reserve

Each milestone has these fields:

| Field | Type and meaning |
|---|---|
| `title` | Required nonempty text. |
| `days` | Required positive decimal workdays. Includes any reserve allocated to this row. |
| `deliverable` | Required nonempty text describing a concrete result. |
| `timing` | Optional nonempty text for approximate delivery timing. |
| `reserve_days` | Optional nonnegative reserve included within this delivery row; must be strictly less than `days`. |
| `is_reserve` | Optional boolean retained for input compatibility. Only `false` is accepted; `true` is rejected. |

Optional top-level `reserve_days` must equal the sum of reserve included in the rows. If omitted, the row sum is used. The total is always the sum of milestone `days`; reserve is never added a second time.

Reserve alone is not a customer delivery milestone. Include it within a row with actual delivery work and a concrete result. Whole reserve rows are rejected whether marked with `is_reserve: true` or represented by `reserve_days == days`.

In daily pricing, each milestone amount equals `days × rate`, and the table shows these amounts plus their total. Embedded reserve is already priced within its milestone. Both row amounts and total must fit the monetary precision requirement; fractional cents are rejected, not silently rounded. In fixed pricing, the table omits milestone amounts because no payment allocation has been supplied or validated. Use explicit approved payment wording in `terms`; the helper does not invent fixed-price allocations.

## Optional narrative fields

`assumptions`, `excluded`, `acceptance`, `third_party`, and `maintenance` are arrays of nonempty strings. Empty arrays are allowed and suppress that section. `author` is an optional nonempty string for the footer and document metadata.

`terms` is an optional array of objects with required nonempty `heading` and `text` strings. Approved commercial terms can appear in a proposal. Proposed terms can appear in a document with `status: draft` when their wording clearly labels them as proposed; retain their source and approval state in the internal evidence ledger. The renderer does not verify approval or invent business policy. Do not present terms copied from another client as approved for this client.

`options` is an optional array of objects:

| Field | Type and meaning |
|---|---|
| `title` | Required nonempty text. |
| `description` | Required nonempty text. |
| `days` | Optional positive decimal workdays. |
| `amount` | Optional nonnegative explicit money amount. It is not calculated from days. |
| `note` | Optional nonempty text, for assumptions and separate pricing conditions. |

Optional items never contribute days or money to the base total. An option without an amount remains unpriced. Client-facing wording is preserved from the supplied JSON; the helper adds standard section labels and financial totals only.

## Output and verification

The JSON summary contains status, currency, pricing mode, total/base/reserve workdays, base amount, option count and `options_included_in_amount: false`. Daily pricing also includes `milestone_amounts` with each title, days and amount. Decimal values are serialized as strings.

The validator checks structured numeric fields, not monetary claims inside narrative text. Before delivery, manually compare every price, day count, reserve statement, installment, option, tax statement, supplier budget and maintenance amount in prose against the validated calculation summary and evidence ledger. A valid JSON does not prove narrative totals or commercial approvals are correct.

The DOCX uses Arial, black headings and title, real Heading 1 styles, paragraph RTL with start alignment, and a visual RTL table with explicit grid and cell widths. Price and timeline appear early. It does not force a page count or insert decorative title rules. Rendering and visual inspection remain mandatory before delivery: verify each page, numerical ordering, table widths, wrapping, whitespace, footer and no clipped text. Use the Documents skill for sanitization, rendering and PDF export; use the Google Docs skill when an editable Google document is requested. Follow its supported import path and verify the native readback.

`assets/proposal-example.json` contains a fictional client and illustrative commercial values. Copy its structure, not its price or assumptions.
