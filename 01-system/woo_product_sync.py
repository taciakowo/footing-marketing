#!/usr/bin/env python3
"""Read-only sync Product Master (Google Sheet snapshot) ↔ WooCommerce REST API."""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from footing_csv import write_csv  # noqa: E402
from product_sheet_sync import (  # noqa: E402
    build_header_map,
    cell_value,
    read_local_csv,
    resolve_column,
)

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "00-inbox"
DEFAULT_OUTPUT_DIR = ROOT / "02-output-private" / "produkty"
DEFAULT_CREDENTIALS = INBOX / "woo_credentials.json"
DEFAULT_SHEET_CSV = DEFAULT_OUTPUT_DIR / "PRODUKTY-GOOGLE-SHEET-VALUES.csv"

REMOTE_SNAPSHOT = "PRODUKTY-WOO-REMOTE-SNAPSHOT.csv"
DIFF_CSV = "PRODUKTY-WOO-DIFF.csv"
DIFF_MD = "PRODUKTY-WOO-DIFF.md"
DRY_RUN_JSON = "PRODUKTY-WOO-UPDATE-DRY-RUN.json"

WOO_API_VERSION = "wc/v3"
WOO_PER_PAGE = 100

COMPARE_FIELDS = [
    "name",
    "regular_price",
    "sale_price",
    "stock_quantity",
    "stock_status",
    "description",
    "short_description",
    "categories",
    "tags",
    "weight",
    "dimensions",
    "status",
]

REMOTE_SNAPSHOT_COLS = [
    "woo_id",
    "sku",
    "name",
    "regular_price",
    "sale_price",
    "stock_quantity",
    "stock_status",
    "description",
    "short_description",
    "categories",
    "tags",
    "weight",
    "length",
    "width",
    "height",
    "dimensions",
    "status",
    "type",
    "permalink",
]

DIFF_COLS = [
    "category",
    "sku",
    "woo_id",
    "field",
    "sheet_value",
    "woo_value",
    "message",
]

HTML_TAG_RE = re.compile(r"<[^>]+>")
WEIGHT_UNIT_RE = re.compile(r"\s*kg\s*$", re.IGNORECASE)


@dataclass
class RunOptions:
    fetch_woo: bool = False
    compare: bool = False
    dry_run: bool = False
    write: bool = False
    sku: str = ""
    limit: int = 0
    input_sheet_csv: Path = DEFAULT_SHEET_CSV
    output_dir: Path = DEFAULT_OUTPUT_DIR
    credentials_path: Path = DEFAULT_CREDENTIALS


@dataclass
class RunStats:
    woo_products_fetched: int = 0
    sheet_products: int = 0
    sku_matched: int = 0
    sheet_only: int = 0
    woo_only: int = 0
    products_with_diffs: int = 0
    field_diff_rows: int = 0
    dry_run_items: int = 0
    files_written: list[str] = field(default_factory=list)


def load_credentials(path: Path) -> dict[str, str]:
    if not path.exists():
        raise RuntimeError(
            f"Brak pliku credentials: {path}. "
            f"Wzór: 07-integracje/woocommerce/woo_credentials.example.json"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in ("store_url", "consumer_key", "consumer_secret") if not data.get(k)]
    if missing:
        raise RuntimeError(f"Credentials niekompletne ({path}): brak {', '.join(missing)}")
    store_url = str(data["store_url"]).rstrip("/")
    return {
        "store_url": store_url,
        "consumer_key": str(data["consumer_key"]).strip(),
        "consumer_secret": str(data["consumer_secret"]).strip(),
    }


def woo_request(
    creds: dict[str, str],
    endpoint: str,
    params: dict[str, str | int] | None = None,
) -> tuple[Any, dict[str, str]]:
    query = urllib.parse.urlencode(params or {})
    url = f"{creds['store_url']}/wp-json/{WOO_API_VERSION}/{endpoint.lstrip('/')}"
    if query:
        url = f"{url}?{query}"

    token = base64.b64encode(
        f"{creds['consumer_key']}:{creds['consumer_secret']}".encode()
    ).decode()
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "User-Agent": "FootingSystem/woo_product_sync (read-only)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return json.loads(body), headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"WooCommerce HTTP {exc.code}: {detail}") from exc


