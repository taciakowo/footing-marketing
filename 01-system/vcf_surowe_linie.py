#!/usr/bin/env python3
"""Zapisuje surowe linie z contacts.vcf dla kontaktów oznaczonych jako podejrzane."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "00-inbox"
OUT_PRIVATE = ROOT / "02-output-private"
VCF_PATH = INBOX / "contacts.vcf"
DIAG_PATH = OUT_PRIVATE / "DIAGNOSTYKA-VCF.csv"
OUTPUT_PATH = OUT_PRIVATE / "VCF-SUROWE-LINIE.txt"


def phone_search_patterns(phone: str) -> list[bytes]:
    digits = re.sub(r"\D", "", phone or "")
    patterns: list[str] = []
    if phone:
        patterns.append(phone)
    if digits:
        patterns.append(digits)
        if len(digits) == 11 and digits.startswith("48"):
            patterns.append("+" + digits)
        if len(digits) >= 9:
            patterns.append(digits[-9:])
            patterns.append(f"{digits[-3]}-{digits[-6:-3]}-{digits[-9:-6]}")
    unique: list[bytes] = []
    seen: set[bytes] = set()
    for p in patterns:
        for enc in ("utf-8", "ascii"):
            try:
                b = p.encode(enc)
            except UnicodeEncodeError:
                continue
            if b not in seen:
                seen.add(b)
                unique.append(b)
    return unique


def name_search_patterns(raw_name: str) -> list[bytes]:
    patterns: list[bytes] = []
    seen: set[bytes] = set()
    for enc in ("utf-8", "cp1250", "iso-8859-2", "latin-1"):
        try:
            b = raw_name.encode(enc)
        except UnicodeEncodeError:
            continue
        if b not in seen:
            seen.add(b)
            patterns.append(b)
    return patterns


def split_raw_lines(raw: bytes) -> list[bytes]:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").split(b"\n")


def line_to_raw_text(line: bytes) -> str:
    """Zwróć linię jako tekst bez dekodowania vCard – tylko odczyt bajtów pliku."""
    for enc in ("utf-8", "cp1250", "iso-8859-2"):
        try:
            return line.decode(enc)
        except UnicodeDecodeError:
            continue
    return line.decode("utf-8", errors="replace")


def line_matches(line: bytes, phone_patterns: list[bytes], name_patterns: list[bytes]) -> bool:
    for pattern in phone_patterns + name_patterns:
        if pattern and pattern in line:
            return True
    return False


def block_matches(block: list[bytes], phone_patterns: list[bytes], name_patterns: list[bytes]) -> bool:
    joined = b"\n".join(block)
    for pattern in phone_patterns + name_patterns:
        if pattern and pattern in joined:
            return True
    return False


def extract_vcard_blocks(lines: list[bytes]) -> list[list[bytes]]:
    blocks: list[list[bytes]] = []
    current: list[bytes] = []
    for line in lines:
        if line.strip().upper() == b"BEGIN:VCARD":
            current = [line]
            continue
        if not current:
            continue
        current.append(line)
        if line.strip().upper() == b"END:VCARD":
            blocks.append(current)
            current = []
    return blocks


def find_raw_sections(raw: bytes, phone: str, raw_name: str) -> list[list[bytes]]:
    lines = split_raw_lines(raw)
    phone_patterns = phone_search_patterns(phone)
    name_patterns = name_search_patterns(raw_name)

    if any(line.strip().upper() == b"BEGIN:VCARD" for line in lines):
        return [
            block for block in extract_vcard_blocks(lines)
            if block_matches(block, phone_patterns, name_patterns)
        ]

    matched = [line for line in lines if line_matches(line, phone_patterns, name_patterns)]
    return [matched] if matched else []


def load_suspicious_rows() -> list[dict[str, str]]:
    if not DIAG_PATH.exists():
        print(f"Brak pliku diagnostycznego: {DIAG_PATH}")
        print("Uruchom najpierw: python 01-system/update_footing_database.py")
        return []
    with DIAG_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return [row for row in rows if row.get("czy_podejrzana", "").strip().lower() == "tak"]


def write_suspicious_vcf_raw_lines() -> Path:
    suspicious = load_suspicious_rows()
    OUT_PRIVATE.mkdir(parents=True, exist_ok=True)

    if not VCF_PATH.exists():
        OUTPUT_PATH.write_text(f"Brak pliku: {VCF_PATH}\n", encoding="utf-8")
        return OUTPUT_PATH

    raw = VCF_PATH.read_bytes()
    parts: list[str] = [
        "# Surowe linie z contacts.vcf dla kontaktów podejrzanych",
        "# Bez dekodowania vCard – dokładna treść linii z pliku źródłowego",
        f"# Źródło: {VCF_PATH}",
        f"# Diagnostyka: {DIAG_PATH}",
        "",
    ]

    if not suspicious:
        parts.append("Brak kontaktów oznaczonych jako podejrzane.")
    else:
        for idx, row in enumerate(suspicious, start=1):
            phone = row.get("telefon", "")
            raw_name = row.get("nazwa_surowa", "")
            sections = find_raw_sections(raw, phone, raw_name)

            parts.append("=" * 72)
            parts.append(f"# Kontakt {idx}")
            parts.append(f"# telefon: {phone}")
            parts.append(f"# nazwa_surowa: {raw_name}")
            parts.append("=" * 72)

            if not sections:
                parts.append("[Nie znaleziono pasujących surowych linii w pliku VCF]")
            else:
                for section in sections:
                    for line in section:
                        parts.append(line_to_raw_text(line))
                    parts.append("")

    OUTPUT_PATH.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return OUTPUT_PATH


def main() -> int:
    path = write_suspicious_vcf_raw_lines()
    suspicious = load_suspicious_rows()
    print(f"VCF surowe linie: {len(suspicious)} podejrzanych -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
