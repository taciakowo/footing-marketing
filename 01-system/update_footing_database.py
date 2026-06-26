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
CONTACT_ITEM_RE = re.compile(
    r"(\d+)\s*[*x×X]\s*"
    r"((?:Z|K|H|W|F)\d+(?:[-/=][A-Z0-9/]+|[A-Z]\d+[A-Z0-9/]*)?)",
    re.I,
)
CONTACT_ITEM_COMPACT = re.compile(
    r"(\d+)\s*[*x×X]\s*(Z\d+|K\d+|H\d+|W\d+|F25|F2)([\-/=A-Z0-9./]*)",
    re.I,
)
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
    "klient_id", "telefon", "email", "nazwa_kontaktu", "data_z_kontaktu",
    "produkty_z_kontaktu", "zastosowania", "miasto", "liczba_zamowien",
    "pierwsza_data", "ostatnia_data", "status_sprawdzenia", "uwagi",
]
ORDER_COLS = [
    "order_id", "klient_id", "data_zamowienia", "zrodlo_glowne", "zastosowanie",
    "kwota_razem", "adres_dostawy", "status_sprawdzenia", "uwagi",
]
ITEM_COLS = [
    "order_item_id", "order_id", "klient_id", "data_zamowienia", "produkt", "wariant",
    "ilosc", "cena_jednostkowa", "kwota_pozycji", "zrodlo", "status_sprawdzenia", "uwagi",
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
    "powod", "klient_id", "telefon", "email", "nazwa_kontaktu", "data",
    "tresc_lub_nazwa", "sugestia", "uwagi",
]


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
    zastosowanie: str = ""
    miasto: str = ""
    imie_firma: str = ""
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
    return address or ""


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
    if suffix.startswith(base):
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


def parse_contact_items(desc: str) -> list[ContactItem]:
    items: list[ContactItem] = []
    seen_items: set[tuple[str, str, str]] = set()

    def add(qty: str, raw_code: str, surowy: str) -> None:
        code, prod, var = canonical_product(raw_code)
        key = (qty, prod, var)
        if key in seen_items:
            return
        seen_items.add(key)
        items.append(ContactItem(qty, prod, var, surowy))

    for qty, code in CONTACT_ITEM_RE.findall(desc):
        add(qty, code, f"{qty}x{code}")

    if not items:
        for qty, base, suffix in CONTACT_ITEM_COMPACT.findall(desc):
            add(qty, f"{base}{suffix or ''}", f"{qty}x{base}{suffix or ''}")

    return items


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
    desc = decode_vcard_qp(desc.strip())
    out = ParsedContact(surowa=desc)
    out.data_zamowienia = parse_date(desc)
    out.items = parse_contact_items(desc)
    out.zastosowanie = extract_zastosowanie(desc, out.items)
    out.miasto = extract_miasto(desc, out.items, out.zastosowanie)
    m = re.search(
        r"(?:Klient(?:ka)?|Żona)\s+(?:\d+\s+)?([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)?)",
        desc,
    )
    if m:
        out.imie_firma = m.group(1).strip()
    if not out.data_zamowienia:
        out.pewny = False
        out.uwagi.append("brak daty w nazwie kontaktu")
    if not out.items:
        if QTY_SZT_RE.search(desc):
            out.uwagi.append("ilość bez kodu produktu")
            out.pewny = False
        else:
            out.uwagi.append("brak rozpoznanych pozycji produktowych")
    return out


def contact_creates_order(pc: ParsedContact) -> bool:
    return bool(pc.data_zamowienia and (pc.items or QTY_SZT_RE.search(pc.surowa)))


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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writeheader()
        w.writerows({c: r.get(c, "") for c in columns} for r in rows)
    return path


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
        prod = c.get("produkty_z_kontaktu", "").upper()
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
            "produkt": c.get("produkty_z_kontaktu", ""),
            "zastosowanie": c.get("zastosowania", ""),
            "liczba_zamowien": order_count.get(c["klient_id"], 0),
            "ostatnia_data": last_date.get(c["klient_id"], c.get("ostatnia_data", "")),
            "zgoda_marketingowa": "",
            "uwagi": "",
        })
    return rows


