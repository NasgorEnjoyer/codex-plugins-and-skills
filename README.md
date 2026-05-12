# Codex Plugins and Skills

This repository is a Codex plugin marketplace. It currently publishes:

- `precision-docx`: high-fidelity DOCX reading and writing workflows with
  embedded-image inventory, package checks, and visual QA helpers.

## Install Marketplace

Add this repository as a Codex marketplace source:

```bash
codex plugin marketplace add NasgorEnjoyer/codex-plugins-and-skills
```

Then browse plugins in Codex and install `Precision DOCX`.

If Codex asks for a raw marketplace URL, use:

```text
https://raw.githubusercontent.com/NasgorEnjoyer/codex-plugins-and-skills/main/.agents/plugins/marketplace.json
```

## Privacy

Plugins in this repository run locally unless their individual documentation says
otherwise. `precision-docx` reads and writes local DOCX files and does not send
document contents to any external service by itself.

## Terms

Plugins are provided as-is under the repository license. Review plugin scripts
before using them on sensitive documents.
