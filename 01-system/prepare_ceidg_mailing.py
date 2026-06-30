#!/usr/bin/env python3
"""Przygotowanie bazy CEIDG do mailingu B2B – osobny tor, bez mieszania z CRM."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from footing_import_rules import INTERNAL_EMAIL_RE, is_internal_email  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CEIDG_ROOT = ROOT / "02-output-private" / "ceidg"
PRIMARY_INPUT = ROOT / "00-inbox" / "input"
CEIDG_INPUT = CEIDG_ROOT / "input"
CEIDG_OUTPUT = CEIDG_ROOT / "output"
CEIDG_KONTROLA = CEIDG_ROOT / "kontrola"
INPUT_ROZPOZNANIE = CEIDG_KONTROLA / "INPUT-ROZPOZNANIE.csv"
MARKETING_OUT = ROOT / "02-output-private" / "marketing"
REPORTS = ROOT / "03-raporty"

ENCODINGS = ("utf-8-sig", "utf-8", "cp1250")
DELIMITERS = (";", ",", "\t")

CSV_EXTENSIONS = {".csv"}
TXT_EXTENSIONS = {".txt"}
SPREADSHEET_EXTENSIONS = {".ods", ".xlsx"}
DETECTABLE_EXTENSIONS = CSV_EXTENSIONS | TXT_EXTENSIONS | SPREADSHEET_EXTENSIONS
PROCESSABLE_EXTENSIONS = CSV_EXTENSIONS | TXT_EXTENSIONS

SPREADSHEET_SKIP_HINT = (
    "Na czas sprintu mailingowego zapisz dane jako CSV UTF-8 z separatorem średnik ;"
)
NAME_CEIDG_KEYWORDS = (
    "ceidg",
    "firma",
    "firmy",
    "działalności",
    "działalnosci",
    "dzialalnosci",
    "zarejestrowane",
    "województwo",
    "wojewodztwo",
)
HEADER_CEIDG_INDICATORS = (
    "nip",
    "regon",
    "nazwapodmiotu",
    "nazwa",
    "email",
    "telefon",
    "adreswww",
    "kodpocztowy",
    "kod pocztowy",
    "miejscowosc",
    "miejscowość",
    "wojewodztwo",
    "województwo",
    "pkd",
)

INPUT_ROZPOZNANIE_COLS = [
    "nazwa_pliku",
    "sciezka",
    "rozszerzenie",
    "rozmiar",
    "rozpoznany_typ",
    "czy_przetwarzac",
    "powod",
]

CEIDG_CLEAN_COLS = [
    "ceidg_id", "nip", "regon", "nazwa_firmy", "imie", "nazwisko", "email", "telefon",
    "strona_www", "pkd", "pkd_opis", "adres", "kod_pocztowy", "miejscowosc", "wojewodztwo",
    "powiat", "gmina", "segment", "priorytet", "powod_segmentacji", "status_marketingowy",
    "zrodlo", "uwagi",
]
BREVO_CEIDG_COLS = [
    "email", "nazwa_firmy", "imie", "nazwisko", "telefon", "strona_www", "miejscowosc",
    "wojewodztwo", "segment", "priorytet", "pkd", "status_marketingowy", "zrodlo", "uwagi",
]
REVIEW_COLS = [
    "powod", "nazwa_firmy", "email", "telefon", "strona_www", "pkd", "segment", "sugestia", "uwagi",
]
PRIORITY_AUDIT_COLS = [
    "email", "nazwa_firmy", "imie", "nazwisko", "segment", "priorytet",
    "priorytet_score", "priorytet_segment", "priorytet_powody",
    "trafienia_slowa", "trafienia_pola", "podejrzenie_false_positive",
]

BUSINESS_SCORE_FIELDS = (
    "nazwa_firmy", "pkd", "pkd_opis", "strona_www", "opis_dzialalnosci",
)
PERSONAL_NAME_FIELDS = frozenset({"imie", "nazwisko"})
POLISH_INFLECTION_SUFFIX = (
    r"ami|ach|ów|ow|owych|owej|owym|em|om|"
    r"y|i|e|a|u|ie|ne|na|ny|nych|nym"
)

CEIDG_SEGMENTS = (
    "pergole_altany_tarasy",
    "ogrody_mala_architektura",
    "budownictwo_drewno",
    "stolarnia_ciesielstwo",
    "domki_wiaty_konstrukcje",
    "ogrodzenia_konstrukcje",
    "konstrukcje_stalowe",
    "brukarstwo_nawierzchnie",
    "elektryka_lampy_ogrodowe",
    "sklepy_ogrodnicze_budowlane",
    "wykonawcy_lokalni",
    "uslugi_remontowo_budowlane",
    "architektura_krajobrazu",
    "montaz_instalacje",
    "producenci_i_rzemioslo",
    "szeroki_potencjal",
    "do_sprawdzenia",
    "poza_grupa",
)

PRIORITY_A_SEGMENTS = {
    "pergole_altany_tarasy",
    "ogrody_mala_architektura",
    "budownictwo_drewno",
    "domki_wiaty_konstrukcje",
    "architektura_krajobrazu",
}
PRIORITY_B_SEGMENTS = {
    "ogrodzenia_konstrukcje",
    "brukarstwo_nawierzchnie",
    "stolarnia_ciesielstwo",
    "konstrukcje_stalowe",
    "uslugi_remontowo_budowlane",
    "sklepy_ogrodnicze_budowlane",
    "elektryka_lampy_ogrodowe",
}
PRIORITY_C_SEGMENTS = {
    "wykonawcy_lokalni",
    "montaz_instalacje",
    "producenci_i_rzemioslo",
    "szeroki_potencjal",
}

SEGMENT_SORT_ORDER = {seg: idx for idx, seg in enumerate(CEIDG_SEGMENTS)}
PRIORITY_SORT_ORDER = {"A": 0, "B": 1, "C": 2, "X": 3}

EMAIL_VALID_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)
JUNK_EMAIL_RE = re.compile(
    r"no-?reply|noreply|donotreply|\bbrak\b|\btest\b|\bexample\b|footing|taciak|taciakowo",
    re.I,
)
TECH_EMAIL_LOCAL_RE = re.compile(
    r"^(no-?reply|noreply|donotreply|mailer-daemon|postmaster|bounce|newsletter|"
    r"admin|office|sekretariat|recepcja|helpdesk|support|system|robot|automat)",
    re.I,
)
SUSPICIOUS_NAME_RE = re.compile(
    r"^\s*$|^\d+$|^test\b|^\.{2,}|brak nazwy",
    re.I,
)
MULTI_EMAIL_SPLIT = re.compile(r"[,;|/\s]+")

COLUMN_MAP: dict[str, list[str]] = {
    "nip": ["nip", "n ip", "numer nip", "numer_nip"],
    "regon": ["regon", "numer regon", "numer_regon"],
    "nazwa_firmy": [
        "nazwa", "nazwa firmy", "nazwa_firmy", "nazwa przedsiębiorcy", "firma",
        "nazwa podmiotu", "nazwapodmiotu", "name", "company",
    ],
    "imie": ["imie", "imię", "first name", "first_name"],
    "nazwisko": ["nazwisko", "last name", "last_name"],
    "email": ["email", "e-mail", "e mail", "adres e-mail", "adres email", "mail"],
    "telefon": ["telefon", "phone", "tel", "numer telefonu"],
    "strona_www": [
        "strona www", "strona_www", "www", "website", "url", "strona",
        "adreswww", "adres www",
    ],
    "pkd": ["pkd", "kod pkd", "pkd glowny", "pkd_główny", "pkd_glowny"],
    "pkd_opis": ["pkd opis", "pkd_opis", "opis pkd", "nazwa pkd", "pkd nazwa"],
    "adres": ["adres", "ulica", "address", "adres siedziby"],
    "kod_pocztowy": ["kod pocztowy", "kod_pocztowy", "postal", "zip"],
    "miejscowosc": ["miejscowosc", "miejscowość", "miasto", "city", "town"],
    "wojewodztwo": ["wojewodztwo", "województwo", "woj"],
    "powiat": ["powiat", "county"],
    "gmina": ["gmina", "commune"],
    "opis_dzialalnosci": [
        "opis dzialalnosci", "opis działalności", "opis_dzialalnosci",
        "przedmiot dzialalnosci", "przedmiot działalności", "przedmiot_dzialalnosci",
        "zakres dzialalnosci", "zakres działalności",
    ],
}

SEGMENT_RULES: list[tuple[str, list[str], int]] = [
    ("pergole_altany_tarasy", [
        r"pergol", r"altan", r"taras", r"tarasow", r"zadaszen",
    ], 4),
    ("ogrody_mala_architektura", [
        r"ogr[oó]d", r"ogrodnicz", r"mał[aą]\s+architektur", r"mala\s+architektur",
        r"architektura\s+ogrod", r"ogrodnik", r"ogrodow",
    ], 4),
    ("architektura_krajobrazu", [
        r"krajobraz", r"ogrody\s+i", r"projektow.*ogrod", r"ziele[nń]",
    ], 4),
    ("domki_wiaty_konstrukcje", [
        r"domk[ió]w", r"domk[ió]w\s+letnisk", r"wiata", r"wiaty", r"altan",
        r"dom\s+rekreacyj", r"dom\s+ogrod",
    ], 4),
    ("budownictwo_drewno", [
        r"drewn", r"dom\s+drewn", r"konstrukcj[ií]\s+drewn", r"domy\s+drewn",
        r"prefabrykat.*drewn",
    ], 3),
    ("stolarnia_ciesielstwo", [
        r"stolar", r"ciesiel", r"tralowni", r"rama\s+drewn", r"mebl.*ogrod",
    ], 3),
    ("ogrodzenia_konstrukcje", [
        r"ogrodzen", r"bram[ay]", r"panel\s+ogrodzeni", r"siatk.*ogrodzeni",
    ], 3),
    ("konstrukcje_stalowe", [
        r"konstrukcj.*stal", r"stalow", r"spawaln", r"hale\s+stal", r"konstrukcje\s+stal",
    ], 3),
    ("brukarstwo_nawierzchnie", [
        r"bruk", r"brukarstw", r"kostka\s+bruk", r"nawierzchn", r"utwardzen",
        r"kostka\s+bet", r"chodnik",
    ], 3),
    ("elektryka_lampy_ogrodowe", [
        r"elektryk", r"lamp", r"oświetlen", r"oswietlen", r"led", r"instalac.*elektr",
        r"ogrodow.*oświetl", r"ogrodow.*oswietl",
    ], 3),
    ("sklepy_ogrodnicze_budowlane", [
        r"sklep", r"market", r"centrum\s+budowl", r"hurtowni", r"materiały\s+budowl",
        r"materialy\s+budowl", r"centrum\s+ogrodn",
    ], 2),
    ("uslugi_remontowo_budowlane", [
        r"remont", r"remontow", r"budowl", r"wyko[nń]czeni", r"dociepl", r"tynk",
        r"murarsk", r"dekar",
    ], 2),
    ("montaz_instalacje", [
        r"montaż", r"montaz", r"instalac", r"serwis.*monta",
    ], 2),
    ("wykonawcy_lokalni", [
        r"wykonaw", r"usług", r"uslug", r"firma\s+uslug", r"prace\s+ogrod",
    ], 1),
    ("producenci_i_rzemioslo", [
        r"produkcj", r"producent", r"wytw[oó]rni", r"rzemios", r"warsztat",
        r"fabryk", r"manufactur",
    ], 1),
]

EXCLUDE_KEYWORDS = re.compile(
    r"urz[aą]d|urzed|gmin[aey]\b|powiat|starostw|ministerstw|"
    r"szko[lł]|przedszkol|uniwersytet|uczelni|"
    r"parafi|kości[oó]l|kosciol|"
    r"fundacj(?!.*ogrod)(?!.*budowl)|"
    r"przychodni|lekarz|medyc|stomatolog|dentyst|fizjoter|weteryn|"
    r"restaurac|gastronom|kebab|pizza|bar\b|catering|"
    r"fryzjer|kosmetyk|salon\s+urody|"
    r"ubezpiecz|"
    r"ksi[eę]gow|biuro\s+rachunk|"
    r"prawnik|adwokat|kancelari|notariusz|"
    r"taks[oó]w|transport\s+osob|"
    r"bank\b|kredyt|pożyczk|pozyczk|"
    r"hotel\b|nocleg|turyst|"
    r"apteka|"
    r"fotograf|video|marketing\s+internet|reklam",
    re.I,
)


@dataclass
class RunOptions:
    scan_only: bool = False
    allow_spreadsheet: bool = False


@dataclass
class SegmentClassification:
    segment: str
    powod: str
    score: int
    conflict: bool
    trafienia_slowa: str
    trafienia_pola: str
    podejrzenie_false_positive: str


def file_extension(path: Path) -> str:
    return path.suffix.lower()


def is_lock_file(name: str) -> bool:
    return name.startswith(".~lock")


def is_spreadsheet(path: Path) -> bool:
    return file_extension(path) in SPREADSHEET_EXTENSIONS


def is_detectable_extension(path: Path) -> bool:
    return file_extension(path) in DETECTABLE_EXTENSIONS


def is_processable_extension(path: Path, allow_spreadsheet: bool) -> bool:
    ext = file_extension(path)
    if ext in CSV_EXTENSIONS:
        return True
    if ext in TXT_EXTENSIONS:
        return True
    if ext in SPREADSHEET_EXTENSIONS:
        return allow_spreadsheet
    return False


def list_input_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        p for p in folder.iterdir()
        if p.is_file()
    )


def normalize_col(name: str) -> str:
    n = (name or "").strip().lower()
    n = n.replace("ł", "l").replace("ó", "o").replace("ę", "e").replace("ą", "a")
    n = n.replace("ś", "s").replace("ź", "z").replace("ż", "z").replace("ć", "c").replace("ń", "n")
    n = re.sub(r"\s+", " ", n)
    return n


def headers_match_ceidg(headers: list[str]) -> tuple[bool, str]:
    if not headers:
        return False, "brak nagłówków"
    norm_headers = {normalize_col(h) for h in headers}
    matched: list[str] = []
    for ind in HEADER_CEIDG_INDICATORS:
        nind = normalize_col(ind)
        if nind in norm_headers:
            matched.append(ind)
    if matched:
        shown = ", ".join(matched[:5])
        if len(matched) > 5:
            shown += ", ..."
        return True, f"nagłówki: {shown}"
    return False, "brak dopasowania nagłówków"


def name_matches_ceidg(filename: str) -> tuple[bool, str]:
    name_lower = filename.lower()
    norm_name = normalize_col(filename)
    for kw in NAME_CEIDG_KEYWORDS:
        if kw in name_lower or normalize_col(kw) in norm_name:
            return True, f"nazwa zawiera {kw}"
    return False, "nazwa nie pasuje"


def txt_looks_like_csv(path: Path) -> bool:
    _, fields = read_csv_file(path)
    return len(fields) >= 2


def classify_input_file(path: Path, options: RunOptions) -> dict:
    name = path.name
    ext = path.suffix
    ext_lower = file_extension(path)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    base = {
        "nazwa_pliku": name,
        "sciezka": str(path),
        "rozszerzenie": ext,
        "rozmiar": size,
    }

    if is_lock_file(name):
        return {
            **base,
            "rozpoznany_typ": "pominiety",
            "czy_przetwarzac": "nie",
            "powod": "plik blokady",
        }

    if not is_detectable_extension(path):
        return {
            **base,
            "rozpoznany_typ": "nieznany",
            "czy_przetwarzac": "nie",
            "powod": f"nieobsługiwane rozszerzenie {ext or '(brak)'}",
        }

    if is_spreadsheet(path) and not options.allow_spreadsheet:
        by_name, name_reason = name_matches_ceidg(name)
        if by_name:
            return {
                **base,
                "rozpoznany_typ": "ceidg_arkusz",
                "czy_przetwarzac": "nie",
                "powod": f"wykryto arkusz ({name_reason}) — sprint CSV only",
            }
        return {
            **base,
            "rozpoznany_typ": "arkusz",
            "czy_przetwarzac": "nie",
            "powod": "arkusz — sprint CSV only",
        }

    by_name, name_reason = name_matches_ceidg(name)
    if by_name:
        can_process = is_processable_extension(path, options.allow_spreadsheet)
        if ext_lower in TXT_EXTENSIONS and not txt_looks_like_csv(path):
            return {
                **base,
                "rozpoznany_typ": "ceidg",
                "czy_przetwarzac": "nie",
                "powod": f"{name_reason}; plik .txt nie wygląda jak CSV",
            }
        return {
            **base,
            "rozpoznany_typ": "ceidg",
            "czy_przetwarzac": "tak" if can_process else "nie",
            "powod": name_reason,
        }

    headers = peek_headers(path, options)
    by_headers, header_reason = headers_match_ceidg(headers)
    if by_headers:
        can_process = is_processable_extension(path, options.allow_spreadsheet)
        if ext_lower in TXT_EXTENSIONS and not txt_looks_like_csv(path):
            return {
                **base,
                "rozpoznany_typ": "ceidg",
                "czy_przetwarzac": "nie",
                "powod": f"{header_reason}; plik .txt nie wygląda jak CSV",
            }
        return {
            **base,
            "rozpoznany_typ": "ceidg",
            "czy_przetwarzac": "tak" if can_process else "nie",
            "powod": header_reason,
        }

    if is_spreadsheet(path):
        return {
            **base,
            "rozpoznany_typ": "arkusz",
            "czy_przetwarzac": "nie",
            "powod": "brak dopasowania nazwy i nagłówków",
        }

    return {
        **base,
        "rozpoznany_typ": "nieznany",
        "czy_przetwarzac": "nie",
        "powod": "brak dopasowania nazwy i nagłówków",
    }


def format_size(size: int) -> str:
    if size >= 1_048_576:
        return f"{size / 1_048_576:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def print_file_scan_line(info: dict, options: RunOptions) -> None:
    size = int(info["rozmiar"])
    name = info["nazwa_pliku"]
    typ = info["rozpoznany_typ"]

    if is_spreadsheet(Path(name)) and not options.allow_spreadsheet:
        print(f"  Pominięto plik arkusza: {name}. {SPREADSHEET_SKIP_HINT}")
        return

    if typ == "ceidg" and info["czy_przetwarzac"] == "tak":
        print(
            f"  Rozpoznano CEIDG: {name} ({format_size(size)}) — powód: {info['powod']}"
        )
    elif typ == "ceidg_arkusz":
        print(
            f"  Wykryto CEIDG (arkusz): {name} ({format_size(size)}) — "
            f"nie przetwarzany — {info['powod']}"
        )
    elif typ == "pominiety":
        print(f"  Pominięto: {name} — {info['powod']}")
    else:
        print(
            f"  Pominięto: {name} ({format_size(size)}, {info['rozszerzenie']}) — "
            f"{info['powod']}"
        )


def print_input_diagnostics(primary_files: list[Path], options: RunOptions) -> None:
    print("=== Diagnostyka wejścia ===")
    print(f"Katalog roboczy:       {Path.cwd()}")
    print(f"Folder input (główny): {PRIMARY_INPUT}")
    print(f"Folder istnieje:       {'tak' if PRIMARY_INPUT.is_dir() else 'nie'}")
    print(f"Folder fallback:       {CEIDG_INPUT}")
    print()

    if not primary_files:
        print(f"Brak plików w {PRIMARY_INPUT}")
    else:
        print(f"Pliki w {PRIMARY_INPUT}:")
        for path in primary_files:
            info = classify_input_file(path, options)
            print_file_scan_line(info, options)
    print()


def write_input_recognition(rows: list[dict]) -> None:
    CEIDG_KONTROLA.mkdir(parents=True, exist_ok=True)
    write_csv(INPUT_ROZPOZNANIE, INPUT_ROZPOZNANIE_COLS, rows)


def scan_input_files(folders: list[Path], options: RunOptions) -> list[dict]:
    rows: list[dict] = []
    for folder in folders:
        for path in list_input_files(folder):
            rows.append(classify_input_file(path, options))
    return rows


def select_ceidg_files(primary_files: list[Path], options: RunOptions) -> tuple[list[Path], list[dict], str]:
    recognition_rows: list[dict] = []
    ceidg_files: list[Path] = []

    for path in primary_files:
        info = classify_input_file(path, options)
        recognition_rows.append(info)
        if info["czy_przetwarzac"] == "tak":
            ceidg_files.append(path)

    source = "primary"
    if ceidg_files:
        return ceidg_files, recognition_rows, source

    fallback_files = list_input_files(CEIDG_INPUT)
    if fallback_files:
        print(f"Brak plików CSV CEIDG w {PRIMARY_INPUT} — skan fallback: {CEIDG_INPUT}")
        for path in fallback_files:
            info = classify_input_file(path, options)
            recognition_rows.append(info)
            if info["czy_przetwarzac"] == "tak":
                ceidg_files.append(path)
                print(
                    f"  Rozpoznano CEIDG (fallback): {info['nazwa_pliku']} — "
                    f"powód: {info['powod']}"
                )
            elif is_spreadsheet(path) and not options.allow_spreadsheet:
                print(f"  Pominięto plik arkusza: {path.name}. {SPREADSHEET_SKIP_HINT}")
        source = "fallback"

    return ceidg_files, recognition_rows, source


def map_columns(fieldnames: list[str]) -> dict[str, str]:
    norm_to_orig = {normalize_col(h): h for h in fieldnames}
    mapping: dict[str, str] = {}
    for target, aliases in COLUMN_MAP.items():
        for alias in aliases:
            key = normalize_col(alias)
            if key in norm_to_orig:
                mapping[target] = norm_to_orig[key]
                break
    return mapping


def read_csv_file(path: Path) -> tuple[list[dict], list[str]]:
    raw = path.read_bytes()
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    best_rows: list[dict] = []
    best_fields: list[str] = []
    for delim in DELIMITERS:
        try:
            reader = csv.DictReader(StringIO(text), delimiter=delim)
            if not reader.fieldnames or len(reader.fieldnames) < 2:
                continue
            rows = list(reader)
            if len(rows) >= len(best_rows):
                best_rows = rows
                best_fields = list(reader.fieldnames or [])
        except csv.Error:
            continue
    return best_rows, best_fields


def peek_headers(path: Path, options: RunOptions) -> list[str]:
    ext = file_extension(path)
    if ext in CSV_EXTENSIONS | TXT_EXTENSIONS:
        _, fields = read_csv_file(path)
        return fields

    if ext not in SPREADSHEET_EXTENSIONS or not options.allow_spreadsheet:
        return []

    try:
        import pandas as pd
    except ImportError:
        return []

    try:
        if ext == ".ods":
            df = pd.read_excel(path, engine="odf", nrows=0)
        else:
            try:
                df = pd.read_excel(path, engine="openpyxl", nrows=0)
            except ImportError:
                df = pd.read_excel(path, nrows=0)
        return [str(c) for c in df.columns]
    except ImportError:
        return []
    except Exception:
        return []


def read_tabular_file(path: Path, options: RunOptions) -> tuple[list[dict], list[str]]:
    ext = file_extension(path)
    if ext in CSV_EXTENSIONS:
        return read_csv_file(path)

    if ext in TXT_EXTENSIONS:
        if not txt_looks_like_csv(path):
            print(f"  Pominięto: {path.name} — plik .txt nie wygląda jak CSV")
            return [], []
        return read_csv_file(path)

    if ext not in SPREADSHEET_EXTENSIONS:
        return [], []

    if not options.allow_spreadsheet:
        print(f"  Pominięto plik arkusza: {path.name}. {SPREADSHEET_SKIP_HINT}")
        return [], []

    try:
        import pandas as pd
    except ImportError:
        print("Brak biblioteki pandas. Uruchom: pip install pandas")
        return [], []

    try:
        if ext == ".ods":
            try:
                df = pd.read_excel(path, engine="odf")
            except ImportError:
                print("Brak biblioteki odfpy. Uruchom: pip install odfpy")
                return [], []
        elif ext == ".xlsx":
            try:
                df = pd.read_excel(path, engine="openpyxl")
            except ImportError:
                try:
                    df = pd.read_excel(path)
                except ImportError:
                    print("Brak biblioteki openpyxl. Uruchom: pip install openpyxl")
                    return [], []
        else:
            return [], []
    except ImportError:
        if ext == ".ods":
            print("Brak biblioteki odfpy. Uruchom: pip install odfpy")
        return [], []
    except Exception as exc:
        print(f"Nie udało się odczytać {path.name}: {exc}")
        return [], []

    df = df.fillna("")
    fields = [str(c) for c in df.columns]
    rows = df.astype(str).to_dict(orient="records")
    return rows, fields


def clean_nip(val: str) -> str:
    return re.sub(r"\D", "", val or "")


def clean_phone(val: str) -> str:
    digits = re.sub(r"\D", "", val or "")
    if len(digits) == 9:
        return "+48" + digits
    if len(digits) == 11 and digits.startswith("48"):
        return "+" + digits
    return (val or "").strip()


def split_emails(raw: str) -> list[str]:
    if not raw:
        return []
    parts = MULTI_EMAIL_SPLIT.split(raw.strip())
    out: list[str] = []
    for p in parts:
        p = p.strip().lower()
        if "@" in p and p not in out:
            out.append(p)
    if not out and "@" in raw:
        out.append(raw.strip().lower())
    return out


def is_valid_export_email(email: str) -> tuple[bool, str]:
    email = (email or "").strip().lower()
    if not email:
        return False, "brak_email"
    if " " in email or email.count("@") != 1:
        return False, "niepoprawny_email"
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        return False, "niepoprawny_email"
    if not EMAIL_VALID_RE.match(email):
        return False, "niepoprawny_email"
    if JUNK_EMAIL_RE.search(email):
        return False, "email_smieciowy"
    if is_internal_email(email) or INTERNAL_EMAIL_RE.search(email):
        return False, "email_wewnetrzny"
    return True, ""


def email_looks_technical(email: str) -> bool:
    local = (email or "").split("@")[0]
    return bool(TECH_EMAIL_LOCAL_RE.search(local))


def _is_word_char(ch: str) -> bool:
    return bool(ch) and (ch.isalnum() or ch == "_")


def _has_valid_inflection_suffix(text: str, end: int) -> bool:
    remainder = text[end:]
    if not remainder:
        return True
    if not remainder[0].isalpha():
        return True
    return bool(re.match(rf"^(?:{POLISH_INFLECTION_SUFFIX})(?=\W|$)", remainder, re.I))


def safe_pattern_match(pattern: str, text: str) -> bool:
    """Dopasowanie z granicą słowa – odrzuca trafienia w nazwiskach typu Tarasiewicz."""
    if not text:
        return False
    for match in re.finditer(pattern, text, re.I):
        start, end = match.span()
        if start > 0 and _is_word_char(text[start - 1]):
            continue
        if end < len(text) and _is_word_char(text[end]):
            if not _has_valid_inflection_suffix(text, end):
                continue
        return True
    return False


def strip_personal_from_nazwa(nazwa: str, imie: str, nazwisko: str) -> str:
    result = nazwa or ""
    for token in (imie, nazwisko):
        token = (token or "").strip()
        if len(token) < 2:
            continue
        result = re.sub(
            rf"(?<![\w]){re.escape(token)}(?![\w])",
            " ",
            result,
            flags=re.I,
        )
    return re.sub(r"\s+", " ", result).strip()


def business_field_texts(rec: dict) -> dict[str, str]:
    imie = rec.get("imie", "")
    nazwisko = rec.get("nazwisko", "")
    nazwa = strip_personal_from_nazwa(rec.get("nazwa_firmy", ""), imie, nazwisko)
    fields = {
        "nazwa_firmy": nazwa,
        "pkd": rec.get("pkd", ""),
        "pkd_opis": rec.get("pkd_opis", ""),
        "strona_www": rec.get("strona_www", ""),
        "opis_dzialalnosci": rec.get("opis_dzialalnosci", ""),
    }
    return {name: (value or "").strip() for name, value in fields.items() if (value or "").strip()}


def personal_field_text(rec: dict) -> str:
    parts = [
        (rec.get("imie", "") or "").strip(),
        (rec.get("nazwisko", "") or "").strip(),
    ]
    return " ".join(p for p in parts if p)


def collect_pattern_hits(text: str, field_name: str) -> list[tuple[str, str, str, int]]:
    hits: list[tuple[str, str, str, int]] = []
    for seg, patterns, weight in SEGMENT_RULES:
        for pat in patterns:
            if safe_pattern_match(pat, text):
                hits.append((seg, pat, field_name, weight))
                break
    return hits


def classify_segment(rec: dict) -> SegmentClassification:
    """Segmentacja wyłącznie na polach branżowych; imię/nazwisko nie punktują."""
    business_fields = business_field_texts(rec)
    business_blob = " ".join(business_fields.values())
    personal_text = personal_field_text(rec)

    if EXCLUDE_KEYWORDS.search(business_blob):
        return SegmentClassification(
            segment="poza_grupa",
            powod="słowa wykluczające branżę",
            score=0,
            conflict=False,
            trafienia_slowa="",
            trafienia_pola="",
            podejrzenie_false_positive="nie",
        )

    scores: Counter = Counter()
    reasons: list[str] = []
    slowa_hits: list[str] = []
    pola_hits: list[str] = []
    personal_only_hits: list[str] = []

    for field_name, field_text in business_fields.items():
        for seg, pat, hit_field, weight in collect_pattern_hits(field_text, field_name):
            scores[seg] += weight
            reasons.append(f"{seg}:{pat}@{hit_field}")
            slowa_hits.append(pat)
            pola_hits.append(hit_field)

    if personal_text:
        unsafe_personal_hits: list[str] = []
        for seg, patterns, _weight in SEGMENT_RULES:
            for pat in patterns:
                if re.search(pat, personal_text, re.I) and not safe_pattern_match(pat, personal_text):
                    unsafe_personal_hits.append(pat)
                    break
        business_patterns = set(slowa_hits)
        for pat in unsafe_personal_hits:
            if pat not in business_patterns:
                personal_only_hits.append(pat)

    podejrzenie = "tak" if personal_only_hits else "nie"

    if not scores:
        return SegmentClassification(
            segment="szeroki_potencjal",
            powod="brak wąskiego dopasowania – szeroki potencjał",
            score=0,
            conflict=False,
            trafienia_slowa="",
            trafienia_pola="",
            podejrzenie_false_positive=podejrzenie,
        )

    ranked = scores.most_common()
    seg, score = ranked[0]
    if len(ranked) > 1 and ranked[1][1] >= score * 0.75 and ranked[1][0] != seg:
        return SegmentClassification(
            segment="do_sprawdzenia",
            powod=f"konflikt segmentów: {ranked[0][0]} vs {ranked[1][0]}",
            score=score,
            conflict=True,
            trafienia_slowa="; ".join(dict.fromkeys(slowa_hits)),
            trafienia_pola="; ".join(dict.fromkeys(pola_hits)),
            podejrzenie_false_positive=podejrzenie,
        )

    return SegmentClassification(
        segment=seg,
        powod="; ".join(reasons[:3]),
        score=score,
        conflict=False,
        trafienia_slowa="; ".join(dict.fromkeys(slowa_hits)),
        trafienia_pola="; ".join(dict.fromkeys(pola_hits)),
        podejrzenie_false_positive=podejrzenie,
    )


def assign_priority(segment: str) -> str:
    if segment == "poza_grupa":
        return "X"
    if segment == "do_sprawdzenia":
        return "C"
    if segment in PRIORITY_A_SEGMENTS:
        return "A"
    if segment in PRIORITY_B_SEGMENTS:
        return "B"
    if segment in PRIORITY_C_SEGMENTS:
        return "C"
    return "C"


def assess_review(rec: dict, segment_conflict: bool) -> tuple[bool, str, str]:
    """Czy rekord (z poprawnym e-mailem) trafia do ręcznej weryfikacji."""
    segment = rec.get("segment", "")
    email = rec.get("email", "")
    nazwa = rec.get("nazwa_firmy", "")

    if segment == "do_sprawdzenia":
        return True, "niejasny_segment", "Zweryfikuj segment ręcznie przed wysyłką"

    if segment_conflict:
        return True, "konflikt_segmentow", "Wybierz właściwy segment przed eksportem"

    if SUSPICIOUS_NAME_RE.search(nazwa) or len(nazwa.strip()) < 3:
        return True, "podejrzana_nazwa", "Sprawdź nazwę firmy"

    if email_looks_technical(email) and not JUNK_EMAIL_RE.search(email):
        return True, "email_techniczny", "E-mail ogólny – rozważ personalizację lub pominięcie"

    return False, "", ""


def brevo_sort_key(rec: dict) -> tuple:
    woj = normalize_col(rec.get("wojewodztwo", ""))
    is_wlkp = 0 if "wielkopolsk" in woj else 1
    return (
        PRIORITY_SORT_ORDER.get(rec.get("priorytet", "C"), 9),
        SEGMENT_SORT_ORDER.get(rec.get("segment", ""), 50),
        0 if rec.get("nazwa_firmy", "").strip() else 1,
        0 if rec.get("strona_www", "").strip() else 1,
        0 if rec.get("telefon", "").strip() else 1,
        is_wlkp,
        rec.get("email", ""),
    )


def to_brevo_row(rec: dict) -> dict:
    return {
        "email": rec.get("email", ""),
        "nazwa_firmy": rec.get("nazwa_firmy", ""),
        "imie": rec.get("imie", ""),
        "nazwisko": rec.get("nazwisko", ""),
        "telefon": rec.get("telefon", ""),
        "strona_www": rec.get("strona_www", ""),
        "miejscowosc": rec.get("miejscowosc", ""),
        "wojewodztwo": rec.get("wojewodztwo", ""),
        "segment": rec.get("segment", ""),
        "priorytet": rec.get("priorytet", ""),
        "pkd": rec.get("pkd", ""),
        "status_marketingowy": "potencjalny_klient_ceidg",
        "zrodlo": "ceidg",
        "uwagi": rec.get("uwagi", ""),
    }


def to_priority_audit_row(rec: dict) -> dict:
    return {
        "email": rec.get("email", ""),
        "nazwa_firmy": rec.get("nazwa_firmy", ""),
        "imie": rec.get("imie", ""),
        "nazwisko": rec.get("nazwisko", ""),
        "segment": rec.get("segment", ""),
        "priorytet": rec.get("priorytet", ""),
        "priorytet_score": rec.get("priorytet_score", ""),
        "priorytet_segment": rec.get("priorytet_segment", ""),
        "priorytet_powody": rec.get("priorytet_powody", ""),
        "trafienia_slowa": rec.get("trafienia_slowa", ""),
        "trafienia_pola": rec.get("trafienia_pola", ""),
        "podejrzenie_false_positive": rec.get("podejrzenie_false_positive", ""),
    }


def is_brevo_exportable(rec: dict) -> bool:
    if rec.get("priorytet") not in ("A", "B", "C"):
        return False
    if rec.get("segment") in ("poza_grupa", "do_sprawdzenia"):
        return False
    email = rec.get("email", "")
    ok, _ = is_valid_export_email(email)
    return ok and bool(email)


def build_test_050(sorted_export: list[dict]) -> list[dict]:
    a_rows = [r for r in sorted_export if r.get("priorytet") == "A"]
    b_rows = [r for r in sorted_export if r.get("priorytet") == "B"]
    picked = a_rows[:50]
    if len(picked) < 50:
        picked.extend(b_rows[: 50 - len(picked)])
    return picked


def build_test_100(sorted_export: list[dict]) -> list[dict]:
    return sorted_export[:100]


def make_ceidg_id(nip: str, nazwa: str, email: str) -> str:
    if nip:
        return f"CEIDG-NIP-{nip}"
    key = f"{nazwa}|{email}".encode("utf-8", errors="replace")
    return "CEIDG-" + hashlib.sha1(key).hexdigest()[:12]


def row_from_raw(raw: dict, mapping: dict[str, str], source_file: str) -> list[dict]:
    def get(field: str) -> str:
        col = mapping.get(field)
        return (raw.get(col, "") if col else "").strip()

    nazwa = get("nazwa_firmy")
    nip = clean_nip(get("nip"))
    emails = split_emails(get("email"))
    base = {
        "nip": nip,
        "regon": clean_nip(get("regon")),
        "nazwa_firmy": nazwa,
        "imie": get("imie"),
        "nazwisko": get("nazwisko"),
        "telefon": clean_phone(get("telefon")),
        "strona_www": get("strona_www"),
        "pkd": get("pkd"),
        "pkd_opis": get("pkd_opis"),
        "opis_dzialalnosci": get("opis_dzialalnosci"),
        "adres": get("adres"),
        "kod_pocztowy": get("kod_pocztowy"),
        "miejscowosc": get("miejscowosc"),
        "wojewodztwo": get("wojewodztwo"),
        "powiat": get("powiat"),
        "gmina": get("gmina"),
        "zrodlo": "ceidg",
        "status_marketingowy": "potencjalny_klient_ceidg",
        "_source_file": source_file,
    }
    classification = classify_segment(base)
    segment = classification.segment
    powod = classification.powod
    score = classification.score
    conflict = classification.conflict
    priorytet = assign_priority(segment)

    if not emails:
        return []

    rows: list[dict] = []
    for i, em in enumerate(emails):
        uwagi = f"plik: {source_file}"
        if i > 0:
            uwagi += f"; dodatkowy email #{i + 1} z pola źródłowego"
        rec = {
            **base,
            "email": em,
            "segment": segment,
            "priorytet": priorytet,
            "powod_segmentacji": powod,
            "priorytet_score": score,
            "priorytet_segment": segment,
            "priorytet_powody": powod,
            "trafienia_slowa": classification.trafienia_slowa,
            "trafienia_pola": classification.trafienia_pola,
            "podejrzenie_false_positive": classification.podejrzenie_false_positive,
            "uwagi": uwagi,
            "ceidg_id": make_ceidg_id(nip, nazwa, em),
            "_segment_conflict": conflict,
        }
        rows.append(rec)
    return rows


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def write_report(stats: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    segments = stats.get("segment_counts", Counter())
    seg_lines = "\n".join(
        f"| {s} | {segments.get(s, 0)} |" for s in CEIDG_SEGMENTS if segments.get(s, 0)
    )
    if not seg_lines:
        seg_lines = "| (brak) | 0 |"

    export_a = stats.get("export_a", 0)
    export_b = stats.get("export_b", 0)
    export_c = stats.get("export_c", 0)
    if export_a >= 50:
        first_import = "BREVO-CEIDG-TEST-050-v2.csv (partia testowa priorytet A/B)"
    elif stats.get("brevo_export", 0) > 0:
        first_import = "BREVO-CEIDG-TEST-050-v2.csv"
    else:
        first_import = "brak danych do importu"

    quality = []
    if stats.get("input_rows", 0) == 0:
        quality.append(
            "Brak plików CEIDG do przetworzenia – wrzuć eksport CSV (UTF-8, separator `;`) "
            "do `00-inbox/input/`."
        )
    if stats.get("valid_emails", 0) == 0 and stats.get("input_rows", 0) > 0:
        quality.append("Żaden rekord nie ma poprawnego e-maila – sprawdź mapowanie kolumn.")
    if stats.get("brevo_export", 0) == 0 and stats.get("valid_emails", 0) > 0:
        quality.append("Są poprawne e-maile, ale brak eksportu – sprawdź priorytety i segmenty.")
    if not quality:
        quality.append("Rozpocznij od BREVO-CEIDG-TEST-050-v2.csv, potem rozszerzaj partiami.")

    processed = stats.get("processed_files") or []
    processed_line = ", ".join(processed) if processed else "brak"
    elapsed = stats.get("elapsed_seconds", 0)

    (REPORTS / "CEIDG-MAILING-001.md").write_text(
        f"# CEIDG Mailing 001 – podsumowanie\n\n"
        f"Wygenerowano: {now}\n\n"
        f"Rekordy bez adresu e-mail **nie są eksportowane** i **nie są kierowane do ręcznej "
        f"weryfikacji**, ponieważ sprint dotyczy mailingu.\n\n"
        f"## Statystyki zbiorcze (bez danych osobowych)\n\n"
        f"| Metryka | Liczba |\n|---|---:|\n"
        f"| Pliki w 00-inbox/input | {stats.get('inbox_files', 0)} |\n"
        f"| Przetworzone pliki | {processed_line} |\n"
        f"| Rekordy wejściowe | {stats.get('input_rows', 0)} |\n"
        f"| Rekordy bez e-maila | {stats.get('rekordy_bez_emaila', 0)} |\n"
        f"| Rekordy z poprawnym e-mailem | {stats.get('valid_emails', 0)} |\n"
        f"| Rekordy z błędnym e-mailem | {stats.get('rekordy_zly_email', 0)} |\n"
        f"| Duplikaty e-mail usunięte | {stats.get('duplicates_removed', 0)} |\n"
        f"| Rekordy po czyszczeniu (z e-mailem) | {stats.get('clean_rows', 0)} |\n"
        f"| Priorytet A | {stats.get('priority_a', 0)} |\n"
        f"| Priorytet B | {stats.get('priority_b', 0)} |\n"
        f"| Priorytet C | {stats.get('priority_c', 0)} |\n"
        f"| Priorytet X | {stats.get('priority_x', 0)} |\n"
        f"| Do sprawdzenia | {stats.get('review_count', 0)} |\n"
        f"| Eksport BREVO-CEIDG-001.csv | {stats.get('brevo_export', 0)} |\n"
        f"| TEST-050-v2 | {stats.get('test_050', 0)} |\n"
        f"| TEST-100-v2 | {stats.get('test_100', 0)} |\n"
        f"| Podejrzenia false positive | {stats.get('false_positive_suspicion', 0)} |\n"
        f"| A-001 | {export_a} |\n"
        f"| B-001 | {export_b} |\n"
        f"| C-001 | {export_c} |\n"
        f"| Czas przetwarzania (s) | {elapsed:.1f} |\n\n"
        f"## Podział według segmentów (rekordy z poprawnym e-mailem)\n\n"
        f"| Segment | Liczba |\n|---|---:|\n{seg_lines}\n\n"
        f"## Rekomendowany pierwszy import do Brevo\n\n"
        f"**{first_import}**\n\n"
        f"## Uwagi jakościowe\n\n"
        + "\n".join(f"- {q}" for q in quality) + "\n\n"
        f"## Ostrożność przy kampanii CEIDG\n\n"
        f"- CEIDG jest **osobnym źródłem** – nie mieszać z klientami Google/SMS/e-mail.\n"
        f"- Wysyłka masowa B2B wymaga ostrożności prawnej (identyfikacja nadawcy, podstawa kontaktu).\n"
        f"- Kampanię testuj na **małej partii** (TEST-050-v2, potem TEST-100-v2).\n"
        f"- Wiadomość musi mieć **jasną identyfikację nadawcy** Footing.\n"
        f"- Musi być **prosty sposób wypisania / sprzeciwu** (link lub odpowiedź).\n"
        f"- **Nie wysyłać całej bazy naraz** – stopniowe rozszerzanie po analizie bounce/unsubscribe.\n",
        encoding="utf-8",
    )


def process_ceidg(options: RunOptions) -> dict:
    PRIMARY_INPUT.mkdir(parents=True, exist_ok=True)
    CEIDG_OUTPUT.mkdir(parents=True, exist_ok=True)
    CEIDG_KONTROLA.mkdir(parents=True, exist_ok=True)
    MARKETING_OUT.mkdir(parents=True, exist_ok=True)

    primary_files = list_input_files(PRIMARY_INPUT)
    print_input_diagnostics(primary_files, options)

    ceidg_files, recognition_rows, input_source = select_ceidg_files(primary_files, options)
    write_input_recognition(recognition_rows)

    ceidg_recognized = sum(
        1 for r in recognition_rows
        if r["rozpoznany_typ"] in ("ceidg", "ceidg_arkusz")
    )

    if options.scan_only:
        print("=== Tryb --scan-only: bez przetwarzania rekordów ===")
        return {
            "inbox_files": len(primary_files),
            "ceidg_recognized": ceidg_recognized,
            "processed_files": [],
            "input_source": input_source,
            "input_rows": 0,
            "clean_rows": 0,
            "valid_emails": 0,
            "duplicates_removed": 0,
            "excluded": 0,
            "priority_a": 0,
            "priority_b": 0,
            "priority_c": 0,
            "priority_x": 0,
            "brevo_export": 0,
            "segment_counts": Counter(),
            "scan_only": True,
        }

    processed_names: list[str] = []
    t0 = time.perf_counter()

    all_rows: list[dict] = []
    input_rows = 0
    rekordy_bez_emaila = 0
    rekordy_zly_email = 0

    for path in ceidg_files:
        raw_rows, fields = read_tabular_file(path, options)
        if not fields:
            print(f"  Pominięto (brak danych): {path.name}")
            continue
        mapping = map_columns(fields)
        input_rows += len(raw_rows)
        processed_names.append(path.name)
        print(f"  Przetwarzanie: {path.name} ({len(raw_rows)} rekordów)")
        for raw in raw_rows:
            email_col = mapping.get("email")
            raw_email = (raw.get(email_col, "") if email_col else "").strip()
            expanded = row_from_raw(raw, mapping, path.name)
            if not expanded:
                if not raw_email:
                    rekordy_bez_emaila += 1
                else:
                    parts = split_emails(raw_email)
                    if not parts:
                        rekordy_bez_emaila += 1
                    else:
                        for em in parts:
                            ok, _ = is_valid_export_email(em)
                            if not ok:
                                rekordy_zly_email += 1
                continue
            all_rows.extend(expanded)

    clean_rows: list[dict] = []
    review_rows: list[dict] = []
    seen_emails: set[str] = set()
    stats: Counter = Counter()
    duplicates_removed = 0

    for rec in all_rows:
        email = rec.get("email", "").strip().lower()
        ok, reason = is_valid_export_email(email)

        if not ok:
            rekordy_zly_email += 1
            continue

        if email in seen_emails:
            duplicates_removed += 1
            continue
        seen_emails.add(email)

        clean_rows.append(rec)
        stats["valid_emails"] += 1
        stats[f"priorytet_{rec.get('priorytet', 'C').lower()}"] += 1

        needs, review_powod, sugestia = assess_review(
            rec, rec.get("_segment_conflict", False)
        )
        if needs:
            review_rows.append({
                "powod": review_powod,
                "nazwa_firmy": rec.get("nazwa_firmy", ""),
                "email": email,
                "telefon": rec.get("telefon", ""),
                "strona_www": rec.get("strona_www", ""),
                "pkd": rec.get("pkd", ""),
                "segment": rec.get("segment", ""),
                "sugestia": sugestia,
                "uwagi": rec.get("uwagi", ""),
            })

    exportable = [r for r in clean_rows if is_brevo_exportable(r)]
    exportable.sort(key=brevo_sort_key)

    brevo_a = [to_brevo_row(r) for r in exportable if r.get("priorytet") == "A"]
    brevo_b = [to_brevo_row(r) for r in exportable if r.get("priorytet") == "B"]
    brevo_c = [to_brevo_row(r) for r in exportable if r.get("priorytet") == "C"]
    brevo_all = [to_brevo_row(r) for r in exportable]
    test_050 = build_test_050(exportable)
    test_100 = build_test_100(exportable)

    clean_for_file = [{k: v for k, v in r.items() if not k.startswith("_")} for r in clean_rows]
    clean_for_file.sort(key=brevo_sort_key)
    audit_rows = [to_priority_audit_row(r) for r in clean_rows]
    audit_rows.sort(key=brevo_sort_key)
    false_positive_count = sum(
        1 for r in clean_rows if r.get("podejrzenie_false_positive") == "tak"
    )

    write_csv(CEIDG_OUTPUT / "CEIDG-CZYSTE.csv", CEIDG_CLEAN_COLS, clean_for_file)
    write_csv(CEIDG_KONTROLA / "CEIDG-DO-SPRAWDZENIA.csv", REVIEW_COLS, review_rows)
    write_csv(MARKETING_OUT / "BREVO-CEIDG-001.csv", BREVO_CEIDG_COLS, brevo_all)
    write_csv(
        MARKETING_OUT / "BREVO-CEIDG-TEST-050-v2.csv",
        BREVO_CEIDG_COLS,
        [to_brevo_row(r) for r in test_050],
    )
    write_csv(
        MARKETING_OUT / "BREVO-CEIDG-TEST-100-v2.csv",
        BREVO_CEIDG_COLS,
        [to_brevo_row(r) for r in test_100],
    )
    write_csv(MARKETING_OUT / "CEIDG-PRIORYTET-AUDYT.csv", PRIORITY_AUDIT_COLS, audit_rows)
    write_csv(MARKETING_OUT / "BREVO-CEIDG-A-001.csv", BREVO_CEIDG_COLS, brevo_a)
    write_csv(MARKETING_OUT / "BREVO-CEIDG-B-001.csv", BREVO_CEIDG_COLS, brevo_b)
    write_csv(MARKETING_OUT / "BREVO-CEIDG-C-001.csv", BREVO_CEIDG_COLS, brevo_c)

    segment_counts = Counter(rec.get("segment", "") for rec in clean_rows)
    elapsed = time.perf_counter() - t0

    result = {
        "inbox_files": len(primary_files),
        "ceidg_recognized": ceidg_recognized,
        "processed_files": processed_names,
        "input_source": input_source,
        "input_rows": input_rows,
        "rekordy_bez_emaila": rekordy_bez_emaila,
        "rekordy_zly_email": rekordy_zly_email,
        "clean_rows": len(clean_rows),
        "valid_emails": stats["valid_emails"],
        "duplicates_removed": duplicates_removed,
        "review_count": len(review_rows),
        "priority_a": stats.get("priorytet_a", 0),
        "priority_b": stats.get("priorytet_b", 0),
        "priority_c": stats.get("priorytet_c", 0),
        "priority_x": stats.get("priorytet_x", 0),
        "brevo_export": len(brevo_all),
        "test_050": len(test_050),
        "test_100": len(test_100),
        "export_a": len(brevo_a),
        "export_b": len(brevo_b),
        "export_c": len(brevo_c),
        "false_positive_suspicion": false_positive_count,
        "segment_counts": segment_counts,
        "elapsed_seconds": elapsed,
    }
    write_report(result)
    return result


def parse_args(argv: list[str] | None = None) -> RunOptions:
    parser = argparse.ArgumentParser(
        description="Przygotowanie bazy CEIDG do mailingu B2B (Footing System).",
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Skanuj pliki wejściowe i zapisz rozpoznanie, bez przetwarzania rekordów.",
    )
    parser.add_argument(
        "--allow-spreadsheet",
        action="store_true",
        help="Zezwól na odczyt plików .ods i .xlsx (domyślnie sprint: tylko CSV).",
    )
    args = parser.parse_args(argv)
    return RunOptions(scan_only=args.scan_only, allow_spreadsheet=args.allow_spreadsheet)


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    print("=== Footing System – prepare_ceidg_mailing ===")
    if options.allow_spreadsheet:
        print("Tryb wejścia: CSV + arkusze (.ods, .xlsx)")
    else:
        print("Tryb wejścia: CSV only")
    if options.scan_only:
        print("Skan: wszystkie pliki; przetwarzanie: tylko CSV (tryb --scan-only bez zapisu wyników)")
    print()
    stats = process_ceidg(options)
    print()
    print("=== Podsumowanie ===")
    print(f"Pliki w 00-inbox/input:  {stats['inbox_files']}")
    print(f"Rozpoznane jako CEIDG:   {stats['ceidg_recognized']}")
    if stats.get("scan_only"):
        print("Przetwarzanie:           pominięte (--scan-only)")
    else:
        processed = stats.get("processed_files") or []
        if processed:
            print(f"Przetworzony plik:       {', '.join(processed)}")
        else:
            print("Przetworzony plik:       (brak)")
        print(f"Rekordy wejściowe:       {stats['input_rows']}")
        print(f"Rekordy bez e-maila:     {stats.get('rekordy_bez_emaila', 0)}")
        print(f"Poprawne e-maile:        {stats['valid_emails']}")
        print(f"Błędne e-maile:          {stats.get('rekordy_zly_email', 0)}")
        print(f"Po czyszczeniu (z email): {stats['clean_rows']}")
        print(f"Duplikaty usunięte:      {stats['duplicates_removed']}")
        print(f"Priorytet A:             {stats['priority_a']}")
        print(f"Priorytet B:             {stats['priority_b']}")
        print(f"Priorytet C:             {stats['priority_c']}")
        print(f"Priorytet X:             {stats['priority_x']}")
        print(f"Do sprawdzenia:          {stats.get('review_count', 0)}")
        print(f"BREVO-CEIDG-001:         {stats['brevo_export']}")
        print(f"TEST-050-v2:             {stats.get('test_050', 0)}")
        print(f"TEST-100-v2:             {stats.get('test_100', 0)}")
        print(f"False positive (audyt):  {stats.get('false_positive_suspicion', 0)}")
        print(f"Czas przetwarzania:      {stats.get('elapsed_seconds', 0):.1f} s")
        print()
        print("Segmenty (rekordy z e-mailem):")
        for seg, cnt in stats["segment_counts"].most_common():
            if seg:
                print(f"  {seg}: {cnt}")
        print()
        print(f"Brevo:   {MARKETING_OUT / 'BREVO-CEIDG-001.csv'}")
        print(f"Raport:  {REPORTS / 'CEIDG-MAILING-001.md'}")
    print(f"Kontrola rozpoznania: {INPUT_ROZPOZNANIE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