def build_email_contacts(komunikacja: list[dict], vcf: dict[str, ParsedContact]) -> list[dict]:
    by_email: dict[str, dict] = {}
    for row in komunikacja:
        email = row.get("email", "").strip()
        if not email:
            continue
        rec = by_email.setdefault(email, {
            "email": email, "telefon": "", "klient_id": "", "nazwa_kontaktu": "",
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


def main() -> int:
    assert_contact_parser_self_test()
    assert_vcard_decode_self_test()
    cfg = load_config()
    INBOX.mkdir(parents=True, exist_ok=True)
    OUT_PRIVATE.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    print("=== Footing System – update_footing_database ===")

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

    for phone, pc in sorted(contacts.items()):
        if not contact_creates_order(pc):
            if pc.surowa:
                reviews.append({
                    "powod": "kontakt bez pełnych danych zamówienia",
                    "klient_id": klient_id_from_phone(phone), "telefon": phone, "email": "",
                    "nazwa_kontaktu": pc.surowa, "data": pc.data_zamowienia,
                    "tresc_lub_nazwa": pc.surowa[:300],
                    "sugestia": "Uzupełnij datę, produkt i ilość w nazwie kontaktu",
                    "uwagi": "; ".join(pc.uwagi),
                })
            continue

        order_seq += 1
        oid = f"O-{order_seq:05d}"
        kid = klient_id_from_phone(phone)
        phone_to_order[phone] = oid
        status = "ok" if pc.pewny and pc.items else "do_sprawdzenia"
        if not pc.items:
            reviews.append({
                "powod": "data i ilość bez kodu produktu",
                "klient_id": kid, "telefon": phone, "email": "",
                "nazwa_kontaktu": pc.surowa, "data": pc.data_zamowienia,
                "tresc_lub_nazwa": pc.surowa[:300], "sugestia": "",
                "uwagi": "; ".join(pc.uwagi),
            })

        orders.append({
            "order_id": oid, "klient_id": kid, "data_zamowienia": pc.data_zamowienia,
            "zrodlo_glowne": "nazwa_kontaktu", "zastosowanie": pc.zastosowanie,
            "kwota_razem": "", "adres_dostawy": "", "status_sprawdzenia": status,
            "uwagi": "; ".join(pc.uwagi),
        })
        for it in pc.items:
            item_seq += 1
            items.append({
                "order_item_id": f"OI-{item_seq:05d}", "order_id": oid, "klient_id": kid,
                "data_zamowienia": pc.data_zamowienia,
                "produkt": it.kod_pelny if "-" in it.kod_pelny or "/" in it.kod_pelny else it.produkt,
                "wariant": it.wariant, "ilosc": it.ilosc,
                "cena_jednostkowa": "", "kwota_pozycji": "",
                "zrodlo": "nazwa_kontaktu", "status_sprawdzenia": "ok", "uwagi": "",
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
        if msg.email and kid and not client_emails[kid]:
            client_emails[kid] = msg.email

        if oid and oid in order_by_id:
            sup = extract_sms_supplement(msg.tresc)
            od = order_by_id[oid]
            if sup.get("kwota_razem") and not od["kwota_razem"]:
                od["kwota_razem"] = sup["kwota_razem"]
                od["uwagi"] = (od["uwagi"] + "; kwota uzupełniona z SMS").strip("; ")
            if sup.get("adres_dostawy") and not od["adres_dostawy"]:
                od["adres_dostawy"] = sup["adres_dostawy"]
            if sup.get("email") and kid and not client_emails[kid]:
                client_emails[kid] = sup["email"]

        komunikacja.append({
            "message_id": msg.message_id, "klient_id": kid, "data": msg.data,
            "kanal": msg.kanal, "kierunek": msg.kierunek, "telefon": msg.telefon,
            "email": msg.email, "temat": msg.temat,
            "tresc": msg.tresc.replace("\n", " | ")[:2000],
            "typ_wiadomosci": msg.typ_wiadomosci, "powiazane_order_id": oid,
            "status_sprawdzenia": "ok",
        })

    client_orders = Counter(o["klient_id"] for o in orders)
    all_phones = set(contacts.keys()) | {m.telefon for m in all_comm if m.telefon and not m.wewnetrzny}
    clients: list[dict] = []

    for phone in sorted(all_phones):
        if is_internal_phone(phone):
            continue
        pc = contacts.get(phone)
        kid = klient_id_from_phone(phone)
        dates = sorted(set(client_dates.get(kid, []) + ([pc.data_zamowienia] if pc and pc.data_zamowienia else [])))
        prods = [f"{it.ilosc}x{it.kod_pelny}" for it in pc.items] if pc else []
        zasts = [pc.zastosowanie] if pc and pc.zastosowanie else []
        status, uwagi = "ok", ""
        if pc and not pc.pewny:
            status, uwagi = "do_sprawdzenia", "; ".join(pc.uwagi)
        elif not pc:
            status, uwagi = "do_sprawdzenia", "brak nazwy kontaktu w cache"

        clients.append({
            "klient_id": kid, "telefon": phone,
            "email": client_emails.get(kid, ""),
            "nazwa_kontaktu": pc.surowa if pc else "",
            "data_z_kontaktu": pc.data_zamowienia if pc else "",
            "produkty_z_kontaktu": "; ".join(prods),
            "zastosowania": "; ".join(zasts),
            "miasto": pc.miasto if pc else "",
            "liczba_zamowien": client_orders.get(kid, 0),
            "pierwsza_data": dates[0] if dates else "",
            "ostatnia_data": dates[-1] if dates else "",
            "status_sprawdzenia": status, "uwagi": uwagi,
        })

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
    email_contact_rows = build_email_contacts(komunikacja, contacts)

    write_csv(OUT_PRIVATE / "KLIENCI.csv", CLIENT_COLS, clients)
    write_csv(OUT_PRIVATE / "ZAMOWIENIA.csv", ORDER_COLS, orders)
    write_csv(OUT_PRIVATE / "POZYCJE-ZAMOWIEN.csv", ITEM_COLS, items)
    write_csv(OUT_PRIVATE / "KOMUNIKACJA.csv", KOM_COLS, komunikacja)
    write_csv(OUT_PRIVATE / "DO-SPRAWDZENIA.csv", REVIEW_COLS, reviews)
    write_csv(OUT_PRIVATE / "EMAIL-KONTAKTY.csv", EMAIL_CONTACT_COLS, email_contact_rows)
    write_csv(OUT_PRIVATE / "SEO-FRAZY.csv", SEO_COLS, seo_rows)
    write_csv(OUT_PRIVATE / "SEGMENTY-KLIENTOW.csv", SEGMENT_COLS, segment_rows)

    stats = {
        "clients": len(clients), "orders": len(orders), "items": len(items),
        "komunikacja": len(komunikacja), "reviews": len(reviews), "excluded": excluded,
        "rank_qty": rank_qty.most_common(), "rank_apps": rank_apps.most_common(),
        "rank_seo": Counter(r["fraza"] for r in seo_rows).most_common(),
        "contacts_source": contacts_source,
    }
    write_public_reports(stats)
    send_slack(cfg, stats)

    print()
    print("=== Wynik ===")
    for label, val in [
        ("Klienci", stats["clients"]), ("Zamówienia", stats["orders"]),
        ("Pozycje", stats["items"]), ("Komunikacja", stats["komunikacja"]),
        ("Do sprawdzenia", stats["reviews"]), ("Wykluczone wewn.", stats["excluded"]),
    ]:
        print(f"  {label}: {val}")
    print(f"\nDane prywatne: {OUT_PRIVATE}")
    print(f"Raporty:        {REPORTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
