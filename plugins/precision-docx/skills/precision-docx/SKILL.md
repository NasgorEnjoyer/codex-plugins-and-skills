---
name: precision-docx
description: Use when reading, editing, generating, auditing, or comparing DOCX files where exact layout, embedded images, image relationships, page rendering, headers, footers, or OpenXML package fidelity matter.
---

# Precision DOCX

Use this skill whenever a `.docx` task requires high fidelity. Trigger examples
include requests that mention exact formatting, images, screenshots, layout,
rendering, headers/footers, page breaks, comments, tracked changes, charts,
shapes, or preserving the original file structure.

## Core Rules

- Treat a DOCX as an OPC ZIP package, not just a text document.
- Inventory the original package before changing anything.
- Preserve unrelated ZIP parts byte-for-byte whenever possible.
- Do not rely on `python-docx` for high-fidelity round trips unless the user has
  accepted layout/image risk. It can normalize or omit unsupported Word features.
- Make targeted OpenXML edits in the specific XML part that owns the content.
- Preserve all `word/media/*` bytes unless the user explicitly asks to replace
  an image.
- Preserve relationship IDs, content types, section properties, drawing extents,
  anchors, wrapping, crop rectangles, alt text, and header/footer links unless
  the requested edit requires changing them.
- Verify after writing: compare package/media hashes and render pages when a
  renderer is available.

## Standard Workflow

1. Locate the plugin root and use scripts from `scripts/`.
2. Run an inventory on the source DOCX:

   ```bash
   python scripts/docx_media_inventory.py input.docx --output input.inventory.json
   ```

3. Inspect the relevant XML parts directly:
   - `word/document.xml`
   - `word/_rels/document.xml.rels`
   - `word/header*.xml`, `word/footer*.xml`
   - `word/styles.xml`
   - `word/numbering.xml`
   - `word/comments*.xml`
   - `word/footnotes.xml`, `word/endnotes.xml`
4. Edit only the target XML nodes. When possible, unpack to a scratch folder,
   edit structured XML, then repackage while preserving untouched ZIP entries.
5. Run a round-trip check against the original:

   ```bash
   python scripts/docx_roundtrip_check.py original.docx edited.docx
   ```

6. Render and visually inspect the edited document:

   ```bash
   python scripts/render_docx.py edited.docx --output-dir rendered
   ```

7. Report any verification limits clearly, especially if Word or LibreOffice
   rendering was unavailable.

## Image-Specific Requirements

- Before editing, identify every embedded and linked image through `.rels` files
  and drawing references.
- Track each image by package path, relationship ID, SHA-256 hash, byte size,
  MIME type, pixel dimensions, and DrawingML extent in EMUs.
- If changing text near an image, confirm that its anchor/inline container,
  wrapping, crop, transform, and extent are unchanged unless intentionally edited.
- If replacing an image, preserve the original relationship target when possible
  and update `[Content_Types].xml` only when the extension or MIME type changes.
- Never flatten a DOCX to PDF or images as the final editable output unless the
  user explicitly asks for that.

## Writing Strategy

- Prefer XML-aware edits with `xml.etree.ElementTree`, `lxml`, or OpenXML SDK
  style tooling where available.
- Preserve namespace prefixes and relationship references as much as practical.
- For simple text replacement, operate inside `w:t` nodes and avoid rebuilding
  paragraphs unless required.
- For layout-sensitive changes, keep `w:sectPr`, `w:pgSz`, `w:pgMar`,
  `w:tabs`, `w:spacing`, `w:rPr`, `wp:inline`, and `wp:anchor` intact.
- If the document contains tracked changes, comments, fields, charts, SmartArt,
  equations, content controls, macros, or embedded OLE objects, call out the
  added risk and verify the related package parts.

## Completion Checklist

- Original inventory saved or summarized.
- Intended XML changes made with a narrow diff.
- `docx_roundtrip_check.py` passes, or intentional changes are explained.
- Embedded media hashes are unchanged unless image edits were requested.
- Rendered page previews or PDF were checked when tooling was available.
- Final answer names any verification steps that could not be run.
