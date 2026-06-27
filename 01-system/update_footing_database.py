#!/usr/bin/env python3
"""Footing System – aktualizacja bazy klientów, zamówień i komunikacji."""

from __future__ import annotations

import base64
import csv
import hashlib
import html
import json
import quopri
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "01-system"))

from footing_import_rules import (  # noqa: E402
    KLIENT_NAME_RE,
    NON_FOOTING_CONTACT_RE,
    find_qty_product_matches,
    find_standalone_products,
    find_unknown_qty_products,
    has_footing_product,
    is_internal_email,
    sanitize_email,
)
from footing_csv import normalize_text, write_csv as csv_write  # noqa: E402
from shipping_export import build_shipping_exports  # noqa: E402
from footing_order_core import (  # noqa: E402
    build_tytul_sprawy,
    extract_skrot_nazwy,
    parse_items_text,
)
from footing_buffer import (  # noqa: E402
    BufferStore,
    detect_commercial_signals,
    merge_quick_order_files,
    write_buffer_exports,
    write_buffer_notification,
)

INBOX = ROOT / "00-inbox"
OUT_PRIVATE = ROOT / "02-output-private"
REPORTS = ROOT / "03-raporty"
CONFIG_PATH = ROOT / "01-system" / "config.json"
CONFIG_EXAMPLE = ROOT / "01-system" / "config.example.json"

INTERNAL_PHONES = {"+48888338495", "48888338495", "888338495"}

MONTHS_PL = {
    "sty": "01", "lut": "02", "mar": "03", "kwi": "04", "maj": "05", "cze": "06",
    "lip": "07", "sie": "08", "wrz": "09", "paź": "10", "paz": "10", "lis": "11", "gru": "12",
}
DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})\.(\d{2})\.(\d{2})\b"), "ymd"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "ymd"),
    (re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b"), "dmy"),
]
QTY_SZT_RE = re.compile(r"\b(\d+)\s*szt(?:uk|\.)?\b", re.I)
APPLICATION_RE = re.compile(
    r"\b(pergol\w*|altan\w*|domek\w*|budynek\w*|wiata\w*|fotowoltaik\w*|"
    r"słup\w*|slup\w*|maszt\w*|lamp\w*|ogrodzen\w*|taras\w*|konstrukcj\w*|"
    r"zadaszen\w*|szlaban\w*|latarn\w*)\b", re.I,
)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
POSTAL_RE = re.compile(r"\b(\d{2}-\d{3})\b")
STRONG_FOOTING = re.compile(
    r"footing\.pl|\bZ2[567]\b|\bZ17\b|\bfundament|\bkotw|\bocynk|"
    r"stop[aąęy]\s+fundament|podstaw[aąęy]", re.I,
)
EXCLUDE_SENDERS = {
    "ORANGE", "Inteligo", "Alior Bank", "3333", "Google", "Microsoft",
    "PACZKAwRUCH", "DHL", "PP S.A.", "Info", "AXA",
}
SEO_KEYWORDS = re.compile(
    r"\b(fundament\w*|footing|Z25|Z26|Z17|pergol\w*|altan\w*|kotw\w*|"
    r"stop[aąęy]\s+fundament|podstaw[aąęy]|fotowoltaik\w*)\b", re.I,
)

CLIENT_COLS = [
    "nazwa_kontaktu_google", "pierwsza_data", "telefon", "email", "nazwa_klienta",
    "adres", "nr_adresu", "nr_lokalu", "kod_pocztowy", "miasto", "nip",
    "status_sprawdzenia", "uwagi",
    "inwestycja", "segment", "ostatnia_data", "produkty", "wartosc_zamowien",
    "liczba_zamowien", "produkt_glowny", "skrot_nazwy", "ostatnia_komunikacja", "zrodla",
    "klient_id", "contact_resource_name", "google_etag", "hash",
]
ORDER_COLS = [
    "data_zamowienia", "tytul_sprawy", "nazwa_kontaktu_google", "telefon", "produkty",
    "ilosc_sztuk", "liczba_pozycji", "status_zamowienia", "status_sprawdzenia", "kwota",
    "dostawa", "adres_dostawy", "email", "nazwa_klienta", "uwagi", "zrodlo",
    "zamowienie_id", "klient_id", "source_id", "hash", "pozycje_tekst",
]
ITEM_COLS = [
    "data_zamowienia", "nazwa_kontaktu_google", "telefon", "ilosc", "produkt", "wariant",
    "nr_katalogowy", "opis_pozycji", "inwestycja", "status_pozycji", "status_sprawdzenia",
    "uwagi", "pozycja_id", "zamowienie_id", "klient_id", "source_id", "hash",
]
ZAMOWIENIA_WIDOK_COLS = [
    "data_zamowienia", "status_zamowienia", "tytul_sprawy", "produkty", "ilosc_sztuk",
    "liczba_pozycji", "inwestycja", "nazwa_kontaktu_google", "telefon", "dostawa", "kwota",
    "adres_dostawy", "email", "nazwa_klienta", "uwagi",
]
KOM_COLS = [
    "message_id", "klient_id", "data", "kanal", "kierunek", "telefon", "email", "temat",
    "tresc", "typ_wiadomosci", "powiazane_order_id", "status_sprawdzenia",
]
EMAIL_CONTACT_COLS = [
    "email", "telefon", "klient_id", "nazwa_kontaktu", "imie_firma",
    "liczba_wiadomosci", "pierwsza_wiadomosc", "ostatnia_wiadomosc", "status", "uwagi",
]
SEO_COLS = ["fraza", "liczba_wystapien", "zrodlo", "przyklad_tresci", "zastosowanie", "powiazany_produkt"]
SEGMENT_COLS = [
    "segment", "klient_id", "telefon", "email", "produkt", "zastosowanie",
    "liczba_zamowien", "ostatnia_data", "zgoda_marketingowa", "uwagi",
]
REVIEW_COLS = [
    "typ_problemu", "data", "tytul_sprawy", "nazwa_kontaktu_google", "telefon",
    "produkty_lub_fragment", "sugestia", "uwagi", "zrodlo",
    "klient_id", "zamowienie_id", "pozycja_id", "source_id", "hash",
]
BREVO_KONTAKTY_COLS = [
    "email", "telefon", "nazwa_kontaktu_google", "nazwa_klienta", "data_zamowienia",
    "produkt_glowny", "produkty", "ilosc_laczna", "zastosowanie", "segment",
    "zrodlo", "status_marketingowy", "uwagi",
]
BREVO_REVIEW_COLS = ["email", "telefon", "nazwa_kontaktu_google", "powod", "sugestia"]
MARKETING_SEGMENTS = (
    "pergole", "altany", "domki", "lampy", "kotwy", "wykonawcy",
    "allegro", "woo", "ogolny",
)
CRITICAL_REVIEW_TYPY = frozenset({
    "data_i_ilosc_bez_kodu_produktu",
    "produkt_spoza_slownika",
    "do_sprawdzenia_brak_ilosci",
})
PRIVATE_RE = re.compile(r"prywatn|os\.?\s+fiz|nie\s+(?:reklam|mail)", re.I)
UNSUBSCRIBE_RE = re.compile(
    r"wypis\w*|unsubscribe|rezygnuj|nie\s+(?:chc[eę]|pisz)|\bSTOP\b|rezygnacja", re.I,
)
COMPANY_RE = re.compile(
    r"sp\.?\s*z\.?\s*o\.?\s*o\.?|s\.?\s*c\.?|firma|biuro|instalac|monta(?:ż|z)|"
    r"wykonaw|stolar|budowl|handel|sklep|s\.?a\.?|gmbh|fhu|phu", re.I,
)
MARKETING_OUT = OUT_PRIVATE / "marketing"


@dataclass
class ContactItem:
    ilosc: str
    produkt: str
    wariant: str
    surowy: str

    @property
    def kod_pelny(self) -> str:
        if self.wariant:
            sep = "-" if not self.wariant.startswith("-") and not self.wariant.startswith("/") else ""
            return f"{self.produkt}{sep}{self.wariant}".replace("//", "/")
        return self.produkt


@dataclass
class ParsedContact:
    surowa: str
    data_zamowienia: str = ""
    items: list[ContactItem] = field(default_factory=list)
    items_no_qty: list[ContactItem] = field(default_factory=list)
    unknown_items: list[ContactItem] = field(default_factory=list)
    zastosowanie: str = ""
    miasto: str = ""
    imie_firma: str = ""
    skrot_nazwy: str = ""
    pewny: bool = True
    uwagi: list[str] = field(default_factory=list)


@dataclass
class CommMessage:
    message_id: str
    telefon: str
    email: str
    data: str
    kanal: str
    kierunek: str
    temat: str
    tresc: str
    typ_wiadomosci: str
    wewnetrzny: bool = False


def load_config() -> dict:
    path = CONFIG_PATH if CONFIG_PATH.exists() else CONFIG_EXAMPLE
    with path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    for p in cfg.get("internal_phones", []):
        INTERNAL_PHONES.add(p)
    return cfg


def normalize_phone(address: str) -> str:
    digits = re.sub(r"\D", "", address or "")
    if len(digits) == 9:
        return "+48" + digits
    if len(digits) == 11 and digits.startswith("48"):
        return "+" + digits
    if len(digits) >= 9:
        return "+" + digits
    return ""


def is_valid_phone(phone: str) -> bool:
    return len(re.sub(r"\D", "", phone or "")) >= 9


def is_internal_phone(phone: str) -> bool:
    if phone in INTERNAL_PHONES:
        return True
    return re.sub(r"\D", "", phone or "").endswith("888338495")


def klient_id_from_phone(phone: str) -> str:
    d = re.sub(r"\D", "", phone)[-9:]
    return f"K-{d}" if d else ""


def decode_vcard_qp(text: str) -> str:
    def repl(m: re.Match) -> str:
        try:
            return bytes.fromhex(m.group(1)).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return m.group(0)
    return re.sub(r"=([0-9A-Fa-f]{2})", repl, text)


def parse_date(text: str) -> str:
    for pat, fmt in DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        if fmt == "ymd":
            y, mo, d = m.group(1), m.group(2), m.group(3)
        else:
            d, mo, y = m.group(1), m.group(2), m.group(3)
        return f"{y}-{mo}-{d}"
    return ""


def split_produkt_wariant(code: str) -> tuple[str, str]:
    code = code.upper().replace("=", "-")
    if code.startswith("F2"):
        code = "Z25" + code[2:]
    m = re.match(r"^(W(?:35|40|400|2001|2002))(K\d+.*)$", code)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"^(Z\d+|K\d+|H\d+|W\d+|F25)([-/].+)?$", code)
    if m:
        return m.group(1), (m.group(2) or "").lstrip("-/")
    m = re.match(r"^(K\d+|Z\d+|H\d+|W\d+)([A-Z0-9/].*)$", code)
    if m:
        return m.group(1), m.group(2)
    return code, ""


def normalize_product_code(base: str, suffix: str = "") -> str:
    base = base.upper()
    if base == "F2":
        base = "Z25"
    suffix = (suffix or "").lstrip("-=/=").upper()
    if not suffix:
        return base
    if suffix == base:
        return base
    if re.match(rf"^{re.escape(base)}[\-/=]", suffix):
        return suffix.replace("/", "-")
    return f"{base}-{suffix}".replace("/", "-")


