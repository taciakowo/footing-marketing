#!/usr/bin/env python3
"""Quick Order – zapis zdarzenia do Footing System (bez zapisu do Google Contacts)."""

from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from footing_buffer import LIMIT_TYTUL, limit_field, prepare_buffer_fields, quick_order_content_hash  # noqa: E402
from footing_csv import append_csv_rows, normalize_text  # noqa: E402
from footing_order_core import (  # noqa: E402
    ItemsParseResult,
    build_tytul_sprawy,
    extract_skrot_nazwy,
    normalize_event_date,
    parse_items_text,
)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "02-output-private" / "quick-order"
EVENTS_PATH = OUT_DIR / "QUICK-ORDER-EVENTS.csv"
ACCEPT_PATH = OUT_DIR / "QUICK-ORDER-DO-AKCEPTACJI.csv"

EVENTS_COLS = [
    "event_id", "created_at", "data", "telefon", "items_text", "tytul_sprawy",
    "produkty", "ilosc_sztuk", "liczba_pozycji", "inwestycja", "nazwa_klienta",
    "status", "status_sprawdzenia", "uwagi", "zrodlo", "raw_json_path", "hash",
]
ACCEPT_COLS = [
    "status_bufora", "powod_bufora", "data", "tytul_sprawy", "telefon", "produkty",
    "ilosc_sztuk", "liczba_pozycji", "inwestycja", "status_sprawdzenia", "nazwa_klienta",
    "uwagi", "zrodlo", "event_id", "created_at", "raw_json_path", "hash",
]


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        return "+48" + digits
    if len(digits) == 11 and digits.startswith("48"):
        return "+" + digits
    return (raw or "").strip()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_event(data: dict) -> list[str]:
    errors: list[str] = []
    if not normalize_phone(data.get("phone", "")):
        errors.append("brak telefonu")
    if not (data.get("event_date") or data.get("data")):
        errors.append("brak daty")
    if not (data.get("items_text") or "").strip():
        errors.append("brak items_text")
    return errors


def load_existing_hashes(*paths: Path) -> set[str]:
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            if not reader.fieldnames or "hash" not in (reader.fieldnames or []):
                f.seek(0)
                reader = csv.DictReader(f)
            for row in reader:
                h = (row.get("hash") or "").strip()
                if h:
                    seen.add(h)
    return seen


def skrot_from_customer_name(name: str) -> str:
    name = normalize_text(name)
    if not name:
        return ""
    skrot = extract_skrot_nazwy(f"Klient {name}")
    if skrot:
        return skrot
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][:4].capitalize()}.{parts[1][:4].capitalize()}."
    return ""


