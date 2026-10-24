# Client ready proposal document

The proposal must stand alone. Lead with the project, deliverable, price and timeline, then scope and milestones. Place necessary assumptions and terms after the core offer.

## Content and design

Carry explicit user and applicable client requirements. Include scope, days, price/tax treatment, milestone outcomes and payment, schedule, acceptance, dependencies, exclusions, options, support, third-party costs, ownership and start conditions when relevant. The document archetype does not authorize new terms or product scope.

Use concise client language and concrete outcomes. Keep engineering debates and source dumps internal. Remove agent instructions and approval notes from client copy. If terms remain unapproved, label the artifact "Draft proposal" or "טיוטת הצעת מחיר" and tell the user what is still proposed. Do not invent savings, guarantees, experience or agreement. Write client copy the way you would say it to the client.

Follow the chosen format and template. Reuse Google Docs when it is the established editable deliverable; provide PDF when requested or useful for the requested handoff. Preserve meaningful native-template structure.

Use readable fonts, black titles/headings and restrained whitespace. Show milestones with dates and visible outcomes, and use a table for the payment schedule; per-milestone prices and workdays stay out of client copy (see `defaults.md`). Prose for explanation. Hebrew titles, paragraphs, lists and tables must be RTL and right aligned. Write ranges as "בין 6 ל־8 שבועות" when digit ranges reverse. Inspect product names and currency visually. Avoid unnecessary covers, dense repetition, split rows and giant gaps.

## Render and native verification

The helper is a reusable authoring resource requested with this skill. Retain its source with the skill; keep client inputs/outputs in the case workspace. It does not replace Documents artifact marking, title sanitizing, rendering or visual review.

Author, sanitize Google Docs titles when that route is used, and render. Inspect pages individually, repair layout and rerun affected checks. Use explicit direction-relative start alignment: OOXML `w:bidi=1` with `w:jc=start`, and Google Docs `RIGHT_TO_LEFT` with `START`, which is right aligned. Apply this to titles, body text, table cells and footer paragraphs. Verify native table cells after import; do not leave centered cells when the user asks for everything right aligned. Complex-script font settings are required; flags alone are not visual proof.

For new Google Docs without a constraining native template, use the supported DOCX import route and verify content, arithmetic and RTL. For existing documents, use their trusted-read/native-edit workflow and preserve controls. Respect mandatory chip requirements of the selected document skill. Never invent API syntax or bypass connector checks through UI automation.

## Revisions and handoff

Update every total, milestone and schedule after changing days or scope. Keep approved answers and originals. Identify superseded drafts and return one current proposal. Deliver final requested artifacts, not generator files or QA images.

Verify that the document exists through a usable link/file. Creation, recipient sharing and sending are separate actions with separate authorization.
