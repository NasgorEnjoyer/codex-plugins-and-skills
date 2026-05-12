#!/usr/bin/env python3
"""Compare two DOCX packages and fail on unintended embedded-media drift."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from docx_media_inventory import build_inventory


def index_by_name(items: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(item["name"]): item for item in items}


def compare_named_records(
    before: dict[str, dict[str, object]],
    after: dict[str, dict[str, object]],
) -> dict[str, object]:
    before_names = set(before)
    after_names = set(after)
    changed = []
    for name in sorted(before_names & after_names):
        if before[name].get("sha256") != after[name].get("sha256"):
            changed.append({
                "name": name,
                "before_sha256": before[name].get("sha256"),
                "after_sha256": after[name].get("sha256"),
                "before_size": before[name].get("size"),
                "after_size": after[name].get("size"),
            })
    return {
        "added": sorted(after_names - before_names),
        "removed": sorted(before_names - after_names),
        "changed": changed,
    }


def compare_relationship_targets(before_inventory: dict[str, object], after_inventory: dict[str, object]) -> dict[str, object]:
    def key(rel: dict[str, object]) -> tuple[str, str, str]:
        return (
            str(rel.get("source_part", "")),
            str(rel.get("id", "")),
            str(rel.get("resolved_target", "")),
        )

    before = {key(rel) for rel in before_inventory.get("image_relationships", [])}
    after = {key(rel) for rel in after_inventory.get("image_relationships", [])}
    return {
        "added": [list(item) for item in sorted(after - before)],
        "removed": [list(item) for item in sorted(before - after)],
    }


def compare_docx(before_path: Path, after_path: Path) -> dict[str, object]:
    before_inventory = build_inventory(before_path)
    after_inventory = build_inventory(after_path)

    before_parts = index_by_name(before_inventory["parts"])  # type: ignore[arg-type]
    after_parts = index_by_name(after_inventory["parts"])  # type: ignore[arg-type]
    before_media = index_by_name(before_inventory["media"])  # type: ignore[arg-type]
    after_media = index_by_name(after_inventory["media"])  # type: ignore[arg-type]

    return {
        "before": str(before_path),
        "after": str(after_path),
        "package_parts": compare_named_records(before_parts, after_parts),
        "media": compare_named_records(before_media, after_media),
        "image_relationship_targets": compare_relationship_targets(before_inventory, after_inventory),
        "before_media_count": before_inventory["media_count"],
        "after_media_count": after_inventory["media_count"],
    }


def has_media_drift(report: dict[str, object]) -> bool:
    media = report["media"]
    rels = report["image_relationship_targets"]
    return bool(
        media["added"]  # type: ignore[index]
        or media["removed"]  # type: ignore[index]
        or media["changed"]  # type: ignore[index]
        or rels["added"]  # type: ignore[index]
        or rels["removed"]  # type: ignore[index]
    )


def print_text_report(report: dict[str, object]) -> None:
    print(f"before: {report['before']}")
    print(f"after:  {report['after']}")
    print(f"media count: {report['before_media_count']} -> {report['after_media_count']}")

    for section in ("media", "image_relationship_targets", "package_parts"):
        data = report[section]
        print(f"\n{section}:")
        for key in ("added", "removed", "changed"):
            if key not in data:  # type: ignore[operator]
                continue
            value = data[key]  # type: ignore[index]
            count = len(value)
            print(f"  {key}: {count}")
            for item in value[:20]:
                if isinstance(item, dict):
                    print(f"    - {item.get('name', item)}")
                else:
                    print(f"    - {item}")
            if count > 20:
                print(f"    ... {count - 20} more")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path, help="Original DOCX")
    parser.add_argument("after", type=Path, help="Edited DOCX")
    parser.add_argument("--allow-media-change", action="store_true", help="Return success even if embedded media changed")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text")
    args = parser.parse_args()

    try:
        report = compare_docx(args.before, args.after)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text_report(report)

    if has_media_drift(report) and not args.allow_media_change:
        print("\nerror: embedded media or image relationships changed", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