def process_quick_order(json_path: Path) -> dict:
    payload = load_json(json_path)
    errors = validate_event(payload)
    phone = normalize_phone(payload.get("phone", ""))
    event_date = normalize_event_date(payload.get("event_date") or payload.get("data", ""))
    items_text = normalize_text(payload.get("items_text") or "")
    inwestycja = normalize_text(payload.get("inwestycja") or payload.get("investment") or "")
    nazwa_klienta = normalize_text(payload.get("customer_name_raw") or payload.get("nazwa_klienta") or "")
    notatka = normalize_text(payload.get("notatka") or payload.get("note") or "")
    zrodlo = normalize_text(payload.get("source") or payload.get("zrodlo") or "quick_order")

    parsed, _tytul_base, produkty_tekst, inwestycja, _skrot, _full, field_notes = prepare_buffer_fields(
        items_text, event_date, inwestycja,
    )
    skrot = skrot_from_customer_name(nazwa_klienta)
    tytul, trunc_t = limit_field(
        build_tytul_sprawy(event_date, parsed, inwestycja, skrot), LIMIT_TYTUL,
    )
    if trunc_t:
        field_notes.append("skrocono_opis_zrodlowy")

    uwagi: list[str] = list(parsed.uwagi)
    uwagi.extend(field_notes)
    if errors:
        uwagi.extend(errors)
    if notatka:
        uwagi.append(notatka)

    status = "do_akceptacji"
    status_sprawdzenia = parsed.status_sprawdzenia
    if errors:
        status_sprawdzenia = "blad_walidacji"

    h = quick_order_content_hash(
        telefon=phone,
        data=event_date,
        items_text=items_text,
        zrodlo=zrodlo,
        inwestycja=inwestycja,
        nazwa_klienta=nazwa_klienta,
    )
    existing = load_existing_hashes(EVENTS_PATH, ACCEPT_PATH)
    if h in existing:
        return {
            "skipped": True,
            "hash": h,
            "tytul_sprawy": tytul,
            "status_sprawdzenia": status_sprawdzenia,
            "errors": errors,
            "events_path": str(EVENTS_PATH),
            "accept_path": str(ACCEPT_PATH),
        }

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    event_id = f"QO-{h[:12]}"

    event_row = {
        "event_id": event_id,
        "created_at": now,
        "data": event_date,
        "telefon": phone,
        "items_text": items_text,
        "tytul_sprawy": tytul,
        "produkty": produkty_tekst,
        "ilosc_sztuk": parsed.ilosc_sztuk,
        "liczba_pozycji": parsed.liczba_pozycji,
        "inwestycja": inwestycja,
        "nazwa_klienta": nazwa_klienta,
        "status": status,
        "status_sprawdzenia": status_sprawdzenia,
        "uwagi": "; ".join(uwagi),
        "zrodlo": zrodlo,
        "raw_json_path": str(json_path),
        "hash": h,
    }

    accept_row = {
        "status_bufora": "do_akceptacji",
        "powod_bufora": "quick_order",
        "data": event_date,
        "tytul_sprawy": tytul,
        "telefon": phone,
        "produkty": produkty_tekst,
        "ilosc_sztuk": parsed.ilosc_sztuk,
        "liczba_pozycji": parsed.liczba_pozycji,
        "inwestycja": inwestycja,
        "status_sprawdzenia": status_sprawdzenia,
        "nazwa_klienta": nazwa_klienta,
        "uwagi": "; ".join(uwagi),
        "zrodlo": zrodlo,
        "event_id": event_id,
        "created_at": now,
        "raw_json_path": str(json_path),
        "hash": h,
    }

    append_csv_rows(EVENTS_PATH, EVENTS_COLS, [event_row])
    append_csv_rows(ACCEPT_PATH, ACCEPT_COLS, [accept_row])

    return {
        "skipped": False,
        "event_id": event_id,
        "hash": h,
        "tytul_sprawy": tytul,
        "status_sprawdzenia": status_sprawdzenia,
        "errors": errors,
        "events_path": str(EVENTS_PATH),
        "accept_path": str(ACCEPT_PATH),
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Użycie: python 01-system/quick_order_events.py <sciezka-do-json>")
        return 1

    json_path = Path(args[0])
    if not json_path.is_file():
        print(f"Brak pliku: {json_path}")
        return 1

    print("=== Footing System – quick_order_events ===")
    print("Google Contacts: tryb read-only – brak zapisu do Google")
    print()

    result = process_quick_order(json_path)
    if result.get("skipped"):
        print(f"Duplikat pominięty (hash): {result['hash']}")
        print(f"tytul_sprawy:        {result['tytul_sprawy']}")
        print(f"Zdarzenia:           {result['events_path']}")
        return 0

    print(f"event_id:            {result['event_id']}")
    print(f"hash:                {result['hash']}")
    print(f"tytul_sprawy:        {result['tytul_sprawy']}")
    print(f"status_sprawdzenia:  {result['status_sprawdzenia']}")
    if result["errors"]:
        print(f"Uwagi walidacji:     {'; '.join(result['errors'])}")
    print(f"Zdarzenia:           {result['events_path']}")
    print(f"Do akceptacji:       {result['accept_path']}")
    print()
    print("Brak pliku zmian Google Contacts – zgodnie z polityką read-only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
