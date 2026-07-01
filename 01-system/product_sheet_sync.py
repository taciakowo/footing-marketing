#!/usr/bin/env python3
"""Read-only sync Product Master z Google Sheets → lokalne snapshoty Footing System."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from footing_csv import write_csv  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "00-inbox"
DOCS_DIR = ROOT / "04-produkty"
DEFAULT_OUTPUT_DIR = ROOT / "02-output-private" / "produkty"
CREDENTIALS_PATH = INBOX / "google_credentials.json"
TOKEN_PATH = INBOX / "google_token_sheets.json"

DEFAULT_SPREADSHEET_ID = "1YtWrOgyJgNXFYaSg5-TeApJOOP3R25b9b62TT7lZqXE"
DEFAULT_SHEET_NAME = "baza_produktow_footing"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

VALUES_OUT = "PRODUKTY-GOOGLE-SHEET-VALUES.csv"
FORMULAS_OUT = "PRODUKTY-GOOGLE-SHEET-FORMULAS.csv"
VALIDATIONS_OUT = "PRODUKTY-GOOGLE-SHEET-VALIDATIONS.csv"
BRAKI_OUT = "PRODUKTY-BRAKI.csv"
RAPORT_OUT = "PRODUKTY-RAPORT.md"
WOO_OUT = "PRODUKTY-WOO-EXPORT.csv"

FORMULA_METHOD = "userEnteredValue.formulaValue"
FORMULA_COLS = [
    "sheet_name", "row", "col", "a1", "header", "sku", "formula",
    "effective_value", "formatted_value",
]
VALIDATION_COLS = [
    "sheet_name", "row", "col", "a1", "header", "sku", "validation_type",
    "allowed_values", "source_range", "strict", "show_custom_ui", "input_message",
]
BRAKI_COLS = [
    "sku", "row", "field", "issue", "severity", "formula_present",
    "calculated_value_empty", "message",
]
WOO_EXPORT_COLS = [
    "sku", "name", "regular_price", "sale_price", "status", "stock_status",
    "short_description", "description", "categories", "tags", "weight",
    "length", "width", "height", "image_main", "drawing", "permalink",
    "Zbrojenie", "Blacha podstawy", "Śruby mocujące", "Peszel", "Wykop",
    "Max wysokość urządzenia", "Pasuje do",
]

FIELD_ALIASES: dict[str, list[str]] = {
    "sku": ["sku", "SKU", "kod", "kod produktu"],
    "name": ["name", "Name", "nazwa", "Nazwa", "product_name"],
    "regular_price": ["regular_price", "price", "cena_netto", "Cena netto", "cena netto", "cena"],
    "status": ["status", "Status", "post_status"],
    "stock_status": ["stock_status", "Stock status", "stan magazynowy"],
    "permalink": ["permalink", "Permalink", "url", "link"],
    "image_main": ["image_main", "Image main", "zdjecie", "zdjęcie", "image", "main_image"],
    "drawing": ["drawing", "Drawing", "rysunek", "Rysunek"],
    "categories": ["categories", "Categories", "kategorie", "Kategorie"],
    "short_description": ["short_description", "Short description", "krotki opis", "krótki opis"],
    "description": ["description", "Description", "opis", "Opis"],
    "weight": ["weight", "Weight", "waga", "Waga"],
    "dimensions": ["dimensions", "Dimensions", "wymiary", "Wymiary"],
    "length": ["length", "Length", "dlugosc", "długość"],
    "width": ["width", "Width", "szerokosc", "szerokość"],
    "height": ["height", "Height", "wysokosc", "wysokość"],
    "Zbrojenie": ["Zbrojenie", "zbrojenie"],
    "Blacha podstawy": ["Blacha podstawy", "blacha podstawy"],
    "Śruby mocujące": ["Śruby mocujące", "Sruby mocujace", "śruby mocujące"],
    "Peszel": ["Peszel", "peszel"],
    "Wykop": ["Wykop", "wykop"],
    "Max wysokość urządzenia": [
        "Max wysokość urządzenia", "Max wysokosc urzadzenia", "max wysokość urządzenia",
    ],
    "Pasuje do": ["Pasuje do", "pasuje do"],
}

TECH_PARAM_FIELDS = [
    "Zbrojenie", "Blacha podstawy", "Śruby mocujące", "Peszel", "Wykop",
    "Max wysokość urządzenia", "Pasuje do",
]

CRITICAL_CHECKS = [
    ("sku", "brak sku"),
    ("name", "brak name lub Nazwa"),
    ("regular_price", "brak ceny"),
    ("status", "brak status"),
    ("stock_status", "brak stock_status"),
]
PUBLISH_CHECKS = [
    ("permalink", "brak permalink dla produktu publish"),
    ("image_main", "brak image_main"),
    ("drawing", "brak drawing"),
    ("categories", "brak categories"),
    ("short_description", "brak short_description"),
    ("weight", "brak weight"),
    ("dimensions", "brak dimensions"),
]


@dataclass
class RunOptions:
    spreadsheet_id: str = DEFAULT_SPREADSHEET_ID
    sheet_name: str = DEFAULT_SHEET_NAME
    input_csv: Path | None = None
    output_dir: Path = DEFAULT_OUTPUT_DIR
    snapshot_only: bool = False
    audit: bool = False
    export_woo: bool = False
    inspect_formulas: bool = False
    inspect_validations: bool = False
    debug_cells: list[str] = field(default_factory=list)
    debug_formulas_limit: int = 0


@dataclass
class SheetSnapshot:
    headers: list[str]
    rows: list[list[str]]
    source_mode: str
    api_ok: bool = False
    api_error: str = ""
    formulas_available: int = 0
    validations_available: int = 0
    formula_cells: list[dict[str, str]] = field(default_factory=list)
    validation_cells: list[dict[str, str]] = field(default_factory=list)
    raw_rows_count: int = 0
    product_rows_count: int = 0
    inspected_cells_count: int = 0
    full_values_grid: list[list[str]] = field(default_factory=list)


@dataclass
class RunStats:
    api_ok: bool = False
    api_error: str = ""
    source_mode: str = "api"
    row_count: int = 0
    column_count: int = 0
    raw_rows_count: int = 0
    product_rows_count: int = 0
    inspected_cells_count: int = 0
    formula_count: int = 0
    validation_count: int = 0
    formulas_read_active: bool = False
    formula_method: str = ""
    critical_gaps: int = 0
    warning_gaps: int = 0
    duplicate_sku: int = 0
    files_written: list[str] = field(default_factory=list)


def normalize_header(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())


def col_index_to_a1(col_idx: int) -> str:
    """0-based column index → A1 notation column letters."""
    n = col_idx + 1
    letters = ""
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def a1_notation(row: int, col: int) -> str:
    return f"{col_index_to_a1(col)}{row}"


A1_ADDRESS_RE = re.compile(r"^([A-Za-z]+)(\d+)$")


def parse_a1_address(address: str) -> tuple[int, int]:
    """A1 → (wiersz 1-based, kolumna 0-based)."""
    match = A1_ADDRESS_RE.match((address or "").strip())
    if not match:
        raise ValueError(f"Niepoprawny adres komórki: {address!r}")
    col_letters, row_str = match.groups()
    col = 0
    for ch in col_letters.upper():
        col = col * 26 + (ord(ch) - 64)
    return int(row_str), col - 1


def extended_value_to_str(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    if "stringValue" in value:
        return str(value["stringValue"])
    if "numberValue" in value:
        num = value["numberValue"]
        if isinstance(num, float) and num.is_integer():
            return str(int(num))
        return str(num)
    if "boolValue" in value:
        return str(value["boolValue"]).lower()
    if "formulaValue" in value:
        return str(value["formulaValue"])
    return ""


def count_product_rows(headers: list[str], raw_rows: list[list[str]]) -> int:
    header_map = build_header_map(headers)
    sku_col = resolve_column(header_map, "sku")
    if sku_col is None:
        return sum(1 for row in raw_rows if any(cell for cell in row))
    return sum(1 for row in raw_rows if cell_value(row, sku_col))


def build_header_map(headers: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, header in enumerate(headers):
        h = normalize_header(header)
        if h:
            mapping[h] = idx
    return mapping


def resolve_column(header_map: dict[str, int], field_key: str) -> int | None:
    for alias in FIELD_ALIASES.get(field_key, [field_key]):
        idx = header_map.get(normalize_header(alias))
        if idx is not None:
            return idx
    return None


def cell_value(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def is_empty(value: str) -> bool:
    return not (value or "").strip()


def is_publish_status(status: str) -> bool:
    return (status or "").strip().lower() in {"publish", "published", "opublikowany", "public"}


def read_local_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1250"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    for delim in (";", ",", "\t"):
        try:
            reader = csv.reader(StringIO(text), delimiter=delim)
            rows = list(reader)
            if rows and len(rows[0]) >= 2:
                headers = [normalize_header(h) for h in rows[0]]
                data = [[(c or "").strip() for c in r] for r in rows[1:] if any((x or "").strip() for x in r)]
                return headers, data
        except csv.Error:
            continue
    return [], []


def get_credentials():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError(
            "Brak bibliotek Google API. Uruchom: pip install google-api-python-client google-auth-oauthlib"
        ) from exc

    if not CREDENTIALS_PATH.exists():
        raise RuntimeError(
            f"Brak pliku {CREDENTIALS_PATH}. Dodaj OAuth credentials z Google Cloud Console."
        )

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds


def build_sheets_service():
    from googleapiclient.discovery import build

    creds = get_credentials()
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def sheet_range(sheet_name: str, a1: str = "") -> str:
    quoted = sheet_name.replace("'", "''")
    if a1:
        return f"'{quoted}'!{a1}"
    return f"'{quoted}'"


def fetch_values(service, spreadsheet_id: str, sheet_name: str) -> list[list[str]]:
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=sheet_range(sheet_name),
        valueRenderOption="FORMATTED_VALUE",
    ).execute()
    values = result.get("values") or []
    return [[(c or "").strip() for c in row] for row in values]


def fetch_grid_row_data(service, spreadsheet_id: str, sheet_name: str) -> list[dict[str, Any]]:
    response = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[sheet_range(sheet_name)],
        includeGridData=True,
        fields=(
            "sheets.data.rowData.values("
            "userEnteredValue,effectiveValue,formattedValue,dataValidation"
            ")"
        ),
    ).execute()
    sheets = response.get("sheets") or []
    if not sheets:
        return []
    return (sheets[0].get("data") or [{}])[0].get("rowData") or []


def fetch_formulas_from_grid(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    headers: list[str],
    full_values_grid: list[list[str]],
    sku_col: int | None,
    row_data: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, str]], int]:
    """Metoda B: userEnteredValue.formulaValue z includeGridData."""
    if row_data is None:
        row_data = fetch_grid_row_data(service, spreadsheet_id, sheet_name)
    rows_out: list[dict[str, str]] = []
    inspected = 0

    for r_idx, row in enumerate(row_data):
        values = row.get("values") or []
        for c_idx, cell in enumerate(values):
            inspected += 1
            entered = cell.get("userEnteredValue") or {}
            formula = (entered.get("formulaValue") or "").strip()
            if not formula:
                continue

            header = headers[c_idx] if c_idx < len(headers) else ""
            sku = ""
            if r_idx >= 1 and r_idx < len(full_values_grid) and sku_col is not None:
                sku = cell_value(full_values_grid[r_idx], sku_col)

            rows_out.append({
                "sheet_name": sheet_name,
                "row": str(r_idx + 1),
                "col": str(c_idx + 1),
                "a1": a1_notation(r_idx + 1, c_idx),
                "header": header,
                "sku": sku,
                "formula": formula,
                "effective_value": extended_value_to_str(cell.get("effectiveValue")),
                "formatted_value": (cell.get("formattedValue") or "").strip(),
            })
    return rows_out, inspected


def debug_print_cell(
    service,
    options: RunOptions,
    address: str,
    snapshot: SheetSnapshot,
) -> None:
    row_num, col_idx = parse_a1_address(address)
    row_data = fetch_grid_row_data(service, options.spreadsheet_id, options.sheet_name)
    grid_row_idx = row_num - 1
    if grid_row_idx >= len(row_data):
        print(f"=== debug-cell {address.upper()} ===")
        print("Komórka poza zakresem danych arkusza.")
        return

    values = row_data[grid_row_idx].get("values") or []
    if col_idx >= len(values):
        print(f"=== debug-cell {address.upper()} ===")
        print("Komórka poza zakresem kolumn w wierszu.")
        return

    cell = values[col_idx]
    entered = cell.get("userEnteredValue") or {}
    header = snapshot.headers[col_idx] if col_idx < len(snapshot.headers) else ""
    sku = ""
    header_map = build_header_map(snapshot.headers)
    sku_col = resolve_column(header_map, "sku")
    if row_num >= 2 and snapshot.full_values_grid and row_num - 1 < len(snapshot.full_values_grid):
        sku = cell_value(snapshot.full_values_grid[row_num - 1], sku_col)

    print(f"=== debug-cell {address.upper()} ===")
    print(f"A1 address:     {address.upper()}")
    print(f"header:         {header or '(brak)'}")
    print(f"sku:            {sku or '(brak)'}")
    print(f"userEnteredValue: {extended_value_to_str(entered) or '(pusto)'}")
    print(f"formulaValue:   {entered.get('formulaValue') or '(brak)'}")
    print(f"effectiveValue: {extended_value_to_str(cell.get('effectiveValue')) or '(pusto)'}")
    print(f"formattedValue: {(cell.get('formattedValue') or '').strip() or '(pusto)'}")
    rule = cell.get("dataValidation")
    if rule:
        print(f"dataValidation: {_validation_type_name(rule)} strict={rule.get('strict')}")
    else:
        print("dataValidation: (brak)")
    print()


def print_formula_debug_sample(formula_cells: list[dict[str, str]], limit: int) -> None:
    if limit <= 0 or not formula_cells:
        return
    print(f"=== Pierwsze {min(limit, len(formula_cells))} formuł ===")
    for item in formula_cells[:limit]:
        formula = item.get("formula", "")
        preview = formula[:80] + ("…" if len(formula) > 80 else "")
        print(
            f"  {item.get('a1', '?')} | {item.get('header', '')} | "
            f"sku={item.get('sku', '')} | {preview}"
        )
    print()


def _validation_type_name(rule: dict[str, Any]) -> str:
    condition = rule.get("condition") or {}
    vtype = condition.get("type", "")
    mapping = {
        "ONE_OF_LIST": "lista_reczna",
        "ONE_OF_RANGE": "lista_z_zakresu",
        "BOOLEAN": "boolean",
        "NUMBER_GREATER": "number",
        "NUMBER_LESS": "number",
        "NUMBER_GREATER_THAN_EQ": "number",
        "NUMBER_LESS_THAN_EQ": "number",
        "NUMBER_EQ": "number",
        "NUMBER_NOT_EQ": "number",
        "NUMBER_BETWEEN": "number",
        "NUMBER_NOT_BETWEEN": "number",
        "TEXT_CONTAINS": "text",
        "TEXT_NOT_CONTAINS": "text",
        "TEXT_EQ": "text",
        "TEXT_NOT_EQ": "text",
        "TEXT_STARTS_WITH": "text",
        "TEXT_ENDS_WITH": "text",
        "DATE_EQ": "date",
        "DATE_BEFORE": "date",
        "DATE_AFTER": "date",
        "DATE_BETWEEN": "date",
        "CUSTOM_FORMULA": "formula_niestandardowa",
    }
    return mapping.get(vtype, vtype or "inny_typ")


def _grid_range_to_a1(grid_range: dict[str, Any], sheet_title: str) -> str:
    start_row = (grid_range.get("startRowIndex") or 0) + 1
    end_row = grid_range.get("endRowIndex")
    start_col = (grid_range.get("startColumnIndex") or 0) + 1
    end_col = grid_range.get("endColumnIndex")
    start_a1 = f"{col_index_to_a1(start_col - 1)}{start_row}"
    if end_row is None or end_col is None:
        return f"'{sheet_title}'!{start_a1}"
    end_a1 = f"{col_index_to_a1(end_col - 1)}{end_row}"
    return f"'{sheet_title}'!{start_a1}:{end_a1}"


def _fetch_range_values(service, spreadsheet_id: str, grid_range: dict[str, Any]) -> list[str]:
    sheet_id = grid_range.get("sheetId")
    if sheet_id is None:
        return []
    meta = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties(sheetId,title)",
    ).execute()
    title = ""
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties") or {}
        if props.get("sheetId") == sheet_id:
            title = props.get("title") or ""
            break
    if not title:
        return []
    a1 = _grid_range_to_a1(grid_range, title)
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=a1,
        valueRenderOption="FORMATTED_VALUE",
    ).execute()
    out: list[str] = []
    for row in result.get("values") or []:
        for cell in row:
            val = (cell or "").strip()
            if val and val not in out:
                out.append(val)
    return out


def fetch_validations(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    headers: list[str],
    data_rows: list[list[str]],
    sku_col: int | None,
    row_data: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    if row_data is None:
        row_data = fetch_grid_row_data(service, spreadsheet_id, sheet_name)

    validations: list[dict[str, str]] = []
    seen: set[tuple[int, int]] = set()

    for r_idx, row in enumerate(row_data):
        values = row.get("values") or []
        for c_idx, cell in enumerate(values):
            rule = cell.get("dataValidation")
            if not rule:
                continue
            key = (r_idx, c_idx)
            if key in seen:
                continue
            seen.add(key)

            condition = rule.get("condition") or {}
            vtype = _validation_type_name(rule)
            allowed: list[str] = []
            source_range = ""

            if condition.get("type") == "ONE_OF_LIST":
                for item in condition.get("values") or []:
                    val = (item or {}).get("userEnteredValue") or (item or {}).get("value")
                    if val is not None and str(val).strip():
                        allowed.append(str(val).strip())
            elif condition.get("type") == "ONE_OF_RANGE":
                values_meta = condition.get("values") or []
                if values_meta:
                    first = values_meta[0] or {}
                    entered = first.get("userEnteredValue") or {}
                    formula_ref = entered.get("formulaValue")
                    if formula_ref:
                        source_range = str(formula_ref)
                    grid = first.get("relativeRange") or entered.get("range")
                    if isinstance(grid, dict):
                        source_range = source_range or _grid_range_to_a1(grid, sheet_name)
                        allowed = _fetch_range_values(service, spreadsheet_id, grid)

            header = headers[c_idx] if c_idx < len(headers) else ""
            sku = ""
            if r_idx >= 1 and sku_col is not None:
                data_row = data_rows[r_idx - 1] if r_idx - 1 < len(data_rows) else []
                sku = cell_value(data_row, sku_col)

            validations.append({
                "sheet_name": sheet_name,
                "row": str(r_idx + 1),
                "col": str(c_idx + 1),
                "a1": a1_notation(r_idx + 1, c_idx),
                "header": header,
                "sku": sku,
                "validation_type": vtype,
                "allowed_values": " | ".join(allowed),
                "source_range": source_range,
                "strict": str(rule.get("strict", "")),
                "show_custom_ui": str(rule.get("showCustomUi", "")),
                "input_message": (rule.get("inputMessage") or "").replace("\n", " "),
            })
    return validations


def load_snapshot(options: RunOptions) -> SheetSnapshot:
    if options.input_csv:
        headers, rows = read_local_csv(options.input_csv)
        return SheetSnapshot(
            headers=headers,
            rows=rows,
            source_mode="csv",
            api_ok=True,
            formulas_available=0,
            validations_available=0,
            raw_rows_count=len(rows),
            product_rows_count=count_product_rows(headers, rows),
        )

    try:
        service = build_sheets_service()
        values_grid = fetch_values(service, options.spreadsheet_id, options.sheet_name)
        if not values_grid:
            return SheetSnapshot(
                headers=[],
                rows=[],
                source_mode="api",
                api_ok=False,
                api_error="Arkusz pusty lub brak dostępu.",
            )

        headers = [normalize_header(h) for h in values_grid[0]]
        raw_rows = values_grid[1:]
        rows = [row for row in raw_rows if any(cell for cell in row)]
        snapshot = SheetSnapshot(
            headers=headers,
            rows=rows,
            source_mode="api",
            api_ok=True,
            raw_rows_count=len(raw_rows),
            product_rows_count=count_product_rows(headers, raw_rows),
            full_values_grid=values_grid,
        )
        return snapshot
    except Exception as exc:
        return SheetSnapshot(
            headers=[],
            rows=[],
            source_mode="api",
            api_ok=False,
            api_error=str(exc),
        )


def enrich_from_api(
    snapshot: SheetSnapshot,
    options: RunOptions,
    do_formulas: bool,
    do_validations: bool,
) -> None:
    if options.input_csv or not snapshot.api_ok:
        return
    try:
        service = build_sheets_service()
        header_map = build_header_map(snapshot.headers)
        sku_col = resolve_column(header_map, "sku")
        full_grid = snapshot.full_values_grid or [snapshot.headers] + snapshot.rows

        row_data: list[dict[str, Any]] | None = None
        if do_formulas or do_validations:
            row_data = fetch_grid_row_data(service, options.spreadsheet_id, options.sheet_name)

        if do_formulas:
            snapshot.formula_cells, snapshot.inspected_cells_count = fetch_formulas_from_grid(
                service,
                options.spreadsheet_id,
                options.sheet_name,
                snapshot.headers,
                full_grid,
                sku_col,
                row_data=row_data,
            )
            snapshot.formulas_available = 1

        if do_validations:
            snapshot.validation_cells = fetch_validations(
                service,
                options.spreadsheet_id,
                options.sheet_name,
                snapshot.headers,
                snapshot.rows,
                sku_col,
                row_data=row_data,
            )
            snapshot.validations_available = 1
            if not do_formulas and row_data is not None:
                inspected = 0
                for row in row_data:
                    inspected += len(row.get("values") or [])
                snapshot.inspected_cells_count = inspected

        for address in options.debug_cells:
            debug_print_cell(service, options, address, snapshot)
    except Exception as exc:
        snapshot.api_error = snapshot.api_error or str(exc)


def build_formula_lookup(formula_cells: list[dict[str, str]]) -> dict[tuple[int, str], dict[str, str]]:
    lookup: dict[tuple[int, str], dict[str, str]] = {}
    for item in formula_cells:
        try:
            row_num = int(item.get("row", "0"))
            header = normalize_header(item.get("header", ""))
            lookup[(row_num, header)] = item
        except ValueError:
            continue
    return lookup


def audit_products(
    snapshot: SheetSnapshot,
    formula_lookup: dict[tuple[int, str], dict[str, str]],
) -> list[dict[str, str]]:
    header_map = build_header_map(snapshot.headers)
    col_by_field = {field: resolve_column(header_map, field) for field in FIELD_ALIASES}
    existing_fields = {k: v for k, v in col_by_field.items() if v is not None}

    gaps: list[dict[str, str]] = []
    sku_col = col_by_field.get("sku")
    sku_counts = Counter(
        cell_value(row, sku_col)
        for row in snapshot.rows
        if cell_value(row, sku_col)
    )
    duplicate_skus = {sku for sku, count in sku_counts.items() if count > 1}

    for row_idx, row in enumerate(snapshot.rows, start=2):
        sku = cell_value(row, sku_col)

        status = cell_value(row, col_by_field.get("status"))
        publish = is_publish_status(status)

        def add_gap(field: str, issue: str, severity: str, formula_present: str = "0", calc_empty: str = "0"):
            gaps.append({
                "sku": sku,
                "row": str(row_idx),
                "field": field,
                "issue": issue,
                "severity": severity,
                "formula_present": formula_present,
                "calculated_value_empty": calc_empty,
                "message": issue,
            })

        if not sku:
            add_gap("sku", "brak sku", "critical")
        elif sku in duplicate_skus:
            add_gap("sku", "duplikat sku", "critical")

        for field_key, issue in CRITICAL_CHECKS:
            if field_key == "sku":
                continue
            col = existing_fields.get(field_key)
            if col is None:
                continue
            header = snapshot.headers[col]
            value = cell_value(row, col)
            formula_item = formula_lookup.get((row_idx, normalize_header(header)))
            if is_empty(value):
                if formula_item:
                    add_gap(field_key, issue, "warning", "1", "1")
                else:
                    add_gap(field_key, issue, "critical")

        if publish:
            for field_key, issue in PUBLISH_CHECKS:
                col = existing_fields.get(field_key)
                if col is None and field_key == "dimensions":
                    has_dim = any(existing_fields.get(k) is not None for k in ("length", "width", "height"))
                    if not has_dim:
                        add_gap(field_key, issue, "critical")
                    continue
                if col is None:
                    continue
                header = snapshot.headers[col]
                value = cell_value(row, col)
                if field_key == "dimensions":
                    if is_empty(value):
                        parts = [
                            cell_value(row, existing_fields.get("length")),
                            cell_value(row, existing_fields.get("width")),
                            cell_value(row, existing_fields.get("height")),
                        ]
                        if not any(parts):
                            formula_item = formula_lookup.get((row_idx, normalize_header(header)))
                            if formula_item:
                                add_gap(field_key, issue, "warning", "1", "1")
                            else:
                                add_gap(field_key, issue, "critical")
                    continue
                if is_empty(value):
                    formula_item = formula_lookup.get((row_idx, normalize_header(header)))
                    if formula_item:
                        add_gap(field_key, issue, "warning", "1", "1")
                    else:
                        add_gap(field_key, issue, "critical")

        for field_key in TECH_PARAM_FIELDS:
            col = existing_fields.get(field_key)
            if col is None:
                continue
            header = snapshot.headers[col]
            value = cell_value(row, col)
            if is_empty(value):
                formula_item = formula_lookup.get((row_idx, normalize_header(header)))
                if formula_item:
                    add_gap(field_key, f"brak parametru: {field_key}", "warning", "1", "1")
                else:
                    add_gap(field_key, f"brak parametru: {field_key}", "warning")

    return gaps


def build_woo_export(snapshot: SheetSnapshot) -> list[dict[str, str]]:
    header_map = build_header_map(snapshot.headers)
    rows_out: list[dict[str, str]] = []

    for row in snapshot.rows:
        sku = cell_value(row, resolve_column(header_map, "sku"))
        if not sku:
            continue
        record: dict[str, str] = {}
        for col_name in WOO_EXPORT_COLS:
            idx = resolve_column(header_map, col_name)
            record[col_name] = cell_value(row, idx)
        if not record.get("name"):
            record["name"] = cell_value(row, resolve_column(header_map, "name"))
        rows_out.append(record)
    return rows_out


def write_values_snapshot(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    columns = headers[:]
    dict_rows = []
    for row in rows:
        dict_rows.append({columns[i]: row[i] if i < len(row) else "" for i in range(len(columns))})
    write_csv(path, columns, dict_rows)


def write_report(path: Path, stats: RunStats, snapshot: SheetSnapshot, options: RunOptions) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Produkty – raport synchronizacji Google Sheet",
        "",
        f"Wygenerowano: {now}",
        "",
        "## Źródło",
        "",
        f"- Spreadsheet ID: `{options.spreadsheet_id}`",
        f"- Zakładka: `{options.sheet_name}`",
        f"- Tryb: `{snapshot.source_mode}`",
        f"- API Google Sheets: {'tak' if snapshot.source_mode == 'api' and stats.api_ok else 'nie' if snapshot.source_mode == 'api' else 'n/d (csv)'}",
    ]
    if stats.api_error:
        lines.append(f"- Błąd API: {stats.api_error}")
    lines.extend([
        "",
        "## Statystyki",
        "",
        f"| Metryka | Wartość |",
        f"|---|---:|",
        f"| source_mode | {stats.source_mode} |",
        f"| raw_rows_count | {stats.raw_rows_count} |",
        f"| product_rows_count | {stats.product_rows_count} |",
        f"| Wiersze w snapshocie CSV | {stats.row_count} |",
        f"| columns_count | {stats.column_count} |",
        f"| inspected_cells_count | {stats.inspected_cells_count} |",
        f"| formulas_available | {snapshot.formulas_available} |",
        f"| formulas_found | {stats.formula_count} |",
        f"| method | {stats.formula_method or 'n/d'} |",
        f"| validations_found | {stats.validation_count} |",
        f"| Braki krytyczne | {stats.critical_gaps} |",
        f"| Braki ostrzegawcze | {stats.warning_gaps} |",
        f"| Duplikaty SKU | {stats.duplicate_sku} |",
        "",
        "### Wyjaśnienie wierszy",
        "",
        "- **raw_rows_count** – wszystkie wiersze danych z arkusza (bez nagłówka).",
        "- **product_rows_count** – wiersze z niepustym SKU (lub niepuste, gdy brak kolumny SKU).",
        "- **Wiersze w snapshocie CSV** – wiersze zapisane do VALUES (niepuste komórki w wierszu).",
        "",
        "CSV prywatne używają separatora `;` (Import-Csv ... -Delimiter ';').",
        "",
        "## Pliki prywatne",
        "",
    ])
    for fpath in stats.files_written:
        lines.append(f"- `{fpath}`")
    lines.extend([
        "",
        "## Zasady",
        "",
        "- Google Sheet pozostaje źródłem prawdy (read-only z Footing System).",
        "- Formuły i listy rozwijane w arkuszu są zachowane – system ich nie nadpisuje.",
        "- WooCommerce jest miejscem publikacji, nie źródłem prawdy.",
        "- Eksport Woo (`PRODUKTY-WOO-EXPORT.csv`) jest roboczy – bez automatycznej publikacji.",
        "",
    ])
    if snapshot.source_mode == "csv":
        lines.extend([
            "## Tryb CSV",
            "",
            "- `formulas_available = 0`",
            "- `validations_available = 0`",
            "- `source_mode = csv`",
            "",
        ])
    elif stats.formulas_read_active and stats.formula_count == 0:
        lines.extend([
            "## Formuły",
            "",
            f"- `formulas_available = 1`",
            f"- `formulas_found = 0`",
            f"- `method = {FORMULA_METHOD}`",
            "",
            "Odczyt formuł działa – w zakresie nie wykryto komórek z formulaValue.",
            "",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> RunOptions:
    parser = argparse.ArgumentParser(
        description="Read-only sync Product Master z Google Sheets (Footing System).",
    )
    parser.add_argument("--spreadsheet-id", default=DEFAULT_SPREADSHEET_ID)
    parser.add_argument("--sheet-name", default=DEFAULT_SHEET_NAME)
    parser.add_argument("--input-csv", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--snapshot-only", action="store_true")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--export-woo", action="store_true")
    parser.add_argument("--inspect-formulas", action="store_true")
    parser.add_argument("--inspect-validations", action="store_true")
    parser.add_argument(
        "--debug-cell",
        action="append",
        default=[],
        metavar="A1",
        help="Diagnostyka pojedynczej komórki (konsola), np. --debug-cell B2",
    )
    parser.add_argument(
        "--debug-formulas-limit",
        type=int,
        default=0,
        help="Wypisz pierwsze N formuł na konsolę",
    )
    args = parser.parse_args(argv)

    action_flags = (
        args.snapshot_only,
        args.audit,
        args.export_woo,
        args.inspect_formulas,
        args.inspect_validations,
    )
    if not any(action_flags):
        return RunOptions(
            spreadsheet_id=args.spreadsheet_id,
            sheet_name=args.sheet_name,
            input_csv=args.input_csv,
            output_dir=args.output_dir,
            snapshot_only=True,
            audit=True,
            export_woo=True,
            inspect_formulas=True,
            inspect_validations=True,
            debug_cells=[c.strip() for c in args.debug_cell if c.strip()],
            debug_formulas_limit=max(0, args.debug_formulas_limit),
        )

    return RunOptions(
        spreadsheet_id=args.spreadsheet_id,
        sheet_name=args.sheet_name,
        input_csv=args.input_csv,
        output_dir=args.output_dir,
        snapshot_only=args.snapshot_only,
        audit=args.audit,
        export_woo=args.export_woo,
        inspect_formulas=args.inspect_formulas,
        inspect_validations=args.inspect_validations,
        debug_cells=[c.strip() for c in args.debug_cell if c.strip()],
        debug_formulas_limit=max(0, args.debug_formulas_limit),
    )


def run(options: RunOptions) -> RunStats:
    options.output_dir.mkdir(parents=True, exist_ok=True)
    stats = RunStats(source_mode="csv" if options.input_csv else "api")

    do_snapshot = (
        options.snapshot_only
        or options.audit
        or options.export_woo
        or not any((
            options.inspect_formulas,
            options.inspect_validations,
        ))
    )
    do_formulas = options.inspect_formulas or options.audit
    do_validations = options.inspect_validations
    need_grid = do_formulas or do_validations or bool(options.debug_cells)

    snapshot = load_snapshot(options)
    stats.api_ok = snapshot.api_ok
    stats.api_error = snapshot.api_error
    stats.source_mode = snapshot.source_mode

    if snapshot.api_ok and snapshot.source_mode == "api" and need_grid:
        enrich_from_api(snapshot, options, do_formulas, do_validations)

    if options.input_csv:
        snapshot.formulas_available = 0

    if snapshot.api_ok:
        stats.row_count = len(snapshot.rows)
        stats.column_count = len(snapshot.headers)
        stats.raw_rows_count = snapshot.raw_rows_count
        stats.product_rows_count = snapshot.product_rows_count
        stats.inspected_cells_count = snapshot.inspected_cells_count
        stats.formula_count = len(snapshot.formula_cells)
        stats.validation_count = len(snapshot.validation_cells)
        stats.formulas_read_active = bool(
            snapshot.formulas_available and snapshot.source_mode == "api" and do_formulas
        )
        stats.formula_method = FORMULA_METHOD if snapshot.formulas_available else ""

    if do_snapshot and snapshot.api_ok and snapshot.headers:
        values_path = options.output_dir / VALUES_OUT
        write_values_snapshot(values_path, snapshot.headers, snapshot.rows)
        stats.files_written.append(str(values_path))

    if options.inspect_formulas and snapshot.api_ok:
        formulas_path = options.output_dir / FORMULAS_OUT
        write_csv(formulas_path, FORMULA_COLS, snapshot.formula_cells)
        stats.files_written.append(str(formulas_path))

    if do_validations and snapshot.validation_cells:
        validations_path = options.output_dir / VALIDATIONS_OUT
        write_csv(validations_path, VALIDATION_COLS, snapshot.validation_cells)
        stats.files_written.append(str(validations_path))

    formula_lookup = build_formula_lookup(snapshot.formula_cells)
    gaps: list[dict[str, str]] = []
    if options.audit and snapshot.api_ok:
        gaps = audit_products(snapshot, formula_lookup)
        stats.critical_gaps = sum(1 for g in gaps if g["severity"] == "critical")
        stats.warning_gaps = sum(1 for g in gaps if g["severity"] == "warning")
        stats.duplicate_sku = sum(1 for g in gaps if g["issue"] == "duplikat sku")
        braki_path = options.output_dir / BRAKI_OUT
        write_csv(braki_path, BRAKI_COLS, gaps)
        stats.files_written.append(str(braki_path))

    if options.export_woo and snapshot.api_ok:
        woo_rows = build_woo_export(snapshot)
        woo_path = options.output_dir / WOO_OUT
        write_csv(woo_path, WOO_EXPORT_COLS, woo_rows)
        stats.files_written.append(str(woo_path))

    if snapshot.api_ok and (options.audit or do_snapshot or options.inspect_formulas):
        report_path = options.output_dir / RAPORT_OUT
        write_report(report_path, stats, snapshot, options)
        stats.files_written.append(str(report_path))

    if options.debug_formulas_limit > 0 and snapshot.formula_cells:
        print_formula_debug_sample(snapshot.formula_cells, options.debug_formulas_limit)

    return stats


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    print("=== Footing System – product_sheet_sync (read-only) ===")
    print(f"Spreadsheet: {options.spreadsheet_id}")
    print(f"Zakładka:    {options.sheet_name}")
    if options.input_csv:
        print(f"Tryb CSV:    {options.input_csv}")
    else:
        print("Tryb:        Google Sheets API")
    print(f"Output:      {options.output_dir}")
    print()

    stats = run(options)
    print("=== Podsumowanie ===")
    if stats.source_mode == "csv":
        print(f"Odczyt CSV:              {'tak' if stats.api_ok else 'nie'}")
    else:
        print(f"API Google Sheets:       {'tak' if stats.api_ok else 'nie'}")
    if stats.api_error:
        print(f"Błąd API:                {stats.api_error}")
    print(f"source_mode:             {stats.source_mode}")
    print(f"raw_rows_count:          {stats.raw_rows_count}")
    print(f"product_rows_count:      {stats.product_rows_count}")
    print(f"Wiersze snapshot CSV:    {stats.row_count}")
    print(f"columns_count:           {stats.column_count}")
    print(f"inspected_cells_count:   {stats.inspected_cells_count}")
    if stats.formulas_read_active or options.inspect_formulas:
        active = "tak" if stats.formulas_read_active else "nie"
        print(
            f"Formuły:                 {stats.formula_count} znalezionych / "
            f"odczyt formuł aktywny: {active} / "
            f"metoda: {stats.formula_method or FORMULA_METHOD}"
        )
    else:
        print(f"formulas_found:          {stats.formula_count}")
    print(f"validations_found:       {stats.validation_count}")
    print(f"Braki krytyczne:         {stats.critical_gaps}")
    print(f"Braki ostrzegawcze:      {stats.warning_gaps}")
    print("CSV prywatne: separator ;  (Import-Csv ... -Delimiter ';')")
    print()
    if stats.files_written:
        print("Zapisane pliki:")
        for path in stats.files_written:
            print(f"  {path}")
    else:
        print("Brak zapisanych plików – sprawdź dostęp do API lub podaj --input-csv.")
    return 0 if stats.api_ok else 1


if __name__ == "__main__":
    sys.exit(main())