def canonical_product(raw_code: str) -> tuple[str, str, str]:
    """Zwraca (kod_znormalizowany, produkt, wariant)."""
    raw_code = raw_code.replace(" ", "").upper()
    m = re.match(r"^(Z\d+|K\d+|H\d+|W\d+|F25|F2)(.*)$", raw_code, re.I)
    code = normalize_product_code(m.group(1), m.group(2)) if m else raw_code.replace("=", "-")
    prod, var = split_produkt_wariant(code)
    var = var.lstrip("-/")
    return code, prod, var


def parse_contact_items(desc: str) -> tuple[list[ContactItem], list[ContactItem], list[ContactItem]]:
    items: list[ContactItem] = []
    items_no_qty: list[ContactItem] = []
    unknown: list[ContactItem] = []
    seen: set[tuple[str, str, str]] = set()
    occupied: list[tuple[int, int]] = []
    qty_codes: set[str] = set()

    def add(qty: str, prod: str, var: str, surowy: str, target: list[ContactItem]) -> None:
        key = (qty, prod, var)
        if key in seen:
            return
        seen.add(key)
        target.append(ContactItem(qty, prod, var, surowy))

    for start, end, qty, code, surowy in find_qty_product_matches(desc):
        occupied.append((start, end))
        qty_codes.add(code.upper().replace(" ", ""))
        _code, prod, var = canonical_product(code)
        add(qty, prod, var, surowy, items)

    for code in find_standalone_products(desc, occupied, qty_codes):
        _code, prod, var = canonical_product(code)
        if has_footing_product(code):
            add("", prod, var, code, items_no_qty)
        else:
            add("", prod or code, var, code, unknown)

    for qty, tail, surowy in find_unknown_qty_products(desc, occupied, qty_codes):
        add(qty, tail, "", surowy, unknown)

    return items, items_no_qty, unknown


def extract_zastosowanie(desc: str, items: list[ContactItem]) -> str:
    remainder = desc
    for it in items:
        remainder = remainder.replace(it.surowy, " ")
    for pat, _ in DATE_PATTERNS:
        remainder = pat.sub(" ", remainder)
    remainder = re.sub(r"\b(?:Klient(?:ka)?|Żona)\b", " ", remainder, flags=re.I)
    apps = APPLICATION_RE.findall(remainder)
    return apps[0].capitalize() if apps else ""


def extract_miasto(desc: str, items: list[ContactItem], zast: str) -> str:
    remainder = desc
    for it in items:
        remainder = remainder.replace(it.surowy, " ")
    if zast:
        remainder = re.sub(re.escape(zast), " ", remainder, flags=re.I)
    for pat, _ in DATE_PATTERNS:
        remainder = pat.sub(" ", remainder)
    remainder = re.sub(r"\b(?:Klient(?:ka)?|Żona)\b", " ", remainder, flags=re.I)
    remainder = APPLICATION_RE.sub(" ", remainder)
    remainder = re.sub(r"\d+\s*[*x×X]\s*\S+", " ", remainder)
    remainder = re.sub(r"\b(?:szt(?:uk)?|Fund|Got|Sztuk|Podstawy|Kwadr)\b", " ", remainder, flags=re.I)
    remainder = re.sub(r"\s+", " ", remainder).strip(" ,-|=")
    remainder = re.sub(r"^\d+\s+", "", remainder).strip()
    return remainder[:80] if remainder and len(remainder) >= 3 else ""


def parse_contact_name(desc: str) -> ParsedContact:
    desc = normalize_text(decode_vcard_qp(desc.strip()))
    out = ParsedContact(surowa=desc)
    out.data_zamowienia = parse_date(desc)
    out.items, out.items_no_qty, out.unknown_items = parse_contact_items(desc)
    all_items = out.items + out.items_no_qty + out.unknown_items
    out.zastosowanie = extract_zastosowanie(desc, all_items)
    out.miasto = extract_miasto(desc, all_items, out.zastosowanie)
    out.skrot_nazwy = extract_skrot_nazwy(desc)
    m = re.search(
        r"(?:Klient(?:ka)?|Żona)\s+(?:\d+\s+)?([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?)",
        desc,
    )
    if m:
        out.imie_firma = m.group(1).strip()
    if not out.data_zamowienia:
        out.pewny = False
        out.uwagi.append("brak daty w nazwie kontaktu")
    if len(re.findall(r"\b\d{4}\.\d{2}\.\d{2}\b", desc)) > 1:
        out.pewny = False
        out.uwagi.append("wiele dat w nazwie kontaktu")
    if not out.items and not out.items_no_qty and not out.unknown_items:
        if QTY_SZT_RE.search(desc):
            out.uwagi.append("ilość bez kodu produktu")
            out.pewny = False
        elif has_footing_product(desc):
            out.uwagi.append("produkt bez rozpoznanej ilości")
        elif KLIENT_NAME_RE.search(desc):
            out.uwagi.append("brak rozpoznanego produktu")
    elif out.items_no_qty and not out.items:
        out.uwagi.append("brak ilości przy rozpoznanym produkcie")
    return out


def contact_is_footing_client(pc: ParsedContact) -> bool:
    return bool(KLIENT_NAME_RE.search(pc.surowa) and pc.data_zamowienia)


def contact_creates_order(pc: ParsedContact) -> bool:
    if not pc.data_zamowienia:
        return False
    return bool(pc.items or pc.items_no_qty or pc.unknown_items)


def looks_like_google_title(text: str) -> bool:
    text = (text or "").strip()
    if re.match(r"\d{4}\.\d{2}\.\d{2}\s+Klient", text, re.I):
        return True
    if re.match(r"Klient\s+\d{4}", text, re.I):
        return True
    if re.search(r"\bKlient\b", text, re.I) and re.search(r"\d{4}", text):
        if re.search(r"\d+\s*[*x×X]\s*", text, re.I) or has_footing_product(text):
            return True
    return False


def resolve_nazwa_klienta(
    pc: ParsedContact | None,
    meta: dict,
    comm_names: list[str] | None = None,
) -> str:
    for name in comm_names or []:
        clean = normalize_text(name)
        if clean and not looks_like_google_title(clean):
            return clean
    if meta.get("firma"):
        firma = normalize_text(meta["firma"])
        if firma and not looks_like_google_title(firma):
            return firma
    parts = [meta.get("imie", ""), meta.get("nazwisko", "")]
    joined = normalize_text(" ".join(p for p in parts if p))
    if joined and not looks_like_google_title(joined):
        return joined
    if pc and pc.imie_firma and not looks_like_google_title(pc.imie_firma):
        return normalize_text(pc.imie_firma)
    return ""


def row_hash(*parts: str) -> str:
    payload = "|".join(normalize_text(p) for p in parts if p)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def make_review_row(
    typ_problemu: str,
    *,
    data: str = "",
    tytul_sprawy: str = "",
    nazwa_kontaktu_google: str = "",
    telefon: str = "",
    produkty_lub_fragment: str = "",
    sugestia: str = "",
    uwagi: str = "",
    zrodlo: str = "google_contacts_read",
    klient_id: str = "",
    zamowienie_id: str = "",
    pozycja_id: str = "",
    source_id: str = "",
) -> dict:
    return {
        "typ_problemu": typ_problemu,
        "data": data,
        "tytul_sprawy": tytul_sprawy,
        "nazwa_kontaktu_google": nazwa_kontaktu_google,
        "telefon": telefon,
        "produkty_lub_fragment": produkty_lub_fragment,
        "sugestia": sugestia,
        "uwagi": uwagi,
        "zrodlo": zrodlo,
        "klient_id": klient_id,
        "zamowienie_id": zamowienie_id,
        "pozycja_id": pozycja_id,
        "source_id": source_id,
        "hash": row_hash(typ_problemu, telefon, data, produkty_lub_fragment),
    }


def project_crm_row(row: dict, columns: list[str]) -> dict:
    aliases = {
        "zamowienie_id": ("order_id", "zamowienie_id"),
        "pozycja_id": ("order_item_id", "pozycja_id"),
        "source_id": ("zrodlo", "source_id", "zrodlo_glowne"),
        "produkty": ("produkty", "pozycje_tekst"),
        "ilosc_sztuk": ("ilosc_sztuk", "ilosc_laczna"),
        "inwestycja": ("inwestycja", "zastosowanie", "zastosowania"),
        "typ_problemu": ("typ_problemu", "powod"),
        "produkty_lub_fragment": ("produkty_lub_fragment", "tresc_lub_nazwa"),
    }
    out: dict = {}
    for col in columns:
        if col in aliases:
            for key in aliases[col]:
                if row.get(key) not in (None, ""):
                    out[col] = row[key]
                    break
            else:
                out[col] = ""
        else:
            out[col] = row.get(col, "")
    return out


def write_crm_csv(path: Path, columns: list[str], rows: list[dict]) -> Path:
    projected = [project_crm_row(r, columns) for r in rows]
    return csv_write(path, columns, projected)


def nr_katalogowy(produkt: str, wariant: str) -> str:
    if wariant:
        sep = "-" if not str(wariant).startswith(("-", "/")) else ""
        return f"{produkt}{sep}{wariant}".replace("//", "/")
    return produkt


def format_produkty(items: list[dict]) -> str:
    parts: list[str] = []
    for it in items:
        code = it.get("nr_katalogowy") or it.get("kod_pelny") or it.get("produkt", "")
        qty = it.get("ilosc", "")
        if qty and code:
            parts.append(f"{qty}x{code}")
        elif code:
            parts.append(code)
    return "; ".join(parts)


def sum_ilosc(items: list[dict]) -> int:
    total = 0
    for it in items:
        try:
            total += int(it.get("ilosc") or 0)
        except ValueError:
            pass
    return total


def sum_ilosc_sztuk(items: list[dict]) -> int:
    return sum_ilosc(items)


def liczba_pozycji_zamowienia(items: list[dict]) -> int:
    return len(items)


def format_pozycje_tekst(items: list[dict]) -> str:
    return format_produkty(items)


def pick_produkt_glowny(items: list[dict]) -> str:
    if not items:
        return ""
    ranked: list[tuple[int, str]] = []
    for it in items:
        code = it.get("nr_katalogowy") or it.get("kod_pelny") or it.get("produkt", "")
        try:
            qty = int(it.get("ilosc") or 0)
        except ValueError:
            qty = 0
        score = qty * 10 + (3 if re.match(r"Z|K", code, re.I) else 1)
        ranked.append((score, code))
    ranked.sort(reverse=True)
    return ranked[0][1]


def record_client_email(
    store: dict[str, str], kid: str, raw_email: str, internal_seen: set[str],
) -> None:
    if not raw_email or not kid or store.get(kid):
        return
    clean, internal = sanitize_email(raw_email)
    if internal:
        internal_seen.add(internal.lower())
    if clean:
        store[kid] = clean


VCARD_CHARSETS = {
    "UTF-8": "utf-8",
    "UTF8": "utf-8",
    "ISO-8859-2": "iso-8859-2",
    "ISO8859-2": "iso-8859-2",
    "LATIN2": "iso-8859-2",
    "WINDOWS-1250": "cp1250",
    "CP1250": "cp1250",
}
VCARD_CHARSET_FALLBACKS = ("utf-8", "cp1250", "iso-8859-2")
SUSPICIOUS_VCF_MARKERS = ("\ufffd", "Ã", "Å", "Ä", "=C", "=D", "=E", "=F")
DIAG_VCF_COLS = [
    "telefon", "nazwa_surowa", "nazwa_zdekodowana", "encoding", "charset", "czy_podejrzana",
]


def normalize_vcard_charset(charset: str) -> str:
    key = (charset or "").strip().upper().replace("_", "-")
    return VCARD_CHARSETS.get(key, charset.lower())


