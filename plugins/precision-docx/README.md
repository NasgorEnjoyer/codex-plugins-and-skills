# Precision DOCX

Precision DOCX is a Codex plugin for work on `.docx` files where text, layout,
relationships, and embedded images all matter. It provides one skill plus helper
scripts for OpenXML package inspection, image hashing, round-trip checks, and
render-based QA when LibreOffice is available.

## Contents

- `.codex-plugin/plugin.json`: plugin manifest.
- `skills/precision-docx/SKILL.md`: Codex workflow instructions.
- `scripts/docx_media_inventory.py`: extracts package, relationship, and media metadata.
- `scripts/docx_roundtrip_check.py`: compares original and edited DOCX packages.
- `scripts/render_docx.py`: converts DOCX to PDF and optional PNG page previews.

## Typical Use

```powershell
python .\scripts\docx_media_inventory.py .\input.docx --output .\input.inventory.json
python .\scripts\docx_roundtrip_check.py .\input.docx .\edited.docx
python .\scripts\render_docx.py .\edited.docx --output-dir .\rendered
```

The scripts use only Python standard library features except PNG rendering in
`render_docx.py`, which optionally uses PyMuPDF when installed.
