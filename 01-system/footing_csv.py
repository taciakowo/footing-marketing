"""Wspólny zapis CSV Footing System – separator średnik, UTF-8 BOM."""

from __future__ import annotations

import csv
import re
from pathlib import Path

CSV_DELIMITER = ";"

NORMALIZE_TEXT_COLS = frozenset({
    "nazwa_kontaktu_google",
    "tytul_sprawy",
    "nazwa_klienta",
    "inwestycja",
    "produkty",
    "pozycje_tekst",
    "produkty_lub_fragment",
    "opis_pozycji",
    "uwagi",
    "adres",
    "adres_dostawy",
    "dostawa",
    "sugestia",
    "tresc_lub_nazwa",
    "zastosowanie",
    "zastosowania",
    "skrot_nazwy",
    "miasto",
    "temat",
    "tresc",
    "imie_firma",
    "nazwa_kontaktu",
})


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = re.sub(r" +", " ", text).strip()
    return text


def csv_cell(value: object, column: str) -> object:
    if column in NORMALIZE_TEXT_COLS:
        return normalize_text(value)
    if value is None:
        return ""
    return value


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=columns,
            delimiter=CSV_DELIMITER,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({col: csv_cell(row.get(col, ""), col) for col in columns})
    return path


def append_csv_rows(path: Path, columns: list[str], rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a" if exists else "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=columns,
            delimiter=CSV_DELIMITER,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({col: csv_cell(row.get(col, ""), col) for col in columns})
    return path