def detect_file_charset(raw: bytes) -> str:
    for enc in VCARD_CHARSET_FALLBACKS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def decode_bytes_with_charset(data: bytes, charset: str | None) -> str:
    if charset:
        enc = normalize_vcard_charset(charset)
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            pass
    for enc in VCARD_CHARSET_FALLBACKS:
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def parse_vcard_params(param_part: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for piece in param_part.split(";"):
        piece = piece.strip()
        if not piece:
            continue
        if "=" in piece:
            key, val = piece.split("=", 1)
            params[key.upper()] = val
        else:
            params[piece.upper()] = ""
    return params


def parse_vcard_property(line: str) -> tuple[str, dict[str, str], str]:
    if ":" not in line:
        return "", {}, line
    head, value = line.split(":", 1)
    parts = head.split(";")
    prop = parts[0].split(".")[-1].upper()
    params = parse_vcard_params(";".join(parts[1:]))
    return prop, params, value


def decode_vcard_value(value: str, params: dict[str, str] | None = None) -> str:
    if not value:
        return value
    params = params or {}
    encoding = params.get("ENCODING", "").upper()
    charset = params.get("CHARSET", "")

    if encoding in ("QUOTED-PRINTABLE", "QP"):
        raw_bytes = quopri.decodestring(value.encode("ascii", errors="replace"))
        return decode_bytes_with_charset(raw_bytes, charset or None)

    if encoding == "BASE64":
        raw_bytes = base64.b64decode("".join(value.split()))
        return decode_bytes_with_charset(raw_bytes, charset or None)

    return value


def is_suspicious_vcf_name(name: str) -> bool:
    return any(marker in name for marker in SUSPICIOUS_VCF_MARKERS)


def unfold_vcard_byte_lines(raw_lines: list[bytes]) -> list[bytes]:
    unfolded: list[bytes] = []
    for line in raw_lines:
        if line and line[:1] in (b" ", b"\t") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def unfold_vcard_lines(lines: list[str]) -> list[str]:
    unfolded: list[str] = []
    for line in lines:
        if line and line[0] in " \t" and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def read_vcard_file_lines(path: Path) -> tuple[list[str], str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    physical = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").split(b"\n")
    unfolded = unfold_vcard_byte_lines(physical)
    file_charset = detect_file_charset(raw)
    lines = [decode_bytes_with_charset(line, file_charset) if line else "" for line in unfolded]
    return lines, file_charset


def format_vcard_name(n_value: str, n_params: dict[str, str]) -> str:
    decoded = decode_vcard_value(n_value, n_params)
    parts = decoded.split(";")
    while len(parts) < 5:
        parts.append("")
    family, given, additional, prefix, suffix = parts[:5]
    pieces = [prefix, given, additional, family, suffix]
    return " ".join(p for p in pieces if p).strip()


def is_vcard_format(lines: list[str]) -> bool:
    return any(line.strip().upper() == "BEGIN:VCARD" for line in lines)


def make_vcf_diagnostic(
    telefon: str,
    raw_name: str,
    decoded_name: str,
    encoding: str,
    charset: str,
) -> dict[str, str]:
    return {
        "telefon": telefon,
        "nazwa_surowa": raw_name,
        "nazwa_zdekodowana": decoded_name,
        "encoding": encoding,
        "charset": charset,
        "czy_podejrzana": "tak" if is_suspicious_vcf_name(decoded_name) else "nie",
    }


def load_contacts_tab(lines: list[str], file_charset: str) -> tuple[dict[str, ParsedContact], list[dict]]:
    contacts: dict[str, ParsedContact] = {}
    diagnostics: list[dict] = []
    for line in lines[1:]:
        if not line.strip() or line.startswith("Opis"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        raw_name = parts[0].strip()
        decoded_name = decode_vcard_value(raw_name, {})
        parsed = parse_contact_name(decoded_name)
        for p in re.split(r",\s*", parts[1]):
            phone = normalize_phone(p.strip())
            if phone and not is_internal_phone(phone):
                old = contacts.get(phone)
                if not old or parsed.data_zamowienia >= old.data_zamowienia:
                    contacts[phone] = parsed
                diagnostics.append(make_vcf_diagnostic(
                    phone, raw_name, decoded_name, "", file_charset,
                ))
    return contacts, diagnostics


def load_contacts_vcard(lines: list[str]) -> tuple[dict[str, ParsedContact], list[dict]]:
    contacts: dict[str, ParsedContact] = {}
    diagnostics: list[dict] = []
    block: list[str] = []
    for line in lines:
        if line.strip().upper() == "BEGIN:VCARD":
            block = [line]
            continue
        if not block:
            continue
        block.append(line)
        if line.strip().upper() != "END:VCARD":
            continue

        fn_raw, fn_decoded, fn_params = "", "", {}
        n_raw, n_params = "", {}
        phones: list[tuple[str, str, dict[str, str]]] = []
        for ln in block:
            prop, params, value = parse_vcard_property(ln.strip())
            if prop == "FN":
                fn_raw, fn_params = value, params
                fn_decoded = decode_vcard_value(value, params)
            elif prop == "N":
                n_raw, n_params = value, params
            elif prop == "TEL":
                phones.append((value, decode_vcard_value(value, params), params))
            elif prop == "EMAIL":
                pass

        if fn_decoded:
            name_raw, name_decoded = fn_raw, fn_decoded
            name_enc = fn_params.get("ENCODING", "")
            name_cs = fn_params.get("CHARSET", "")
        elif n_raw:
            name_raw = n_raw
            name_decoded = format_vcard_name(n_raw, n_params)
            name_enc = n_params.get("ENCODING", "")
            name_cs = n_params.get("CHARSET", "")
        else:
            block = []
            continue

        parsed = parse_contact_name(name_decoded)
        for tel_raw, tel_decoded, _tel_params in phones:
            phone = normalize_phone(tel_decoded or tel_raw)
            if phone and not is_internal_phone(phone):
                old = contacts.get(phone)
                if not old or parsed.data_zamowienia >= old.data_zamowienia:
                    contacts[phone] = parsed
                diagnostics.append(make_vcf_diagnostic(
                    phone, name_raw, name_decoded, name_enc, name_cs,
                ))
        block = []
    return contacts, diagnostics


def write_vcf_diagnostics(diagnostics: list[dict]) -> Path:
    OUT_PRIVATE.mkdir(parents=True, exist_ok=True)
    path = OUT_PRIVATE / "DIAGNOSTYKA-VCF.csv"
    write_csv(path, DIAG_VCF_COLS, diagnostics)
    return path


def assert_vcard_decode_self_test() -> None:
    assert decode_vcard_value("Jan Kowalski", {}) == "Jan Kowalski"
    assert decode_vcard_value(
        "=C5=81=C3=B3d=C5=BA",
        {"ENCODING": "QUOTED-PRINTABLE", "CHARSET": "UTF-8"},
    ) == "\u0141\u00f3d\u017a"
    assert decode_vcard_value(
        "Krak=F3w",
        {"ENCODING": "QUOTED-PRINTABLE", "CHARSET": "WINDOWS-1250"},
    ) == "Krak\u00f3w"
    assert decode_vcard_value(
        "Krak=F3w",
        {"ENCODING": "QUOTED-PRINTABLE", "CHARSET": "ISO-8859-2"},
    ) == "Krak\u00f3w"
    assert decode_vcard_value("=C5=81", {"ENCODING": "QP", "CHARSET": "UTF-8"}) == "\u0141"

    folded = unfold_vcard_lines([
        "FN;CHARSET=UTF-8;ENCODING=QUOTED-PRINTABLE:=C5=81=C3=B3",
        " d=C5=BA",
    ])
    _, params, value = parse_vcard_property(folded[0])
    assert decode_vcard_value(value, params) == "\u0141\u00f3d\u017a"

    assert decode_vcard_value("4xZ25=4B160 Ogrodzenie", {}) == "4xZ25=4B160 Ogrodzenie"


def load_contacts_google_cache(path: Path) -> tuple[dict[str, ParsedContact], list[dict]]:
    contacts: dict[str, ParsedContact] = {}
    diagnostics: list[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            name = (row.get("nazwa_kontaktu") or "").strip()
            if not name:
                name = " ".join(
                    p for p in (
                        (row.get("imie") or "").strip(),
                        (row.get("nazwisko") or "").strip(),
                        (row.get("firma") or "").strip(),
                    ) if p
                ).strip()
            if not name:
                continue
            parsed = parse_contact_name(name)
            phone_raw = (row.get("telefon") or "").strip()
            if not phone_raw:
                continue
            phone = normalize_phone(phone_raw)
            if phone and not is_internal_phone(phone):
                old = contacts.get(phone)
                if not old or parsed.data_zamowienia >= old.data_zamowienia:
                    contacts[phone] = parsed
    return contacts, diagnostics


def load_contacts() -> tuple[dict[str, ParsedContact], list[dict], str]:
    cache_path = INBOX / "contacts_cache.csv"
    if cache_path.exists():
        contacts, diagnostics = load_contacts_google_cache(cache_path)
        print(f"Kontakty: źródło google_contacts_cache ({cache_path.name})")
        return contacts, diagnostics, "google_contacts_cache"

    path = INBOX / "contacts.vcf"
    if not path.exists():
        print("Brak contacts_cache.csv i contacts.vcf")
        return {}, [], "brak"

    print(f"Kontakty: źródło contacts_vcf_fallback ({path.name})")
    lines, file_charset = read_vcard_file_lines(path)
    if is_vcard_format(lines):
        contacts, diagnostics = load_contacts_vcard(lines)
    elif any("\t" in line for line in lines[:3]):
        contacts, diagnostics = load_contacts_tab(lines, file_charset)
    else:
        contacts, diagnostics = load_contacts_vcard(lines)
    return contacts, diagnostics, "contacts_vcf_fallback"


def decode_sms_body(body: str) -> str:
    return html.unescape(body.replace("&#10;", "\n").replace("&#13;", "")) if body else ""


def readable_to_iso(readable: str) -> str:
    parts = (readable or "").split()
    if len(parts) >= 4:
        day = parts[0].zfill(2)
        mon = MONTHS_PL.get(parts[1][:3].lower(), "")
        year = parts[2] if parts[2].isdigit() and len(parts[2]) == 4 else parts[-1]
        if mon and year.isdigit():
            return f"{year}-{mon}-{day}"
    return ""


def is_footing_sms(body: str, address: str) -> bool:
    if address in EXCLUDE_SENDERS:
        return False
    if re.search(
        r"wiadomosc glosowa|materac|przyczep|clicktrans|Norwegia|Molde|"
        r"CIESLA SZALUNKOWY|ZUS II|Paczka o nr|odaconnect",
        body, re.I,
    ):
        return False
    return bool(STRONG_FOOTING.search(body))


def classify_sms(body: str, incoming: bool) -> str:
    if re.search(r"Dzi[eę]kuj[eę]\s+za\s+zam[oó]wienie", body, re.I):
        return "podsumowanie_zamowienia"
    if re.search(r"PRZELEW PRZYCHODZACY|zapłacone|zaplacone", body, re.I):
        return "potwierdzenie_platnosci"
    if re.search(r"prosz[eę]\s+o\s+(?:adres|kontakt|realizacj)", body, re.I) and not incoming:
        return "prośba_o_dane"
    if re.search(r"witam|zapytanie|prosz[eę]\s+o\s+kontakt", body, re.I) and incoming:
        return "zapytanie"
    if re.search(r"Razem:|Do zapłaty|zaliczka|Dostawa|Wysyłka", body, re.I):
        return "wycena"
    return "inne"


def load_sms() -> list[CommMessage]:
    path = INBOX / "sms.xml"
    if not path.exists():
        print(f"Brak pliku: {path}")
        return []
    messages: list[CommMessage] = []
    for sms in ET.parse(path).getroot().findall("sms"):
        body = decode_sms_body(sms.get("body", ""))
        phone = normalize_phone(sms.get("address", ""))
        address = sms.get("address", "")
        internal = is_internal_phone(phone)
        footing = is_footing_sms(body, address)
        if internal and not footing:
            continue
        if not internal and not footing:
            continue
        incoming = sms.get("type") == "1"
        mid = "M-" + hashlib.sha1(
            f"{sms.get('date','')}|{address}|{body[:120]}".encode("utf-8", errors="replace")
        ).hexdigest()[:12]
        emails = EMAIL_RE.findall(body)
        messages.append(CommMessage(
            message_id=mid, telefon=phone, email=emails[0] if emails else "",
            data=readable_to_iso(sms.get("readable_date", "")),
            kanal="SMS", kierunek="przychodząca" if incoming else "wychodząca",
            temat="", tresc=body, typ_wiadomosci=classify_sms(body, incoming),
            wewnetrzny=internal,
        ))
    return messages


def load_email_cache() -> list[CommMessage]:
    path = INBOX / "email_cache.csv"
    if not path.exists():
        return []
    messages: list[CommMessage] = []
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            email = row.get("email", "").strip()
            body = row.get("tresc", row.get("body", ""))
            temat = row.get("temat", row.get("subject", ""))
            data = row.get("data", row.get("date", ""))[:10]
            phone = normalize_phone(row.get("telefon", ""))
            kier = row.get("kierunek", "przychodząca")
            raw = f"{email}|{data}|{temat}|{body[:80]}"
            mid = "E-" + hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()[:12]
            messages.append(CommMessage(
                message_id=mid, telefon=phone, email=email, data=data,
                kanal="email", kierunek=kier, temat=temat, tresc=body,
                typ_wiadomosci=row.get("typ", "email"),
            ))
    return messages


def parse_money(text: str | None) -> float | None:
    if not text:
        return None
    try:
        v = float(text.replace(" ", "").replace(",", "."))
        if 1 <= v < 1_000_000:
            return round(v, 2)
    except ValueError:
        pass
    return None


def fmt_money(val: float | None) -> str:
    return f"{val:.2f}".replace(".", ",") if val is not None else ""


def extract_sms_supplement(body: str) -> dict[str, str]:
    sup: dict[str, str] = {}
    for line in body.splitlines():
        ln = line.strip()
        m = re.search(r"razem\s*[:=]?\s*(\d+(?:[.,]\d{1,2})?)\s*(?:zł|zl|PLN)?", ln, re.I)
        if m and not re.search(r"konto|rachunek|\+48", ln, re.I):
            sup.setdefault("kwota_razem", fmt_money(parse_money(m.group(1))))
        m = re.search(r"(?:Dostawa do:|Wysyłka:)\s*(.+)", ln, re.I)
        if m:
            sup.setdefault("adres_dostawy", m.group(1).strip()[:200])
    emails = EMAIL_RE.findall(body)
    if emails:
        sup["email"] = emails[0]
    return sup


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> Path:
    crm_files = {
        "KLIENCI.csv", "ZAMOWIENIA.csv", "POZYCJE-ZAMOWIEN.csv", "ZAMOWIENIA-WIDOK.csv",
        "DO-SPRAWDZENIA.csv", "EMAIL-KONTAKTY.csv",
    }
    if path.name in crm_files:
        return write_crm_csv(path, columns, rows)
    return csv_write(path, columns, rows)


def build_seo_rows(komunikacja: list[dict], contacts: dict[str, ParsedContact]) -> list[dict]:
    counter: Counter = Counter()
    examples: dict[str, str] = {}
    sources: dict[str, str] = {}
    for row in komunikacja:
        if row.get("status_sprawdzenia") == "wykluczony_firmowy":
            continue
        text = row.get("tresc", "")
        for m in SEO_KEYWORDS.finditer(text):
            fraza = m.group(0).lower()
            counter[fraza] += 1
            examples.setdefault(fraza, text[:80].replace("\n", " "))
            sources.setdefault(fraza, row.get("kanal", ""))
    for pc in contacts.values():
        for m in SEO_KEYWORDS.finditer(pc.surowa):
            fraza = m.group(0).lower()
            counter[fraza] += 1
            examples.setdefault(fraza, pc.surowa[:80])
            sources.setdefault(fraza, "kontakt")
    rows = []
    for fraza, cnt in counter.most_common():
        rows.append({
            "fraza": fraza,
            "liczba_wystapien": cnt,
            "zrodlo": sources.get(fraza, ""),
            "przyklad_tresci": examples.get(fraza, "")[:100],
            "zastosowanie": "",
            "powiazany_produkt": fraza.upper() if re.match(r"Z\d+", fraza, re.I) else "",
        })
    return rows


def build_segments(clients: list[dict], orders: list[dict]) -> list[dict]:
    order_count = Counter(o["klient_id"] for o in orders)
    last_date = {o["klient_id"]: o["data_zamowienia"] for o in orders}
    rows = []
    for c in clients:
        segment = "inne"
        zast = c.get("zastosowania", "").lower()
        prod = c.get("produkty", c.get("produkty_z_kontaktu", "")).upper()
        if "pergol" in zast:
            segment = "pergola"
        elif "fotowoltaik" in zast:
            segment = "fotowoltaika"
        elif "Z26" in prod:
            segment = "Z26"
        elif "Z25" in prod:
            segment = "Z25"
        elif c.get("liczba_zamowien", 0) == 0:
            segment = "bez_zamowienia"
        rows.append({
            "segment": segment,
            "klient_id": c["klient_id"],
            "telefon": c["telefon"],
            "email": c["email"],
            "produkt": c.get("produkty", c.get("produkty_z_kontaktu", "")),
            "zastosowanie": c.get("zastosowania", ""),
            "liczba_zamowien": order_count.get(c["klient_id"], 0),
            "ostatnia_data": last_date.get(c["klient_id"], c.get("ostatnia_data", "")),
            "zgoda_marketingowa": "",
            "uwagi": "",
        })
    return rows


def build_email_contacts(
    komunikacja: list[dict], vcf: dict[str, ParsedContact], internal_seen: set[str],
) -> list[dict]:
    by_email: dict[str, dict] = {}
    for row in komunikacja:
        raw = row.get("email", "").strip()
        if not raw:
            continue
        clean, internal = sanitize_email(raw)
        if internal:
            internal_seen.add(internal.lower())
        if not clean:
            continue
        rec = by_email.setdefault(clean, {
            "email": clean, "telefon": "", "klient_id": "", "nazwa_kontaktu": "",
            "imie_firma": "", "liczba_wiadomosci": 0, "dates": [], "status": "ok", "uwagi": "",
        })
        rec["liczba_wiadomosci"] += 1
        if row.get("data"):
            rec["dates"].append(row["data"])
        if row.get("telefon") and not rec["telefon"]:
            rec["telefon"] = row["telefon"]
            rec["klient_id"] = row.get("klient_id", "")
    for phone, pc in vcf.items():
        for row in by_email.values():
            if row["telefon"] == phone:
                row["nazwa_kontaktu"] = pc.surowa
                row["imie_firma"] = pc.imie_firma
    rows = []
    for rec in sorted(by_email.values(), key=lambda x: x["email"]):
        dates = sorted(rec["dates"])
        rows.append({
            "email": rec["email"],
            "telefon": rec["telefon"],
            "klient_id": rec["klient_id"],
            "nazwa_kontaktu": rec["nazwa_kontaktu"],
            "imie_firma": rec["imie_firma"],
            "liczba_wiadomosci": rec["liczba_wiadomosci"],
            "pierwsza_wiadomosc": dates[0] if dates else "",
            "ostatnia_wiadomosc": dates[-1] if dates else "",
            "status": rec["status"],
            "uwagi": rec["uwagi"],
        })
    return rows


def load_google_cache_meta() -> dict[str, dict]:
    path = INBOX / "contacts_cache.csv"
    meta: dict[str, dict] = {}
    if not path.exists():
        return meta
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            phone = normalize_phone((row.get("telefon") or "").strip())
            if not phone or is_internal_phone(phone):
                continue
            rec = meta.setdefault(phone, {
                "email": "", "imie": "", "nazwisko": "", "firma": "", "notatka": "",
                "nazwa_kontaktu": "", "contact_resource_name": "", "google_etag": "",
            })
            for key in ("email", "imie", "nazwisko", "firma", "notatka", "nazwa_kontaktu",
                        "contact_resource_name", "google_etag", "contact_id", "etag"):
                val = (row.get(key) or "").strip()
                if val:
                    if key == "email":
                        clean, _internal = sanitize_email(val)
                        if clean:
                            rec["email"] = clean
                    elif key == "contact_id":
                        rec["contact_resource_name"] = val
                    elif key == "etag":
                        rec["google_etag"] = val
                    elif key in rec:
                        rec[key] = val
    return meta


def google_imie_firma(meta: dict) -> str:
    if meta.get("firma"):
        return meta["firma"]
    return " ".join(p for p in (meta.get("imie", ""), meta.get("nazwisko", "")) if p).strip()


def comm_text_for_client(kid: str, email: str, komunikacja: list[dict]) -> str:
    parts: list[str] = []
    for row in komunikacja:
        if row.get("klient_id") == kid or (email and row.get("email", "").lower() == email.lower()):
            parts.extend([row.get("temat", ""), row.get("tresc", ""), row.get("typ_wiadomosci", "")])
    return " ".join(parts)


def classify_marketing_segment(
    nazwa: str, produkt: str, zastosowanie: str, comm_text: str, order_sources: list[str],
) -> str:
    blob = " ".join([nazwa, produkt, zastosowanie, comm_text, " ".join(order_sources)]).lower()
    scores: Counter = Counter()
    rules = [
        ("allegro", r"allegro"),
        ("woo", r"woocommerce|footing\.pl|zamówienie\s+#\d|zamowienie\s+#\d"),
        ("pergole", r"pergol"),
        ("altany", r"altan|wiata"),
        ("domki", r"domek|całoroczn|caloroczn"),
        ("lampy", r"lamp|latarn|maszt|\bh\d+|\bsłup|\bslup"),
        ("kotwy", r"kotw|\bz2[567]\b|\bz17\b|fundament|stop[aąę]\s+fundament|\bk\d+"),
        ("wykonawcy", r"montaż|montaz|wykonaw|instalat|budowl|stolar|fachow|drew"),
    ]
    for seg, pat in rules:
        if re.search(pat, blob, re.I):
            scores[seg] += 2
    prod_u = produkt.upper()
    if re.search(r"\bZ2[567]\b|\bZ17\b|\bK\d+", prod_u):
        scores["kotwy"] += 3
    if re.search(r"\bH\d+", prod_u):
        scores["lampy"] += 3
    if "pergol" in zastosowanie.lower():
        scores["pergole"] += 3
    if scores:
        return scores.most_common(1)[0][0]
    return "ogolny"


def is_private_contact(nazwa: str, uwagi: str, meta: dict) -> bool:
    blob = " ".join([nazwa, uwagi, meta.get("notatka", ""), meta.get("nazwa_kontaktu", "")])
    return bool(PRIVATE_RE.search(blob))


def is_unsubscribed(nazwa: str, uwagi: str, meta: dict, comm_text: str) -> bool:
    blob = " ".join([nazwa, uwagi, meta.get("notatka", ""), comm_text])
    return bool(UNSUBSCRIBE_RE.search(blob))


def is_kontrahent(nazwa: str, imie_firma: str, meta: dict, segment: str) -> bool:
    if segment == "wykonawcy":
        return True
    blob = " ".join([nazwa, imie_firma, meta.get("firma", ""), meta.get("notatka", "")])
    return bool(COMPANY_RE.search(blob)) and not re.search(r"pergol|altan|domek", blob, re.I)


def is_footing_client(c: dict, contacts: dict[str, ParsedContact], komunikacja: list[dict]) -> bool:
    phone = c.get("telefon", "")
    kid = c.get("klient_id", "")
    if c.get("liczba_zamowien", 0) > 0:
        return True
    pc = contacts.get(phone)
    if pc and pc.data_zamowienia and (pc.items or pc.items_no_qty or pc.unknown_items):
        return True
    blob = " ".join([
        c.get("nazwa_kontaktu_google", c.get("nazwa_kontaktu", "")), c.get("produkty", ""),
        comm_text_for_client(kid, c.get("email", ""), komunikacja),
    ])
    return bool(STRONG_FOOTING.search(blob) or has_footing_product(blob))


def build_brevo_exports(
    clients: list[dict],
    reviews: list[dict],
    komunikacja: list[dict],
    orders: list[dict],
    contacts: dict[str, ParsedContact],
    google_meta: dict[str, dict],
    contacts_source: str,
    internal_seen: set[str],
) -> tuple[list[dict], list[dict], dict]:
    reviews_by_kid: dict[str, list[dict]] = defaultdict(list)
    reviews_by_phone: dict[str, list[dict]] = defaultdict(list)
    for r in reviews:
        if r.get("klient_id"):
            reviews_by_kid[r["klient_id"]].append(r)
        if r.get("telefon"):
            reviews_by_phone[r["telefon"]].append(r)

    order_sources_by_kid: dict[str, list[str]] = defaultdict(list)
    for o in orders:
        order_sources_by_kid[o["klient_id"]].append(o.get("zrodlo_glowne", ""))

    enriched: list[dict] = []
    for c in clients:
        phone = c["telefon"]
        meta = google_meta.get(phone, {})
        raw_email = (c.get("email") or meta.get("email") or "").strip()
        clean, internal = sanitize_email(raw_email)
        if internal:
            internal_seen.add(internal.lower())
        pc = contacts.get(phone)
        imie_firma = (pc.imie_firma if pc else "") or google_imie_firma(meta)
        enriched.append({
            **c,
            "email": clean,
            "imie_firma": imie_firma,
            "meta": meta,
            "pc_pewny": pc.pewny if pc else False,
            "data_zamowienia": c.get("data_z_kontaktu") or c.get("pierwsza_data") or (pc.data_zamowienia if pc else ""),
        })

    for row in komunikacja:
        raw = (row.get("email") or "").strip()
        if not raw or row.get("status_sprawdzenia") == "wykluczony_firmowy":
            continue
        clean, internal = sanitize_email(raw)
        if internal:
            internal_seen.add(internal.lower())
        if not clean:
            continue
        if any(e["email"] == clean for e in enriched):
            continue
        phone = row.get("telefon", "")
        if phone and is_internal_phone(phone):
            continue
        enriched.append({
            "klient_id": row.get("klient_id", ""),
            "telefon": phone,
            "email": clean,
            "nazwa_kontaktu_google": "",
            "nazwa_klienta": "",
            "produkty": "",
            "zastosowania": "",
            "liczba_zamowien": 0,
            "ostatnia_data": row.get("data", ""),
            "data_zamowienia": "",
            "status_sprawdzenia": "ok",
            "uwagi": "kontakt tylko z e-mail",
            "imie_firma": "",
            "meta": google_meta.get(phone, {}),
            "pc_pewny": True,
        })

    brevo_rows: list[dict] = []
    review_rows: list[dict] = []
    stats: dict = {
        "total": len(clients),
        "footing_after_filter": sum(
            1 for c in clients if is_footing_client(c, contacts, komunikacja)
        ),
        "with_email": 0,
        "qualified": 0,
        "excluded": 0,
        "do_sprawdzenia": 0,
        "brak_emaila": 0,
        "internal_emails_excluded": len(internal_seen),
        "segments": Counter(),
        "status_counts": Counter(),
    }

    seen_emails: set[str] = set()
    for c in enriched:
        email = c.get("email", "")
        phone = c.get("telefon", "")
        nazwa = c.get("nazwa_kontaktu_google", c.get("nazwa_kontaktu", ""))
        nazwa_klienta = c.get("nazwa_klienta", c.get("imie_firma", ""))
        uwagi = c.get("uwagi", "")
        meta = c.get("meta", {})
        kid = c.get("klient_id", "")
        produkty = c.get("produkty", c.get("produkty_z_kontaktu", ""))

        if not is_footing_client(c, contacts, komunikacja):
            continue

        if not email:
            stats["brak_emaila"] += 1
            continue
        if email in seen_emails:
            continue
        seen_emails.add(email)
        stats["with_email"] += 1

        comm_text = comm_text_for_client(kid, email, komunikacja)
        segment = classify_marketing_segment(
            nazwa, produkty, c.get("zastosowania", ""),
            comm_text, order_sources_by_kid.get(kid, []),
        )
        imie_firma = c.get("imie_firma", "")

        def review_entry(powod: str, sugestia: str) -> None:
            review_rows.append({
                "email": email, "telefon": phone, "nazwa_kontaktu_google": nazwa,
                "powod": powod, "sugestia": sugestia,
            })

        if is_internal_phone(phone):
            stats["excluded"] += 1
            stats["status_counts"]["wykluczony"] += 1
            continue

        if is_internal_email(email):
            stats["excluded"] += 1
            continue

        if NON_FOOTING_CONTACT_RE.search(nazwa + " " + comm_text):
            stats["excluded"] += 1
            continue

        if is_private_contact(nazwa, uwagi, meta):
            stats["excluded"] += 1
            stats["status_counts"]["wykluczony"] += 1
            continue

        if is_unsubscribed(nazwa, uwagi, meta, comm_text):
            stats["excluded"] += 1
            stats["status_counts"]["wykluczony"] += 1
            continue

        critical = False
        for r in reviews_by_kid.get(kid, []) + reviews_by_phone.get(phone, []):
            typ = r.get("typ_problemu") or r.get("powod", "")
            if typ in CRITICAL_REVIEW_TYPY:
                critical = True
                review_entry(typ, r.get("sugestia") or "Zweryfikuj dane zamówienia przed mailingiem")
                break
        if critical:
            stats["do_sprawdzenia"] += 1
            stats["status_counts"]["do_sprawdzenia"] += 1
            continue

        uncertain = (
            c.get("status_sprawdzenia") == "do_sprawdzenia"
            or not c.get("pc_pewny", True)
            or "brak nazwy kontaktu" in uwagi.lower()
            or "kontakt tylko z e-mail" in uwagi.lower()
        )
        if uncertain:
            powod = uwagi or "niepewne dane kontaktowe"
            sugestia = "Uzupełnij nazwę kontaktu i powiąż telefon z Google Contacts"
            if "kontakt tylko z e-mail" in uwagi.lower():
                sugestia = "Powiąż e-mail z numerem telefonu w Google Contacts"
            review_entry(powod, sugestia)
            stats["do_sprawdzenia"] += 1
            stats["status_counts"]["do_sprawdzenia"] += 1
            continue

        if c.get("liczba_zamowien", 0) > 0:
            status_m = "klient_istniejacy"
        elif is_kontrahent(nazwa, imie_firma, meta, segment):
            status_m = "kontrahent"
        else:
            status_m = "potencjalny_klient"

        brevo_rows.append({
            "email": email,
            "telefon": phone,
            "nazwa_kontaktu_google": nazwa,
            "nazwa_klienta": nazwa_klienta,
            "data_zamowienia": c.get("data_zamowienia") or c.get("ostatnia_data", ""),
            "produkt_glowny": c.get("produkt_glowny", ""),
            "produkty": produkty,
            "ilosc_laczna": c.get("ilosc_laczna", ""),
            "zastosowanie": c.get("zastosowania", ""),
            "segment": segment,
            "zrodlo": contacts_source,
            "status_marketingowy": status_m,
            "uwagi": uwagi,
        })
        stats["qualified"] += 1
        stats["segments"][segment] += 1
        stats["status_counts"][status_m] += 1

    brevo_rows.sort(key=lambda r: (r.get("data_zamowienia", ""), r.get("segment", "")), reverse=True)
    review_rows.sort(key=lambda r: (r["powod"], r["email"]))
    return brevo_rows, review_rows, stats


def write_mailing_report(brevo_stats: dict, contacts_source: str) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    segments = brevo_stats.get("segments", Counter())
    best_seg = "ogolny"
    if segments:
        best_seg = segments.most_common(1)[0][0]

    quality_notes = []
    if brevo_stats.get("brak_emaila", 0) > brevo_stats.get("with_email", 0):
        quality_notes.append("Większość kontaktów nie ma adresu e-mail – priorytet: uzupełnienie w Google Contacts.")
    if brevo_stats.get("do_sprawdzenia", 0) > 0:
        quality_notes.append(
            f"{brevo_stats['do_sprawdzenia']} kontaktów wymaga weryfikacji przed kolejną kampanią."
        )
    if contacts_source == "contacts_vcf_fallback":
        quality_notes.append("Kontakty z fallback VCF – zalecana synchronizacja Google Contacts (contacts_cache.csv).")
    if not quality_notes:
        quality_notes.append("Dane wystarczające do pierwszej kampanii testowej.")

    seg_lines = "\n".join(
        f"| {seg} | {segments.get(seg, 0)} |" for seg in MARKETING_SEGMENTS
    )
    (REPORTS / "MAILING-001.md").write_text(
        f"# Mailing 001 – podsumowanie eksportu Brevo\n\n"
        f"Wygenerowano: {now}\n\n"
        f"Źródło kontaktów: **{contacts_source}**\n\n"
        f"## Statystyki zbiorcze\n\n"
        f"| Metryka | Liczba |\n|---|---:|\n"
        f"| Kontakty ogółem | {brevo_stats.get('total', 0)} |\n"
        f"| Kontakty po filtrze Footing | {brevo_stats.get('footing_after_filter', 0)} |\n"
        f"| Kontakty z e-mailem | {brevo_stats.get('with_email', 0)} |\n"
        f"| E-maile wewnętrzne wykluczone | {brevo_stats.get('internal_emails_excluded', 0)} |\n"
        f"| Zakwalifikowane do Brevo | {brevo_stats.get('qualified', 0)} |\n"
        f"| Wykluczone | {brevo_stats.get('excluded', 0)} |\n"
        f"| Do sprawdzenia | {brevo_stats.get('do_sprawdzenia', 0)} |\n"
        f"| Brak e-maila | {brevo_stats.get('brak_emaila', 0)} |\n\n"
        f"## Podział według segmentów (zakwalifikowane)\n\n"
        f"| Segment | Liczba |\n|---|---:|\n{seg_lines}\n\n"
        f"## Rekomendowany segment startowy\n\n"
        f"**{best_seg}** – największa grupa zakwalifikowanych kontaktów "
        f"({segments.get(best_seg, 0)} rekordów).\n\n"
        f"## Uwagi dotyczące jakości danych\n\n"
        + "\n".join(f"- {n}" for n in quality_notes) + "\n",
        encoding="utf-8",
    )


def write_public_reports(stats: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().strftime("%Y-%m-%d")

    (REPORTS / "PODSUMOWANIE.md").write_text(
        f"# Footing System – podsumowanie\n\nWygenerowano: {now}\n\n"
        f"- Źródło kontaktów: **{stats.get('contacts_source', 'brak')}**\n"
        f"- Klienci: **{stats['clients']}**\n"
        f"- Zamówienia: **{stats['orders']}**\n"
        f"- Pozycje: **{stats['items']}**\n"
        f"- Komunikacja: **{stats['komunikacja']}**\n"
        f"- Do sprawdzenia: **{stats['reviews']}**\n"
        f"- Wykluczone wewnętrzne: **{stats['excluded']}**\n\n"
        "## Ranking produktów (sztuki)\n\n"
        + ("| Produkt | Sztuki |\n|---------|--------|\n" +
           "\n".join(f"| {p} | {q} |" for p, q in stats["rank_qty"][:15]) + "\n"
           if stats["rank_qty"] else "_Brak danych_\n")
        + "\n## Ranking zastosowań\n\n"
        + ("\n".join(f"- {a}: {c}" for a, c in stats["rank_apps"][:15]) + "\n"
           if stats["rank_apps"] else "_Brak danych_\n"),
        encoding="utf-8",
    )

    sprzedaz = REPORTS / "SPRZEDAZ.md"
    if not sprzedaz.exists():
        sprzedaz.write_text(
            "# Sprzedaż Footing\n\n"
            "Raport agregowany bez danych osobowych. Szczegóły w `02-output-private/`.\n\n"
            f"Ostatnia aktualizacja: {now}\n\n"
            "## Produkty (sztuki)\n\n"
            + "\n".join(f"- {p}: {q} szt." for p, q in stats["rank_qty"][:20])
            + "\n",
            encoding="utf-8",
        )
    else:
        sprzedaz.write_text(
            sprzedaz.read_text(encoding="utf-8").split("Ostatnia aktualizacja:")[0].rstrip()
            + f"\n\nOstatnia aktualizacja: {now}\n\n"
            "## Produkty (sztuki) – auto\n\n"
            + "\n".join(f"- {p}: {q} szt." for p, q in stats["rank_qty"][:20])
            + "\n",
            encoding="utf-8",
        )

    seo_path = REPORTS / "SEO.md"
    seo_lines = ["# SEO – frazy z komunikacji\n", f"\nOstatnia aktualizacja: {now}\n\n"]
    for fraza, cnt in stats.get("rank_seo", [])[:20]:
        seo_lines.append(f"- {fraza}: {cnt} wystąpień\n")
    seo_path.write_text("".join(seo_lines), encoding="utf-8")

    kamp = REPORTS / "KAMPANIE.md"
    if not kamp.exists():
        kamp.write_text(
            f"# Kampanie\n\nOstatnia aktualizacja: {now}\n\n"
            "Szablony kampanii: `05-kampanie/`\n", encoding="utf-8",
        )

    prod = REPORTS / "PRODUKCJA.md"
    prod.write_text(
        f"# Produkcja – zapotrzebowanie\n\nOstatnia aktualizacja: {now}\n\n"
        "## Szacunkowe ilości do produkcji (z zamówień)\n\n"
        + "\n".join(f"- {p}: {q} szt." for p, q in stats["rank_qty"][:25])
        + "\n", encoding="utf-8",
    )

    (REPORTS / "DZIENNY-RAPORT.md").write_text(
        f"# Raport dzienny – {today}\n\n"
        f"- Nowi klienci (sesja): {stats['clients']}\n"
        f"- Zamówienia: {stats['orders']}\n"
        f"- Pozycje: {stats['items']}\n"
        f"- Do sprawdzenia: {stats['reviews']}\n"
        f"- Wykluczone wewn.: {stats['excluded']}\n\n"
        f"Pełne dane: `02-output-private/`\n", encoding="utf-8",
    )


def send_slack(cfg: dict, stats: dict) -> None:
    url = cfg.get("slack_webhook_url", "").strip()
    if not url or not cfg.get("slack_notify_on_update"):
        return
    text = (
        f"Footing System – aktualizacja bazy\n"
        f"Klienci: {stats['clients']} | Zamówienia: {stats['orders']} | "
        f"Do sprawdzenia: {stats['reviews']}\n"
        f"Raport: 03-raporty/DZIENNY-RAPORT.md"
    )
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
        print("Slack: wysłano powiadomienie")
    except Exception as e:
        print(f"Slack: błąd ({e})")


def assert_contact_parser_self_test() -> None:
    test = parse_contact_name("2026.06.23 Klient 3xZ26-M20 3xK98/6 Pergola")
    assert test.data_zamowienia == "2026-06-23", test.data_zamowienia
    assert len(test.items) == 2, [(i.ilosc, i.produkt, i.wariant, i.kod_pelny) for i in test.items]
    assert test.items[0].ilosc == "3" and test.items[0].produkt == "Z26" and test.items[0].wariant == "M20"
    assert test.items[1].ilosc == "3" and test.items[1].produkt == "K98" and test.items[1].wariant == "6"
    assert test.zastosowanie.lower().startswith("pergol"), test.zastosowanie

    t2 = parse_contact_name("2026.06.23 Klient 4*Z25K130C altana")
    assert len(t2.items) == 1 and t2.items[0].produkt == "Z25", t2.items

    t3 = parse_contact_name("2026.06.23 Klient 1 x H2-H260/8")
    assert len(t3.items) == 1 and t3.items[0].produkt == "H2", t3.items

    t4 = parse_contact_name("2026.06.23 Klient K2K300")
    assert not t4.items and len(t4.items_no_qty) == 1, (t4.items, t4.items_no_qty)

    t5 = parse_contact_name("2026.06.23 Klient H2-S260 Z25-R150")
    assert len(t5.items_no_qty) == 2, t5.items_no_qty


def enrich_crm_tables(
    orders: list[dict],
    items: list[dict],
    clients: list[dict],
    komunikacja: list[dict],
    contacts: dict[str, ParsedContact],
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    client_by_kid = {c["klient_id"]: c for c in clients}
    items_by_order: dict[str, list[dict]] = defaultdict(list)
    items_by_kid: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        items_by_order[it["order_id"]].append(it)
        items_by_kid[it["klient_id"]].append(it)

    for o in orders:
        kid = o["klient_id"]
        c = client_by_kid.get(kid, {})
        order_items = items_by_order[o["order_id"]]
        for it in order_items:
            it["telefon"] = c.get("telefon", o.get("telefon", ""))
            it["nazwa_kontaktu_google"] = c.get("nazwa_kontaktu_google", o.get("nazwa_kontaktu_google", ""))
            it["inwestycja"] = o.get("inwestycja") or o.get("zastosowanie", "")
            it["opis_pozycji"] = it.get("opis_pozycji") or it.get("surowy", "")
            it["status_pozycji"] = "ok" if it.get("status_sprawdzenia") == "ok" else "do_weryfikacji"
            it["nr_katalogowy"] = nr_katalogowy(it.get("produkt", ""), it.get("wariant", ""))
            it["hash"] = row_hash(it.get("pozycja_id", it.get("order_item_id", "")), it.get("produkt", ""), it.get("ilosc", ""))
        o["telefon"] = c.get("telefon", "")
        o["email"] = c.get("email", "")
        o["nazwa_klienta"] = c.get("nazwa_klienta", "")
        o["produkty"] = format_produkty(order_items)
        o["pozycje_tekst"] = o["produkty"]
        o["ilosc_sztuk"] = sum_ilosc(order_items)
        o["ilosc_laczna"] = o["ilosc_sztuk"]
        o["liczba_pozycji"] = liczba_pozycji_zamowienia(order_items)
        o["produkt_glowny"] = pick_produkt_glowny(order_items)
        o["inwestycja"] = o.get("inwestycja") or o.get("zastosowanie", "")
        o["status_zamowienia"] = o.get("status_zamowienia") or (
            "do_weryfikacji" if o.get("status_sprawdzenia") != "ok" else "aktywne"
        )
        o["zrodlo"] = o.get("zrodlo") or o.get("zrodlo_glowne", "")
        o["hash"] = row_hash(o.get("order_id", ""), o.get("data_zamowienia", ""), o.get("telefon", ""))
        o["segment"] = classify_marketing_segment(
            c.get("nazwa_kontaktu_google", ""), o["produkty"], o.get("inwestycja", ""),
            comm_text_for_client(kid, c.get("email", ""), komunikacja), [o.get("zrodlo", "")],
        )

    comm_last: dict[str, str] = {}
    for row in komunikacja:
        kid = row.get("klient_id", "")
        if kid and row.get("data"):
            comm_last[kid] = max(comm_last.get(kid, ""), row["data"])

    for c in clients:
        kid = c["klient_id"]
        phone = c.get("telefon", "")
        pc = contacts.get(phone)
        client_items = items_by_kid.get(kid, [])
        if client_items:
            c["produkty"] = format_produkty(client_items)
            c["produkt_glowny"] = pick_produkt_glowny(client_items)
            c["ilosc_sztuk"] = sum_ilosc(client_items)
            c["ilosc_laczna"] = c["ilosc_sztuk"]
        else:
            c["produkty"] = c.get("produkty", "")
            c["produkt_glowny"] = c.get("produkt_glowny", "")
            c["ilosc_sztuk"] = c.get("ilosc_sztuk", c.get("ilosc_laczna", 0))
        c["inwestycja"] = c.get("inwestycja") or c.get("zastosowania", "")
        c["skrot_nazwy"] = c.get("skrot_nazwy") or (pc.skrot_nazwy if pc else "")
        c["ostatnia_komunikacja"] = comm_last.get(kid, "")
        c["nazwa_kontaktu_google"] = normalize_text(c.get("nazwa_kontaktu_google", ""))
        c["hash"] = row_hash(c.get("klient_id", ""), c.get("telefon", ""), c.get("nazwa_kontaktu_google", ""))
        c["segment"] = classify_marketing_segment(
            c.get("nazwa_kontaktu_google", ""), c.get("produkty", ""), c.get("inwestycja", ""),
            comm_text_for_client(kid, c.get("email", ""), komunikacja), c.get("zrodla", "").split(";"),
        )

    clients.sort(key=lambda r: (r.get("pierwsza_data", ""), r.get("nazwa_kontaktu_google", "")), reverse=True)
    orders.sort(key=lambda r: (r.get("data_zamowienia", ""), r.get("telefon", "")), reverse=True)
    items.sort(key=lambda r: (r.get("data_zamowienia", ""), r.get("order_id", ""), r.get("produkt", "")), reverse=True)

    widok: list[dict] = []
    for o in orders:
        c = client_by_kid.get(o["klient_id"], {})
        widok.append({
            "data_zamowienia": o.get("data_zamowienia", ""),
            "status_zamowienia": o.get("status_zamowienia", ""),
            "tytul_sprawy": o.get("tytul_sprawy", ""),
            "produkty": o.get("produkty", ""),
            "ilosc_sztuk": o.get("ilosc_sztuk", 0),
            "liczba_pozycji": o.get("liczba_pozycji", 0),
            "inwestycja": o.get("inwestycja", o.get("zastosowanie", "")),
            "nazwa_kontaktu_google": c.get("nazwa_kontaktu_google", o.get("nazwa_kontaktu_google", "")),
            "telefon": o.get("telefon", ""),
            "dostawa": o.get("dostawa", ""),
            "kwota": o.get("kwota", ""),
            "adres_dostawy": o.get("adres_dostawy", ""),
            "email": o.get("email", ""),
            "nazwa_klienta": c.get("nazwa_klienta", o.get("nazwa_klienta", "")),
            "uwagi": o.get("uwagi", ""),
        })
    widok.sort(key=lambda r: r.get("data_zamowienia", ""), reverse=True)
    return clients, orders, items, widok


def build_do_sprawdzenia(
    reviews: list[dict],
    clients: list[dict],
    orders: list[dict],
    items: list[dict],
    contacts: dict[str, ParsedContact],
) -> list[dict]:
    out = list(reviews)
    seen_hashes = {r.get("hash") for r in out if r.get("hash")}

    def add(row: dict) -> None:
        h = row.get("hash")
        if h and h in seen_hashes:
            return
        if h:
            seen_hashes.add(h)
        out.append(row)

    for c in clients:
        phone = c.get("telefon", "")
        pc = contacts.get(phone)
        if not pc or not contact_is_footing_client(pc):
            continue
        if not (c.get("produkty") or "").strip():
            add(make_review_row(
                "brak_rozpoznanego_produktu",
                data=pc.data_zamowienia,
                tytul_sprawy=build_tytul_sprawy(pc.data_zamowienia, [], pc.zastosowanie, pc.skrot_nazwy),
                nazwa_kontaktu_google=pc.surowa,
                telefon=phone,
                produkty_lub_fragment=pc.surowa[:120],
                sugestia="Uzupełnij produkt w Footing Panel (Google Contacts – tylko odczyt)",
                uwagi="; ".join(pc.uwagi),
                klient_id=c.get("klient_id", ""),
            ))
        if "wiele dat" in " ".join(pc.uwagi).lower():
            add(make_review_row(
                "klient_wieloma_datami",
                data=pc.data_zamowienia,
                tytul_sprawy=pc.surowa[:120],
                nazwa_kontaktu_google=pc.surowa,
                telefon=phone,
                produkty_lub_fragment=pc.surowa[:120],
                sugestia="Rozdziel wiele dat na osobne sprawy w panelu",
                uwagi="; ".join(pc.uwagi),
                klient_id=c.get("klient_id", ""),
            ))

    for o in orders:
        if QTY_SZT_RE.search(o.get("nazwa_kontaktu_google", "")) and not (o.get("produkty") or "").strip():
            add(make_review_row(
                "data_i_ilosc_bez_kodu_produktu",
                data=o.get("data_zamowienia", ""),
                tytul_sprawy=o.get("tytul_sprawy", ""),
                nazwa_kontaktu_google=o.get("nazwa_kontaktu_google", ""),
                telefon=o.get("telefon", ""),
                produkty_lub_fragment=o.get("nazwa_kontaktu_google", "")[:120],
                sugestia="Zweryfikuj kod produktu w panelu",
                uwagi=o.get("uwagi", ""),
                klient_id=o.get("klient_id", ""),
                zamowienie_id=o.get("order_id", ""),
            ))

    for it in items:
        status = it.get("status_sprawdzenia", "")
        if status == "do_sprawdzenia_brak_ilosci":
            add(make_review_row(
                "do_sprawdzenia_brak_ilosci",
                data=it.get("data_zamowienia", ""),
                nazwa_kontaktu_google=it.get("nazwa_kontaktu_google", ""),
                telefon=it.get("telefon", ""),
                produkty_lub_fragment=it.get("nr_katalogowy") or it.get("produkt", ""),
                sugestia="Potwierdź ilość w panelu – nie zakładamy domyślnie 1",
                uwagi=it.get("uwagi", ""),
                klient_id=it.get("klient_id", ""),
                zamowienie_id=it.get("order_id", ""),
                pozycja_id=it.get("order_item_id", ""),
            ))
        elif status == "produkt_spoza_slownika":
            add(make_review_row(
                "produkt_spoza_slownika",
                data=it.get("data_zamowienia", ""),
                nazwa_kontaktu_google=it.get("nazwa_kontaktu_google", ""),
                telefon=it.get("telefon", ""),
                produkty_lub_fragment=it.get("opis_pozycji") or it.get("produkt", ""),
                sugestia="Przypisz produkt do katalogu lub dodaj nowy w panelu",
                uwagi=it.get("uwagi", ""),
                klient_id=it.get("klient_id", ""),
                zamowienie_id=it.get("order_id", ""),
                pozycja_id=it.get("order_item_id", ""),
            ))

    out.sort(key=lambda r: (r.get("typ_problemu", ""), r.get("data", "")), reverse=True)
    return out


def main() -> int:
    assert_contact_parser_self_test()
    assert_vcard_decode_self_test()
    cfg = load_config()
    INBOX.mkdir(parents=True, exist_ok=True)
    OUT_PRIVATE.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    print("=== Footing System – update_footing_database ===")
    print("Google Contacts: tryb read-only – system nie modyfikuje nazw kontaktów Google")
    print()

    from fetch_emails_imap import IMAP_CREDENTIALS_MSG, get_imap_credentials, refresh_email_cache_if_configured

    if cfg.get("imap_host", "").strip() and get_imap_credentials(required=False) is None:
        print(IMAP_CREDENTIALS_MSG)
    else:
        added = refresh_email_cache_if_configured(cfg)
        if added:
            print(f"IMAP: zapisano {added} nowych e-maili do cache")

    contacts, vcf_diagnostics, contacts_source = load_contacts()
    if contacts_source == "contacts_vcf_fallback":
        diag_path = write_vcf_diagnostics(vcf_diagnostics)
        suspicious_count = sum(1 for d in vcf_diagnostics if d["czy_podejrzana"] == "tak")
        print(f"VCF: zdekodowano {len(vcf_diagnostics)} kontaktów, podejrzanych: {suspicious_count}")
        print(f"VCF diagnostyka: {diag_path}")

    sms_list = load_sms()
    email_list = load_email_cache()
    all_comm = sms_list + email_list
    print(f"Kontakty: {len(contacts)} | SMS: {len(sms_list)} | E-mail cache: {len(email_list)}")

    reviews: list[dict] = []
    orders: list[dict] = []
    items: list[dict] = []
    phone_to_order: dict[str, str] = {}
    order_seq = item_seq = 0
    internal_emails_seen: set[str] = set()

    for phone, pc in sorted(contacts.items()):
        if not contact_creates_order(pc):
            continue

        order_seq += 1
        oid = f"O-{order_seq:05d}"
        kid = klient_id_from_phone(phone)
        phone_to_order[phone] = oid

        if pc.unknown_items:
            status = "produkt_spoza_slownika"
        elif pc.items_no_qty and not pc.items:
            status = "do_sprawdzenia_brak_ilosci"
        elif pc.pewny and pc.items and not pc.items_no_qty:
            status = "ok"
        else:
            status = "do_sprawdzenia"

        title_bits: list[str] = []
        for it in pc.items + pc.items_no_qty + pc.unknown_items:
            if it.ilosc:
                code = it.kod_pelny or it.produkt
                title_bits.append(f"{it.ilosc}x{code}")
            else:
                title_bits.append(it.kod_pelny or it.produkt or it.surowy)
        parsed_for_title = parse_items_text(" ".join(title_bits))
        tytul = build_tytul_sprawy(
            pc.data_zamowienia, parsed_for_title,
            pc.zastosowanie, pc.skrot_nazwy,
        )

        orders.append({
            "order_id": oid, "klient_id": kid, "data_zamowienia": pc.data_zamowienia,
            "tytul_sprawy": tytul,
            "nazwa_kontaktu_google": pc.surowa,
            "zrodlo_glowne": "google_contacts_read",
            "zrodlo": "google_contacts_read",
            "zastosowanie": pc.zastosowanie,
            "inwestycja": pc.zastosowanie,
            "status_sprawdzenia": status,
            "status_zamowienia": "do_weryfikacji" if status != "ok" else "aktywne",
            "uwagi": "; ".join(pc.uwagi),
        })
        for it in pc.items:
            item_seq += 1
            cat = nr_katalogowy(it.produkt, it.wariant)
            items.append({
                "order_item_id": f"OI-{item_seq:05d}", "order_id": oid, "klient_id": kid,
                "data_zamowienia": pc.data_zamowienia,
                "produkt": it.produkt,
                "wariant": it.wariant,
                "nr_katalogowy": cat,
                "ilosc": it.ilosc,
                "opis_pozycji": it.surowy,
                "zrodlo": "google_contacts_read",
                "status_sprawdzenia": "ok",
                "uwagi": "",
            })
        for it in pc.items_no_qty:
            item_seq += 1
            cat = nr_katalogowy(it.produkt, it.wariant)
            items.append({
                "order_item_id": f"OI-{item_seq:05d}", "order_id": oid, "klient_id": kid,
                "data_zamowienia": pc.data_zamowienia,
                "produkt": it.produkt,
                "wariant": it.wariant,
                "nr_katalogowy": cat,
                "ilosc": "",
                "opis_pozycji": it.surowy,
                "zrodlo": "google_contacts_read",
                "status_sprawdzenia": "do_sprawdzenia_brak_ilosci",
                "uwagi": "brak ilości – wymaga potwierdzenia w panelu",
            })
        for it in pc.unknown_items:
            item_seq += 1
            items.append({
                "order_item_id": f"OI-{item_seq:05d}", "order_id": oid, "klient_id": kid,
                "data_zamowienia": pc.data_zamowienia,
                "produkt": it.produkt,
                "wariant": "",
                "nr_katalogowy": it.produkt if not has_footing_product(it.produkt) else "",
                "ilosc": it.ilosc,
                "opis_pozycji": it.surowy,
                "zrodlo": "google_contacts_read",
                "status_sprawdzenia": "produkt_spoza_slownika",
                "uwagi": "produkt spoza słownika Footing",
            })

    order_by_id = {o["order_id"]: o for o in orders}
    client_emails: dict[str, str] = defaultdict(str)
    client_dates: dict[str, list[str]] = defaultdict(list)
    komunikacja: list[dict] = []
    seen_ids: set[str] = set()
    excluded = 0

    for msg in sorted(all_comm, key=lambda m: (m.data, m.message_id)):
        if msg.message_id in seen_ids:
            continue
        seen_ids.add(msg.message_id)

        if msg.wewnetrzny:
            excluded += 1
            komunikacja.append({
                "message_id": msg.message_id, "klient_id": "", "data": msg.data,
                "kanal": msg.kanal, "kierunek": msg.kierunek, "telefon": msg.telefon,
                "email": msg.email, "temat": msg.temat,
                "tresc": msg.tresc.replace("\n", " | ")[:2000],
                "typ_wiadomosci": msg.typ_wiadomosci, "powiazane_order_id": "",
                "status_sprawdzenia": "wykluczony_firmowy",
            })
            continue

        kid = klient_id_from_phone(msg.telefon) if msg.telefon else ""
        oid = phone_to_order.get(msg.telefon, "")
        if msg.data and kid:
            client_dates[kid].append(msg.data)
        record_client_email(client_emails, kid, msg.email, internal_emails_seen)

        if oid and oid in order_by_id:
            sup = extract_sms_supplement(msg.tresc)
            od = order_by_id[oid]
            if sup.get("kwota_razem"):
                od["uwagi"] = (od.get("uwagi", "") + "; kwota uzupełniona z SMS").strip("; ")
            if sup.get("adres_dostawy"):
                od["uwagi"] = (od.get("uwagi", "") + "; adres uzupełniony z SMS").strip("; ")
            if sup.get("email"):
                record_client_email(client_emails, kid, sup["email"], internal_emails_seen)

        komunikacja.append({
            "message_id": msg.message_id, "klient_id": kid, "data": msg.data,
            "kanal": msg.kanal, "kierunek": msg.kierunek, "telefon": msg.telefon,
            "email": msg.email, "temat": msg.temat,
            "tresc": msg.tresc.replace("\n", " | ")[:2000],
            "typ_wiadomosci": msg.typ_wiadomosci, "powiazane_order_id": oid,
            "status_sprawdzenia": "ok",
        })

    client_orders = Counter(o["klient_id"] for o in orders)
    google_meta = load_google_cache_meta()
    clients: list[dict] = []

    for phone, pc in sorted(contacts.items()):
        if is_internal_phone(phone) or not is_valid_phone(phone):
            continue
        if not contact_is_footing_client(pc):
            continue
        kid = klient_id_from_phone(phone)
        meta = google_meta.get(phone, {})
        dates = sorted(set(client_dates.get(kid, []) + ([pc.data_zamowienia] if pc.data_zamowienia else [])))
        prods = [
            f"{it.ilosc}x{it.kod_pelny}" if it.ilosc else (it.kod_pelny or it.surowy)
            for it in (pc.items + pc.items_no_qty + pc.unknown_items)
        ]
        zasts = [pc.zastosowanie] if pc.zastosowanie else []
        status, uwagi = "ok", ""
        if not pc.pewny:
            status, uwagi = "do_sprawdzenia", "; ".join(pc.uwagi)
        elif not prods:
            status, uwagi = "do_sprawdzenia", "; ".join(filter(None, [uwagi, "brak rozpoznanego produktu"]))

        raw_email = (client_emails.get(kid, "") or meta.get("email", "")).strip()
        clean, internal = sanitize_email(raw_email)
        if internal:
            internal_emails_seen.add(internal.lower())

        nazwa_google = normalize_text(pc.surowa)
        nazwa_klienta = resolve_nazwa_klienta(pc, meta)

        clients.append({
            "nazwa_kontaktu_google": nazwa_google,
            "pierwsza_data": dates[0] if dates else "",
            "telefon": phone,
            "email": clean,
            "nazwa_klienta": nazwa_klienta,
            "adres": "", "nr_adresu": "", "nr_lokalu": "", "kod_pocztowy": "", "miasto": pc.miasto,
            "nip": "",
            "status_sprawdzenia": status,
            "uwagi": uwagi,
            "inwestycja": "; ".join(zasts),
            "segment": "",
            "ostatnia_data": dates[-1] if dates else "",
            "produkty": "; ".join(prods),
            "wartosc_zamowien": "",
            "liczba_zamowien": client_orders.get(kid, 0),
            "produkt_glowny": "",
            "skrot_nazwy": pc.skrot_nazwy,
            "ostatnia_komunikacja": "",
            "zrodla": contacts_source,
            "klient_id": kid,
            "contact_resource_name": meta.get("contact_resource_name", ""),
            "google_etag": meta.get("google_etag", ""),
            "hash": row_hash(kid, phone, nazwa_google),
            "zastosowania": "; ".join(zasts),
            "ilosc_laczna": 0,
        })

    clients, orders, items, zamowienia_widok = enrich_crm_tables(
        orders, items, clients, komunikacja, contacts,
    )
    reviews = build_do_sprawdzenia(reviews, clients, orders, items, contacts)

    bufor_dir = OUT_PRIVATE / "bufor"
    buffer_store = BufferStore()
    buffer_store.load_existing(bufor_dir)
    google_phones = set(contacts.keys())
    for msg in sorted(all_comm, key=lambda m: (m.data, m.message_id)):
        if msg.wewnetrzny:
            continue
        text = normalize_text(f"{msg.temat} {msg.tresc}")
        if not text.strip() and not msg.telefon and not msg.email:
            continue
        if msg.telefon in google_phones and not detect_commercial_signals(text, msg.typ_wiadomosci):
            if not has_footing_product(text) and not STRONG_FOOTING.search(text):
                buffer_store.add_unrelated({
                    "powod": "komunikacja_powiazana_bez_nowego_zamowienia",
                    "telefon": msg.telefon,
                    "email": msg.email,
                    "nazwa_lub_nadawca": msg.email or msg.telefon,
                    "pierwsza_data": msg.data,
                    "ostatnia_data": msg.data,
                    "zrodlo": msg.kanal.lower(),
                    "fragment_tresci": text[:200],
                    "sugestia": "Klient już w danych czystych (Google) – brak nowego sygnału zamówienia",
                    "uwagi": "",
                    "source_id": msg.message_id,
                })
                continue
        buffer_store.add_candidate(
            zrodlo=msg.kanal.lower(),
            source_id=msg.message_id,
            data=msg.data,
            telefon=msg.telefon,
            email=msg.email,
            text=text,
            typ_wiadomosci=msg.typ_wiadomosci,
            nazwa_nadawcy=msg.email or msg.telefon or "",
            clean_clients=clients,
            extract_supplement_fn=extract_sms_supplement,
            has_footing_product_fn=has_footing_product,
            nr_katalogowy_fn=nr_katalogowy,
        )
    merge_quick_order_files(OUT_PRIVATE, buffer_store, clients)
    bufor_dir = write_buffer_exports(OUT_PRIVATE, buffer_store)
    write_buffer_notification(bufor_dir, buffer_store)
    buffer_stats = buffer_store.stats()

    rank_qty: Counter = Counter()
    rank_apps: Counter = Counter()
    for it in items:
        try:
            rank_qty[it["produkt"]] += int(it["ilosc"] or 0)
        except ValueError:
            pass
    for o in orders:
        if o.get("zastosowanie"):
            rank_apps[o["zastosowanie"].lower()] += 1

    seo_rows = build_seo_rows(komunikacja, contacts)
    segment_rows = build_segments(clients, orders)
    email_contact_rows = build_email_contacts(komunikacja, contacts, internal_emails_seen)

    write_csv(OUT_PRIVATE / "KLIENCI.csv", CLIENT_COLS, clients)
    write_csv(OUT_PRIVATE / "ZAMOWIENIA.csv", ORDER_COLS, orders)
    write_csv(OUT_PRIVATE / "POZYCJE-ZAMOWIEN.csv", ITEM_COLS, items)
    write_csv(OUT_PRIVATE / "ZAMOWIENIA-WIDOK.csv", ZAMOWIENIA_WIDOK_COLS, zamowienia_widok)
    write_csv(OUT_PRIVATE / "KOMUNIKACJA.csv", KOM_COLS, komunikacja)
    write_csv(OUT_PRIVATE / "DO-SPRAWDZENIA.csv", REVIEW_COLS, reviews)
    write_csv(OUT_PRIVATE / "EMAIL-KONTAKTY.csv", EMAIL_CONTACT_COLS, email_contact_rows)
    write_csv(OUT_PRIVATE / "SEO-FRAZY.csv", SEO_COLS, seo_rows)
    write_csv(OUT_PRIVATE / "SEGMENTY-KLIENTOW.csv", SEGMENT_COLS, segment_rows)

    MARKETING_OUT.mkdir(parents=True, exist_ok=True)
    brevo_rows, brevo_review_rows, brevo_stats = build_brevo_exports(
        clients, reviews, komunikacja, orders, contacts, google_meta, contacts_source,
        internal_emails_seen,
    )
    brevo_stats["internal_emails_excluded"] = len(internal_emails_seen)
    write_csv(MARKETING_OUT / "BREVO-KONTAKTY-001.csv", BREVO_KONTAKTY_COLS, brevo_rows)
    write_csv(MARKETING_OUT / "BREVO-DO-SPRAWDZENIA.csv", BREVO_REVIEW_COLS, brevo_review_rows)
    write_mailing_report(brevo_stats, contacts_source)

    shipping_stats = build_shipping_exports(
        orders, items, clients, komunikacja, contacts, write_csv,
    )

    clients_bez_produktu = sum(
        1 for c in clients if not (c.get("produkty") or "").strip()
    )

    stats = {
        "clients": len(clients), "orders": len(orders), "items": len(items),
        "komunikacja": len(komunikacja), "reviews": len(reviews), "excluded": excluded,
        "rank_qty": rank_qty.most_common(), "rank_apps": rank_apps.most_common(),
        "rank_seo": Counter(r["fraza"] for r in seo_rows).most_common(),
        "contacts_source": contacts_source,
        "brevo_qualified": len(brevo_rows),
        "brevo_review": len(brevo_review_rows),
        "zamowienia_widok": len(zamowienia_widok),
        "internal_emails_excluded": len(internal_emails_seen),
        "clients_bez_produktu": clients_bez_produktu,
        "buffer_klienci": buffer_stats["klienci_do_akceptacji"],
        "buffer_zamowienia": buffer_stats["zamowienia_do_akceptacji"],
        "buffer_pozycje": buffer_stats["pozycje_do_akceptacji"],
        "buffer_korekta": buffer_stats["wymaga_korekty"],
        "buffer_unrelated": buffer_stats["unrelated"],
        **{f"shipping_{k}": v for k, v in shipping_stats.items() if k not in ("categories", "missing_fields")},
    }
    write_public_reports(stats)
    send_slack(cfg, stats)

    print()
    print("=== BUFOR ===")
    print(f"  klienci do akceptacji:   {buffer_stats['klienci_do_akceptacji']}")
    print(f"  zamówienia do akceptacji: {buffer_stats['zamowienia_do_akceptacji']}")
    print(f"  pozycje do akceptacji:   {buffer_stats['pozycje_do_akceptacji']}")
    print(f"  wymagają korekty:        {buffer_stats['wymaga_korekty']}")
    print(f"  kontakty niepowiązane:   {buffer_stats['unrelated']}")
    print()
    print("=== Wynik ===")
    for label, val in [
        ("Klienci", stats["clients"]),
        ("Klienci bez rozpoznanego produktu", stats.get("clients_bez_produktu", 0)),
        ("Zamówienia", stats["orders"]),
        ("Pozycje", stats["items"]), ("Zamówienia – widok", stats["zamowienia_widok"]),
        ("Komunikacja", stats["komunikacja"]),
        ("Do sprawdzenia", stats["reviews"]), ("Wykluczone wewn.", stats["excluded"]),
        ("E-maile wewn. wykluczone", stats["internal_emails_excluded"]),
        ("Brevo – kontakty", stats["brevo_qualified"]),
        ("Brevo – do sprawdzenia", stats["brevo_review"]),
        ("Wysyłki", stats["shipping_wysylki_total"]),
        ("Paczki", stats["shipping_paczki_total"]),
        ("Gotowe do nadania", stats["shipping_gotowe_do_nadania"]),
        ("Wysyłki do sprawdzenia", stats["shipping_do_sprawdzenia"]),
        ("APACZKA-IMPORT-001", stats["shipping_apaczka_import"]),
    ]:
        print(f"  {label}: {val}")
    print()
    print("=== Wysyłki – braki ===")
    for label, key in [
        ("Brak adresów", "shipping_brak_adresow"),
        ("Brak telefonów", "shipping_brak_telefonow"),
        ("Brak e-maili powiadomień", "shipping_brak_emaili"),
        ("Brak kategorii", "shipping_brak_kategorii"),
    ]:
        print(f"  {label}: {stats[key]}")
    print(f"\nDane prywatne: {OUT_PRIVATE}")
    print(f"Eksport Brevo:  {MARKETING_OUT}")
    print(f"Raporty:        {REPORTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
