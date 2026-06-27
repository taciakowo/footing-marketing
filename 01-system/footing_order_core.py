"""Wspólna logika tytułu sprawy i parsowania pozycji quick order / importu."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from footing_import_rules import (
    find_qty_product_matches,
    find_standalone_products,
    find_unknown_qty_products,
    has_footing_product,
    is_embedded_code,
)

DATE_DOT_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})")
SKROT_NAME_RE = re.compile(
    r"([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{1,})\.?\s+"
    r"([A-ZĄĆĘŁŃÓŚŹŻ][A-Za-ząćęłńóśźż\.\-]{1,})\.?\s*$",
)


@dataclass
class ParsedLineItem:
    ilosc: str
    produkt: str
    wariant: str
    nr_katalogowy: str
    surowy: str
    znany_slownik: bool
    status_sprawdzenia: str = "ok"


@dataclass
class ItemsParseResult:
    items: list[ParsedLineItem] = field(default_factory=list)
    liczba_pozycji: int = 0
    ilosc_sztuk: int = 0
    produkty_tekst: str = ""
    status_sprawdzenia: str = "ok"
    uwagi: list[str] = field(default_factory=list)


def normalize_product_code(prod: str, variant: str) -> str:
    if variant:
        sep = "-" if not variant.startswith(("-", "/")) else ""
        return f"{prod}{sep}{variant}".replace("//", "/")
    return prod


def canonical_from_raw(raw_code: str) -> tuple[str, str, str]:
    raw_code = (raw_code or "").replace(" ", "").upper()
    m = re.match(r"^(Z\d+|K\d+|H\d+|W\d+|F25|F2)(.*)$", raw_code, re.I)
    if m:
        prod = m.group(1).upper()
        var = m.group(2).lstrip("-/=")
        code = normalize_product_code(prod, var)
        return code, prod, var
    return raw_code, raw_code, ""


def is_known_catalog_code(raw_code: str) -> bool:
    code = (raw_code or "").replace(" ", "")
    if not code:
        return False
    return bool(has_footing_product(code))


def is_subcomponent_code(code: str, parents: set[str]) -> bool:
    cu = re.sub(r"[\s\-/=]", "", code.upper())
    for parent in parents:
        pu = re.sub(r"[\s\-/=]", "", parent.upper())
        if cu and pu and cu != pu and (cu in pu or pu.endswith(cu)):
            return True
    return False


def parse_items_text(items_text: str) -> ItemsParseResult:
    text = (items_text or "").strip()
    out = ItemsParseResult()
    if not text:
        out.status_sprawdzenia = "brak_pozycji"
        out.uwagi.append("brak items_text")
        return out

    seen: set[tuple[str, str]] = set()
    occupied: list[tuple[int, int]] = []
    qty_codes: set[str] = set()

    for _start, _end, qty, code, surowy in find_qty_product_matches(text):
        cat, prod, var = canonical_from_raw(code)
        key = (qty, cat)
        if key in seen:
            continue
        seen.add(key)
        qty_codes.add(code.upper().replace(" ", ""))
        znany = is_known_catalog_code(code)
        status = "ok" if znany else "produkt_spoza_slownika"
        out.items.append(ParsedLineItem(
            ilosc=qty,
            produkt=prod,
            wariant=var,
            nr_katalogowy=cat,
            surowy=surowy,
            znany_slownik=znany,
            status_sprawdzenia=status,
        ))
        occupied.append((_start, _end))

    for code in find_standalone_products(text, occupied, qty_codes):
        if is_subcomponent_code(code, qty_codes):
            continue
        cat, prod, var = canonical_from_raw(code)
        key = ("", cat)
        if key in seen:
            continue
        seen.add(key)
        znany = is_known_catalog_code(code)
        status = "do_sprawdzenia_brak_ilosci" if znany else "produkt_spoza_slownika"
        out.items.append(ParsedLineItem(
            ilosc="",
            produkt=prod,
            wariant=var,
            nr_katalogowy=cat,
            surowy=code,
            znany_slownik=znany,
            status_sprawdzenia=status,
        ))

    for qty, tail, surowy in find_unknown_qty_products(text, occupied, qty_codes):
        key = (qty, tail[:40])
        if key in seen:
            continue
        seen.add(key)
        out.items.append(ParsedLineItem(
            ilosc=qty,
            produkt=tail,
            wariant="",
            nr_katalogowy=tail,
            surowy=surowy,
            znany_slownik=False,
            status_sprawdzenia="produkt_spoza_slownika",
        ))

    parts: list[str] = []
    total_qty = 0
    worst = "ok"
    for it in out.items:
        if it.ilosc and it.nr_katalogowy:
            parts.append(f"{it.ilosc}x{it.nr_katalogowy}")
            try:
                total_qty += int(it.ilosc)
            except ValueError:
                pass
        elif it.nr_katalogowy:
            parts.append(it.nr_katalogowy)
        if it.status_sprawdzenia == "produkt_spoza_slownika":
            worst = "produkt_spoza_slownika"
        elif it.status_sprawdzenia == "do_sprawdzenia_brak_ilosci" and worst == "ok":
            worst = "do_sprawdzenia_brak_ilosci"

    out.produkty_tekst = "; ".join(parts)
    out.liczba_pozycji = len(out.items)
    out.ilosc_sztuk = total_qty
    out.status_sprawdzenia = worst if out.items else "brak_pozycji"
    if not out.items and text:
        if re.search(r"\d+\s*[*x×X]", text, re.I):
            out.status_sprawdzenia = "produkt_spoza_slownika"
            out.uwagi.append("tekst z ilością, ale bez rozpoznanego produktu ze słownika")
        else:
            out.status_sprawdzenia = "brak_pozycji"
            out.uwagi.append("brak rozpoznanych pozycji produktowych")
    return out


def normalize_event_date(raw: str) -> str:
    raw = (raw or "").strip()
    m = DATE_DOT_RE.search(raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    return raw


def format_event_date_display(iso_date: str) -> str:
    iso_date = (iso_date or "")[:10]
    if re.match(r"\d{4}-\d{2}-\d{2}", iso_date):
        y, m, d = iso_date.split("-")
        return f"{y}.{m}.{d}"
    return iso_date


def extract_skrot_nazwy(desc: str) -> str:
    remainder = (desc or "").strip()
    remainder = DATE_DOT_RE.sub(" ", remainder)
    remainder = re.sub(r"\b(?:Klient(?:ka)?|Żona)\b", " ", remainder, flags=re.I)
    remainder = re.sub(r"\d+\s*[*x×X]\s*\S+", " ", remainder)
    remainder = re.sub(
        r"\b(?:Z\d+|K\d+|H\d+|W\d+|F25|F2)(?:[\-/=][A-Z0-9/]+|[A-Z]\d+[A-Z0-9/]*)?\b",
        " ",
        remainder,
        flags=re.I,
    )
    remainder = re.sub(r"\s+", " ", remainder).strip(" ,-|=")
    m = SKROT_NAME_RE.search(remainder)
    if not m:
        return ""
    a = m.group(1)[:4]
    b = re.sub(r"[^A-Za-ząćęłńóśźż]", "", m.group(2))[:4]
    if len(a) >= 2 and len(b) >= 2:
        return f"{a.capitalize()}.{b.capitalize()}."
    return ""


def build_tytul_sprawy(
    data: str,
    items: ItemsParseResult | list[ParsedLineItem],
    inwestycja: str = "",
    skrot_nazwy: str = "",
) -> str:
    data_disp = format_event_date_display(normalize_event_date(data))
    line_items = items.items if isinstance(items, ItemsParseResult) else items
    parts = [data_disp, "Klient"]

    product_chunks: list[str] = []
    for it in line_items:
        code = it.nr_katalogowy or it.produkt
        if it.ilosc and code:
            product_chunks.append(f"{it.ilosc}x{code}")
        elif code:
            product_chunks.append(code)
    if product_chunks:
        parts.append(" ".join(product_chunks))

    inv = (inwestycja or "").strip()
    if inv:
        parts.append(inv)
    skrot = (skrot_nazwy or "").strip()
    if skrot:
        parts.append(skrot)
    return " ".join(p for p in parts if p).strip()
