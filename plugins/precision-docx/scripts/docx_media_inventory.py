#!/usr/bin/env python3
"""Inventory a DOCX package with special attention to embedded images."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import struct
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "v": "urn:schemas-microsoft-com:vml",
}

IMAGE_REL_TYPES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
    "http://purl.oclc.org/ooxml/officeDocument/relationships/image",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_content_types(zf: zipfile.ZipFile) -> tuple[dict[str, str], dict[str, str]]:
    defaults: dict[str, str] = {}
    overrides: dict[str, str] = {}
    try:
        root = ET.fromstring(zf.read("[Content_Types].xml"))
    except KeyError:
        return defaults, overrides

    for child in root:
        tag = strip_ns(child.tag)
        if tag == "Default":
            ext = child.attrib.get("Extension")
            ctype = child.attrib.get("ContentType")
            if ext and ctype:
                defaults[ext.lower()] = ctype
        elif tag == "Override":
            part = child.attrib.get("PartName")
            ctype = child.attrib.get("ContentType")
            if part and ctype:
                overrides[part.lstrip("/")] = ctype
    return defaults, overrides


def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def content_type_for(name: str, defaults: dict[str, str], overrides: dict[str, str]) -> str | None:
    if name in overrides:
        return overrides[name]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return defaults.get(ext)


def image_dimensions(data: bytes) -> dict[str, int] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return {"width": width, "height": height}
    if data.startswith((b"GIF87a", b"GIF89a")) and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return {"width": width, "height": height}
    if data.startswith(b"BM") and len(data) >= 26:
        width, height = struct.unpack("<ii", data[18:26])
        return {"width": abs(width), "height": abs(height)}
    if data.startswith(b"\xff\xd8"):
        dims = jpeg_dimensions(data)
        if dims:
            return dims
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        dims = webp_dimensions(data)
        if dims:
            return dims
    return None


def jpeg_dimensions(data: bytes) -> dict[str, int] | None:
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        while marker == 0xFF and index < len(data):
            marker = data[index]
            index += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            return None
        length = struct.unpack(">H", data[index:index + 2])[0]
        if length < 2 or index + length > len(data):
            return None
        if marker in {
            0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
        }:
            if length >= 7:
                height, width = struct.unpack(">HH", data[index + 3:index + 7])
                return {"width": width, "height": height}
        index += length
    return None


def webp_dimensions(data: bytes) -> dict[str, int] | None:
    if len(data) < 30:
        return None
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return {"width": width, "height": height}
    if chunk == b"VP8L" and len(data) >= 25:
        bits = int.from_bytes(data[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return {"width": width, "height": height}
    if chunk == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return {"width": width, "height": height}
    return None


def relationship_source_part(rels_name: str) -> str:
    if rels_name == "_rels/.rels":
        return ""
    folder, filename = posixpath.split(rels_name)
    if not folder.endswith("_rels"):
        return ""
    parent = posixpath.dirname(folder)
    source_name = filename.removesuffix(".rels")
    return posixpath.normpath(posixpath.join(parent, source_name)).lstrip("./")


def resolve_relationship_target(source_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    base = posixpath.dirname(source_part)
    return posixpath.normpath(posixpath.join(base, target)).lstrip("./")


def parse_relationships(zf: zipfile.ZipFile) -> tuple[list[dict[str, str]], dict[str, dict[str, dict[str, str]]]]:
    relationships: list[dict[str, str]] = []
    by_source: dict[str, dict[str, dict[str, str]]] = {}
    for name in sorted(n for n in zf.namelist() if n.endswith(".rels")):
        try:
            root = ET.fromstring(zf.read(name))
        except ET.ParseError:
            continue
        source = relationship_source_part(name)
        by_source.setdefault(source, {})
        for rel in root.findall("rel:Relationship", NS):
            rid = rel.attrib.get("Id", "")
            rtype = rel.attrib.get("Type", "")
            target = rel.attrib.get("Target", "")
            mode = rel.attrib.get("TargetMode", "Internal")
            resolved = target if mode == "External" else resolve_relationship_target(source, target)
            item = {
                "rels_part": name,
                "source_part": source,
                "id": rid,
                "type": rtype,
                "target": target,
                "target_mode": mode,
                "resolved_target": resolved,
            }
            relationships.append(item)
            if rid:
                by_source[source][rid] = item
    return relationships, by_source


def drawing_usages(zf: zipfile.ZipFile, relationships_by_source: dict[str, dict[str, dict[str, str]]]) -> list[dict[str, object]]:
    usages: list[dict[str, object]] = []
    xml_names = sorted(
        name for name in zf.namelist()
        if name.startswith("word/") and name.endswith(".xml")
    )
    for part in xml_names:
        try:
            root = ET.fromstring(zf.read(part))
        except ET.ParseError:
            continue
        rels = relationships_by_source.get(part, {})
        for drawing_type in ("inline", "anchor"):
            for node in root.findall(f".//wp:{drawing_type}", NS):
                extent = node.find("wp:extent", NS)
                doc_pr = node.find("wp:docPr", NS)
                src_rect = node.find(".//a:srcRect", NS)
                for blip in node.findall(".//a:blip", NS):
                    rid = blip.attrib.get(f"{{{NS['r']}}}embed") or blip.attrib.get(f"{{{NS['r']}}}link")
                    rel = rels.get(rid or "", {})
                    usages.append({
                        "part": part,
                        "drawing_type": drawing_type,
                        "relationship_id": rid,
                        "target": rel.get("resolved_target"),
                        "extent_emu": extent.attrib if extent is not None else {},
                        "doc_properties": doc_pr.attrib if doc_pr is not None else {},
                        "crop": src_rect.attrib if src_rect is not None else {},
                    })
        for image_data in root.findall(".//v:imagedata", NS):
            rid = image_data.attrib.get(f"{{{NS['r']}}}id")
            rel = rels.get(rid or "", {})
            usages.append({
                "part": part,
                "drawing_type": "vml",
                "relationship_id": rid,
                "target": rel.get("resolved_target"),
                "extent_emu": {},
                "doc_properties": {},
                "crop": {},
            })
    return usages


def build_inventory(path: Path) -> dict[str, object]:
    if not zipfile.is_zipfile(path):
        raise ValueError(f"{path} is not a valid DOCX/ZIP package")

    with zipfile.ZipFile(path) as zf:
        defaults, overrides = read_content_types(zf)
        relationships, by_source = parse_relationships(zf)
        parts = []
        media = []

        for info in sorted(zf.infolist(), key=lambda item: item.filename):
            if info.is_dir():
                continue
            data = zf.read(info.filename)
            content_type = content_type_for(info.filename, defaults, overrides)
            part_record = {
                "name": info.filename,
                "size": info.file_size,
                "compressed_size": info.compress_size,
                "crc": f"{info.CRC:08x}",
                "sha256": sha256_bytes(data),
                "content_type": content_type,
            }
            parts.append(part_record)
            if info.filename.startswith("word/media/") or (content_type or "").startswith("image/"):
                media.append({
                    **part_record,
                    "dimensions": image_dimensions(data),
                })

        image_rels = [
            rel for rel in relationships
            if rel["type"] in IMAGE_REL_TYPES or rel["resolved_target"].startswith("word/media/")
        ]

        return {
            "docx": str(path),
            "package_part_count": len(parts),
            "media_count": len(media),
            "parts": parts,
            "media": media,
            "image_relationships": image_rels,
            "image_usages": drawing_usages(zf, by_source),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx", type=Path, help="DOCX file to inspect")
    parser.add_argument("--output", "-o", type=Path, help="Write inventory JSON to this path")
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args()

    try:
        inventory = build_inventory(args.docx)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(inventory, indent=args.indent, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