def flatten_woo_terms(items: Any) -> str:
    if not items:
        return ""
    names: list[str] = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                name = (item.get("name") or "").strip()
                if name:
                    names.append(name)
            elif item:
                names.append(str(item).strip())
    return ", ".join(sorted(set(names), key=str.casefold))


def format_dimensions(length: str, width: str, height: str) -> str:
    parts = [p.strip() for p in (length, width, height) if (p or "").strip()]
    if not parts:
        return ""
    if len(parts) == 3:
        return f"{parts[0]} x {parts[1]} x {parts[2]}"
    return " x ".join(parts)


def normalize_text(value: object) -> str:
    text = "" if value is None else str(value)
    text = HTML_TAG_RE.sub(" ", text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_price(value: object) -> str:
    text = normalize_text(value).replace(" ", "").replace(",", ".")
    if not text:
        return ""
    try:
        dec = Decimal(text)
        return format(dec.quantize(Decimal("0.01")), "f")
    except InvalidOperation:
        return text


def normalize_weight(value: object) -> str:
    text = normalize_text(value)
    text = WEIGHT_UNIT_RE.sub("", text).strip()
    if not text:
        return ""
    return normalize_price(text)


def normalize_stock_quantity(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    try:
        dec = Decimal(text.replace(",", "."))
        if dec == dec.to_integral_value():
            return str(int(dec))
        return format(dec.normalize(), "f")
    except InvalidOperation:
        return text


def normalize_status(value: object) -> str:
    return normalize_text(value).lower()


def normalize_stock_status(value: object) -> str:
    return normalize_text(value).lower()


def normalize_categories_tags(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    parts = re.split(r"[;,|]", text)
    cleaned = sorted({p.strip() for p in parts if p.strip()}, key=str.casefold)
    return ", ".join(cleaned)


def normalize_dimensions_value(value: object) -> str:
    text = normalize_text(value).lower()
    text = text.replace("×", "x").replace("*", "x")
    text = re.sub(r"\s*x\s*", " x ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def woo_product_to_row(product: dict[str, Any]) -> dict[str, str]:
    dims = product.get("dimensions") or {}
    length = str(dims.get("length") or "").strip()
    width = str(dims.get("width") or "").strip()
    height = str(dims.get("height") or "").strip()
    return {
        "woo_id": str(product.get("id") or ""),
        "sku": str(product.get("sku") or "").strip(),
        "name": str(product.get("name") or "").strip(),
        "regular_price": str(product.get("regular_price") or "").strip(),
        "sale_price": str(product.get("sale_price") or "").strip(),
        "stock_quantity": str(product.get("stock_quantity") if product.get("stock_quantity") is not None else ""),
        "stock_status": str(product.get("stock_status") or "").strip(),
        "description": str(product.get("description") or "").strip(),
        "short_description": str(product.get("short_description") or "").strip(),
        "categories": flatten_woo_terms(product.get("categories")),
        "tags": flatten_woo_terms(product.get("tags")),
        "weight": str(product.get("weight") or "").strip(),
        "length": length,
        "width": width,
        "height": height,
        "dimensions": format_dimensions(length, width, height),
        "status": str(product.get("status") or "").strip(),
        "type": str(product.get("type") or "").strip(),
        "permalink": str(product.get("permalink") or "").strip(),
    }


def fetch_all_woo_products(creds: dict[str, str]) -> list[dict[str, str]]:
    page = 1
    rows: list[dict[str, str]] = []
    total_pages = 1

    while page <= total_pages:
        data, headers = woo_request(
            creds,
            "products",
            {"per_page": WOO_PER_PAGE, "page": page, "status": "any"},
        )
        if not isinstance(data, list):
            raise RuntimeError(f"Nieoczekiwana odpowiedź WooCommerce na stronie {page}")

        total_pages = int(headers.get("x-wp-totalpages") or 1)
        for product in data:
            if not isinstance(product, dict):
                continue
            rows.append(woo_product_to_row(product))
        page += 1

    return rows


def load_sheet_products(path: Path) -> list[dict[str, str]]:
    headers, raw_rows = read_local_csv(path)
    if not headers:
        raise RuntimeError(f"Nie udało się wczytać arkusza CSV: {path}")

    header_map = build_header_map(headers)
    products: list[dict[str, str]] = []

    for row in raw_rows:
        sku = cell_value(row, resolve_column(header_map, "sku"))
        if not sku:
            continue

        length = cell_value(row, resolve_column(header_map, "length"))
        width = cell_value(row, resolve_column(header_map, "width"))
        height = cell_value(row, resolve_column(header_map, "height"))
        dimensions = cell_value(row, resolve_column(header_map, "dimensions"))
        if not dimensions:
            dimensions = format_dimensions(length, width, height)

        record = {
            "sku": sku,
            "name": cell_value(row, resolve_column(header_map, "name")),
            "regular_price": cell_value(row, resolve_column(header_map, "regular_price")),
            "sale_price": cell_value(row, resolve_column(header_map, "sale_price")),
            "stock_quantity": cell_value(row, resolve_column(header_map, "stock_quantity")),
            "stock_status": cell_value(row, resolve_column(header_map, "stock_status")),
            "description": cell_value(row, resolve_column(header_map, "description")),
            "short_description": cell_value(row, resolve_column(header_map, "short_description")),
            "categories": cell_value(row, resolve_column(header_map, "categories")),
            "tags": cell_value(row, resolve_column(header_map, "tags")),
            "weight": cell_value(row, resolve_column(header_map, "weight")),
            "dimensions": dimensions,
            "status": cell_value(row, resolve_column(header_map, "status")),
        }
        products.append(record)

    return products


def index_by_sku(products: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for product in products:
        sku = (product.get("sku") or "").strip()
        if not sku:
            continue
        index[sku] = product
    return index


def normalize_field(field: str, value: str) -> str:
    if field in {"regular_price", "sale_price"}:
        return normalize_price(value)
    if field == "stock_quantity":
        return normalize_stock_quantity(value)
    if field == "stock_status":
        return normalize_stock_status(value)
    if field == "status":
        return normalize_status(value)
    if field in {"categories", "tags"}:
        return normalize_categories_tags(value)
    if field == "weight":
        return normalize_weight(value)
    if field == "dimensions":
        return normalize_dimensions_value(value)
    if field in {"description", "short_description", "name"}:
        return normalize_text(value)
    return normalize_text(value)


def compare_field_values(field: str, sheet_value: str, woo_value: str) -> bool:
    return normalize_field(field, sheet_value) == normalize_field(field, woo_value)


@dataclass
class CompareResult:
    diff_rows: list[dict[str, str]]
    sheet_only_skus: list[str]
    woo_only_skus: list[str]
    matched_skus: list[str]
    skus_with_diffs: list[str]
    field_diffs_by_sku: dict[str, list[str]]


def compare_products(
    sheet_products: list[dict[str, str]],
    woo_products: list[dict[str, str]],
) -> CompareResult:
    sheet_index = index_by_sku(sheet_products)
    woo_index = index_by_sku(woo_products)

    sheet_skus = set(sheet_index)
    woo_skus = set(woo_index)
    matched = sorted(sheet_skus & woo_skus, key=str.casefold)
    sheet_only = sorted(sheet_skus - woo_skus, key=str.casefold)
    woo_only = sorted(woo_skus - sheet_skus, key=str.casefold)

    diff_rows: list[dict[str, str]] = []
    skus_with_diffs: list[str] = []
    field_diffs_by_sku: dict[str, list[str]] = {}

    for sku in sheet_only:
        diff_rows.append({
            "category": "sheet_only",
            "sku": sku,
            "woo_id": "",
            "field": "",
            "sheet_value": "",
            "woo_value": "",
            "message": "Produkt w arkuszu bez odpowiednika w WooCommerce",
        })

    for sku in woo_only:
        woo = woo_index[sku]
        diff_rows.append({
            "category": "woo_only",
            "sku": sku,
            "woo_id": woo.get("woo_id", ""),
            "field": "",
            "sheet_value": "",
            "woo_value": "",
            "message": "Produkt w WooCommerce bez odpowiednika w arkuszu",
        })

    for sku in matched:
        sheet = sheet_index[sku]
        woo = woo_index[sku]
        changed_fields: list[str] = []

        for field_name in COMPARE_FIELDS:
            sheet_val = sheet.get(field_name, "")
            woo_val = woo.get(field_name, "")
            if field_name == "dimensions" and not sheet_val:
                sheet_val = format_dimensions(
                    sheet.get("length", ""),
                    sheet.get("width", ""),
                    sheet.get("height", ""),
                )
            if compare_field_values(field_name, sheet_val, woo_val):
                continue
            changed_fields.append(field_name)
            diff_rows.append({
                "category": "field_diff",
                "sku": sku,
                "woo_id": woo.get("woo_id", ""),
                "field": field_name,
                "sheet_value": sheet_val,
                "woo_value": woo_val,
                "message": f"Różnica pola {field_name}",
            })

        if changed_fields:
            skus_with_diffs.append(sku)
            field_diffs_by_sku[sku] = changed_fields

    return CompareResult(
        diff_rows=diff_rows,
        sheet_only_skus=sheet_only,
        woo_only_skus=woo_only,
        matched_skus=matched,
        skus_with_diffs=skus_with_diffs,
        field_diffs_by_sku=field_diffs_by_sku,
    )


def write_diff_markdown(
    path: Path,
    result: CompareResult,
    sheet_path: Path,
    woo_path: Path,
    stats: RunStats,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Produkty – raport różnic Sheet ↔ WooCommerce",
        "",
        f"Wygenerowano: {now}",
        "",
        "## Źródła",
        "",
        f"- Arkusz (snapshot): `{sheet_path}`",
        f"- WooCommerce (snapshot): `{woo_path}`",
        "",
        "## Podsumowanie",
        "",
        "| Metryka | Wartość |",
        "|---|---:|",
        f"| Produkty w arkuszu (SKU) | {stats.sheet_products} |",
        f"| Produkty w WooCommerce (SKU) | {stats.woo_products_fetched} |",
        f"| SKU zgodne (w obu źródłach) | {stats.sku_matched} |",
        f"| Tylko w arkuszu | {stats.sheet_only} |",
        f"| Tylko w WooCommerce | {stats.woo_only} |",
        f"| Produkty ze różnicami pól | {stats.products_with_diffs} |",
        f"| Wiersze różnic pól | {stats.field_diff_rows} |",
        "",
        "## Porównywane pola",
        "",
        ", ".join(f"`{f}`" for f in COMPARE_FIELDS),
        "",
        "**Pominięte na tym etapie:** images, image_main, drawing, gallery, yoast, meta_data, variations.",
        "",
        "## Uwagi",
        "",
        "- Moduł jest **read-only** – brak zapisu do sklepu.",
        "- Aktualizacja WooCommerce nastąpi dopiero po akceptacji diff i dry-run.",
    ]

    if result.sheet_only_skus:
        lines.extend(["", "## Przykłady – tylko w arkuszu", ""])
        for sku in result.sheet_only_skus[:10]:
            lines.append(f"- `{sku}`")
        if len(result.sheet_only_skus) > 10:
            lines.append(f"- … i {len(result.sheet_only_skus) - 10} więcej")

    if result.woo_only_skus:
        lines.extend(["", "## Przykłady – tylko w WooCommerce", ""])
        for sku in result.woo_only_skus[:10]:
            lines.append(f"- `{sku}`")
        if len(result.woo_only_skus) > 10:
            lines.append(f"- … i {len(result.woo_only_skus) - 10} więcej")

    if result.skus_with_diffs:
        lines.extend(["", "## Przykłady – różnice pól", ""])
        for sku in result.skus_with_diffs[:10]:
            fields = ", ".join(result.field_diffs_by_sku.get(sku, []))
            lines.append(f"- `{sku}`: {fields}")
        if len(result.skus_with_diffs) > 10:
            lines.append(f"- … i {len(result.skus_with_diffs) - 10} więcej SKU")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def woo_update_value(field: str, sheet_value: str) -> object:
    if field in {"regular_price", "sale_price", "weight"}:
        val = normalize_price(sheet_value) if field != "weight" else normalize_weight(sheet_value)
        return val
    if field == "stock_quantity":
        val = normalize_stock_quantity(sheet_value)
        if not val:
            return None
        try:
            return int(Decimal(val))
        except InvalidOperation:
            return val
    if field in {"categories", "tags"}:
        names = [p.strip() for p in re.split(r"[;,|]", sheet_value) if p.strip()]
        return [{"name": name} for name in names]
    if field == "dimensions":
        parts = [p.strip() for p in re.split(r"\s*x\s*", sheet_value, flags=re.IGNORECASE) if p.strip()]
        return {
            "length": parts[0] if len(parts) > 0 else "",
            "width": parts[1] if len(parts) > 1 else "",
            "height": parts[2] if len(parts) > 2 else "",
        }
    return sheet_value


def build_dry_run_items(
    sheet_products: list[dict[str, str]],
    woo_products: list[dict[str, str]],
    compare_result: CompareResult,
    sku_filter: str = "",
    limit: int = 0,
) -> list[dict[str, Any]]:
    sheet_index = index_by_sku(sheet_products)
    woo_index = index_by_sku(woo_products)
    target_skus = compare_result.skus_with_diffs

    if sku_filter:
        target_skus = [sku for sku in target_skus if sku == sku_filter]
        if sku_filter not in target_skus and sku_filter in sheet_index and sku_filter in woo_index:
            # pojedyncze SKU bez diff – pusty payload informacyjny
            return []

    if limit > 0:
        target_skus = target_skus[:limit]

    items: list[dict[str, Any]] = []
    for sku in target_skus:
        sheet = sheet_index[sku]
        woo = woo_index[sku]
        changed_fields = compare_result.field_diffs_by_sku.get(sku, [])
        before = {f: woo.get(f, "") for f in changed_fields}
        after = {f: sheet.get(f, "") for f in changed_fields}
        payload = {f: woo_update_value(f, sheet.get(f, "")) for f in changed_fields}
        items.append({
            "sku": sku,
            "woo_id": int(woo["woo_id"]) if woo.get("woo_id", "").isdigit() else woo.get("woo_id", ""),
            "changed_fields": changed_fields,
            "before": before,
            "after": after,
            "payload": payload,
        })
    return items


def run_fetch_woo(options: RunOptions, stats: RunStats) -> Path:
    creds = load_credentials(options.credentials_path)
    rows = fetch_all_woo_products(creds)
    stats.woo_products_fetched = len(rows)
    out_path = options.output_dir / REMOTE_SNAPSHOT
    write_csv(out_path, REMOTE_SNAPSHOT_COLS, rows)
    stats.files_written.append(str(out_path))
    return out_path


def run_compare(options: RunOptions, stats: RunStats) -> CompareResult:
    sheet_path = options.input_sheet_csv
    woo_path = options.output_dir / REMOTE_SNAPSHOT

    if not sheet_path.exists():
        raise RuntimeError(f"Brak snapshotu arkusza: {sheet_path}")
    if not woo_path.exists():
        raise RuntimeError(
            f"Brak snapshotu WooCommerce: {woo_path}. Uruchom najpierw: --fetch-woo"
        )

    sheet_products = load_sheet_products(sheet_path)
    woo_rows_raw = []
    headers, raw_rows = read_local_csv(woo_path)
    for row in raw_rows:
        woo_rows_raw.append({headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))})

    stats.sheet_products = len(sheet_products)
    stats.woo_products_fetched = len(woo_rows_raw)

    result = compare_products(sheet_products, woo_rows_raw)
    stats.sku_matched = len(result.matched_skus)
    stats.sheet_only = len(result.sheet_only_skus)
    stats.woo_only = len(result.woo_only_skus)
    stats.products_with_diffs = len(result.skus_with_diffs)
    stats.field_diff_rows = sum(1 for r in result.diff_rows if r["category"] == "field_diff")

    diff_csv_path = options.output_dir / DIFF_CSV
    diff_md_path = options.output_dir / DIFF_MD
    write_csv(diff_csv_path, DIFF_COLS, result.diff_rows)
    write_diff_markdown(diff_md_path, result, sheet_path, woo_path, stats)
    stats.files_written.extend([str(diff_csv_path), str(diff_md_path)])
    return result


def run_dry_run(options: RunOptions, stats: RunStats) -> Path:
    sheet_path = options.input_sheet_csv
    woo_path = options.output_dir / REMOTE_SNAPSHOT

    if not sheet_path.exists():
        raise RuntimeError(f"Brak snapshotu arkusza: {sheet_path}")
    if not woo_path.exists():
        raise RuntimeError(
            f"Brak snapshotu WooCommerce: {woo_path}. Uruchom najpierw: --fetch-woo"
        )

    sheet_products = load_sheet_products(sheet_path)
    headers, raw_rows = read_local_csv(woo_path)
    woo_products = [
        {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        for row in raw_rows
    ]
    compare_result = compare_products(sheet_products, woo_products)
    stats.sheet_products = len(sheet_products)
    stats.woo_products_fetched = len(woo_products)
    stats.sku_matched = len(compare_result.matched_skus)
    stats.sheet_only = len(compare_result.sheet_only_skus)
    stats.woo_only = len(compare_result.woo_only_skus)
    stats.products_with_diffs = len(compare_result.skus_with_diffs)
    stats.field_diff_rows = sum(
        1 for r in compare_result.diff_rows if r["category"] == "field_diff"
    )
    items = build_dry_run_items(
        sheet_products,
        woo_products,
        compare_result,
        sku_filter=options.sku,
        limit=options.limit,
    )
    stats.dry_run_items = len(items)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "dry-run",
        "write_blocked": True,
        "message": "Write mode not implemented in this sprint.",
        "sku_filter": options.sku or None,
        "limit": options.limit or None,
        "items": items,
    }
    out_path = options.output_dir / DRY_RUN_JSON
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stats.files_written.append(str(out_path))
    return out_path


def parse_args(argv: list[str] | None = None) -> RunOptions:
    parser = argparse.ArgumentParser(
        description="Read-only porównanie Product Master (Sheet snapshot) z WooCommerce REST API.",
    )
    parser.add_argument("--fetch-woo", action="store_true", help="Pobierz produkty z WooCommerce (GET).")
    parser.add_argument("--compare", action="store_true", help="Porównaj arkusz i snapshot Woo po SKU.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Przygotuj payload aktualizacji bez wysyłki PUT/POST.",
    )
    parser.add_argument("--write", action="store_true", help="Zablokowany – brak zapisu w tym sprincie.")
    parser.add_argument("--sku", default="", help="Filtruj dry-run do jednego SKU.")
    parser.add_argument("--limit", type=int, default=0, help="Limit pozycji dry-run.")
    parser.add_argument(
        "--input-sheet-csv",
        type=Path,
        default=DEFAULT_SHEET_CSV,
        help=f"Snapshot arkusza (domyślnie: {DEFAULT_SHEET_CSV}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Katalog wyjściowy (domyślnie: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS,
        help=f"Plik credentials Woo (domyślnie: {DEFAULT_CREDENTIALS}).",
    )
    args = parser.parse_args(argv)

    if args.write:
        print("Write mode not implemented in this sprint.", file=sys.stderr)
        sys.exit(1)

    if not any((args.fetch_woo, args.compare, args.dry_run)):
        parser.error("Podaj co najmniej jeden tryb: --fetch-woo, --compare lub --dry-run")

    return RunOptions(
        fetch_woo=args.fetch_woo,
        compare=args.compare,
        dry_run=args.dry_run,
        write=args.write,
        sku=args.sku.strip(),
        limit=max(0, args.limit),
        input_sheet_csv=args.input_sheet_csv,
        output_dir=args.output_dir,
        credentials_path=args.credentials,
    )


def print_summary(stats: RunStats) -> None:
    print("")
    print("=== Podsumowanie woo_product_sync ===")
    if stats.woo_products_fetched:
        print(f"Produkty WooCommerce (pobrane / w snapshot): {stats.woo_products_fetched}")
    if stats.sheet_products:
        print(f"Produkty w arkuszu (SKU): {stats.sheet_products}")
    if stats.sku_matched or stats.sheet_only or stats.woo_only or stats.products_with_diffs:
        print(f"SKU zgodne (w obu źródłach): {stats.sku_matched}")
        print(f"Tylko w arkuszu: {stats.sheet_only}")
        print(f"Tylko w WooCommerce: {stats.woo_only}")
        print(f"Produkty ze różnicami pól: {stats.products_with_diffs}")
    if stats.dry_run_items:
        print(f"Pozycje dry-run: {stats.dry_run_items}")
    if stats.files_written:
        print("")
        print("Pliki prywatne:")
        for path in stats.files_written:
            print(f"  - {path}")


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    stats = RunStats()

    try:
        if options.fetch_woo:
            run_fetch_woo(options, stats)

        compare_result: CompareResult | None = None
        if options.compare:
            compare_result = run_compare(options, stats)

        if options.dry_run:
            run_dry_run(options, stats)

        print_summary(stats)
        return 0
    except RuntimeError as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
