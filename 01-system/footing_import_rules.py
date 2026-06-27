"""Wspólne reguły importu kontaktów Footing (Google Contacts + parser nazw)."""

from __future__ import annotations

import re

KLIENT_NAME_RE = re.compile(r"\bklient\b", re.I)

FULL_DATE_PATTERNS = [
    re.compile(r"\b(\d{4})\.(\d{2})\.(\d{2})\b"),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b"),
    re.compile(r"\b(\d{2})-(\d{2})-(\d{4})\b"),
]

FOOTING_PRODUCT_PATTERNS = [
    re.compile(r"F25\b", re.I),
    re.compile(r"F2(?:[\-/=][A-Z0-9]+|[A-Z]\d+[A-Z0-9]*)", re.I),
    re.compile(r"Z(?:16|17|25|26)(?:[\-/=][A-Z0-9/]+|[A-Z]\d+[A-Z0-9/]*)", re.I),
    re.compile(r"K\d+(?:[\-/=][A-Z0-9/]+|[A-Z]\d+[A-Z0-9/]*)", re.I),
    re.compile(r"H\d+(?:[\-/=][A-Z0-9/]+|[A-Z]\d+[A-Z0-9/]*)", re.I),
    re.compile(r"W2001\b", re.I),
    re.compile(r"W2002\b", re.I),
    re.compile(r"W400\b", re.I),
    re.compile(r"W35(?:[\-/=]?[A-Z0-9]+)?", re.I),
    re.compile(r"W40\b", re.I),
]

IMPORT_ACCEPTED = "name_contains_klient_date_product"

QTY_PRODUCT_RE = re.compile(
    r"(\d+)\s*[*x×X]\s*"
    r"((?:Z(?:16|17|25|26)|K\d+|H\d+|W(?:35|40|400|2001|2002)|F25|F2)"
    r"(?:[\-/=][A-Z0-9/]+|[A-Z]\d+[A-Z0-9/]*)?)",
    re.I,
)

STANDALONE_PRODUCT_RE = re.compile(
    r"(?<![A-Z0-9/])"
    r"((?:Z(?:16|17|25|26)|K\d+|H\d+|W(?:35|40|400|2001|2002)|F25|F2)"
    r"(?:[\-/=][A-Z0-9/]+|[A-Z]\d+[A-Z0-9/]*)?)"
    r"(?![A-Z0-9])",
    re.I,
)

UNKNOWN_QTY_RE = re.compile(r"(\d+)\s*[*x×X]\s*(.+)", re.I)

INTERNAL_EMAIL_RE = re.compile(r"footing|taciak|taciakowo", re.I)

REJECT_EMAIL_RE = re.compile(
    r"@(nazwa\.pl|informacyjny\.|newsletter\.|powiadomienia\.)|"
    r"^(no-?reply|noreply|donotreply|postmaster|mailer-daemon|bounce|"
    r"newsletter|powiadomienia|system|robot)@",
    re.I,
)

NON_FOOTING_CONTACT_RE = re.compile(
    r"zegar|opon|przyczep|cz[eę][sś]ci\s|silnik|\bauto\b|silotop|fortschritt|"
    r"przew[oó]d|poid[lł]|szyba\s+boczna",
    re.I,
)

POMINIETE_SUGESTIE = {
    "excluded_missing_klient": "Dodaj słowo Klient w nazwie kontaktu zamówienia",
    "excluded_missing_date": "Dodaj pełną datę w formacie YYYY.MM.DD (np. 2026.06.23)",
    "excluded_missing_product": "Dodaj kod produktu Footing (np. Z26-M20, Z25K130C, K2-K300)",
    "excluded_not_footing_order": "Kontakt nie wygląda na zamówienie Footing – zostaw poza cache",
}


def spans_overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def span_covered(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
    return any(spans_overlap(span, occ) for occ in occupied)


def norm_code(code: str) -> str:
    return re.sub(r"[\s\-/=]", "", (code or "").upper())


def is_embedded_code(code: str, parents: set[str]) -> bool:
    cn = norm_code(code)
    if not cn:
        return False
    for parent in parents:
        pn = norm_code(parent)
        if cn != pn and cn in pn:
            return True
    return False


def has_full_date(text: str) -> bool:
    return any(p.search(text or "") for p in FULL_DATE_PATTERNS)


def has_footing_product(text: str) -> bool:
    return any(p.search(text or "") for p in FOOTING_PRODUCT_PATTERNS)


def evaluate_google_contact(nazwa: str) -> tuple[bool, str, str]:
    nazwa = (nazwa or "").strip()
    has_k = bool(KLIENT_NAME_RE.search(nazwa))
    has_d = has_full_date(nazwa)
    has_p = has_footing_product(nazwa)

    if not has_k:
        return False, "excluded_missing_klient", POMINIETE_SUGESTIE["excluded_missing_klient"]
    if not has_d and not has_p:
        return False, "excluded_not_footing_order", POMINIETE_SUGESTIE["excluded_not_footing_order"]
    if not has_d:
        return False, "excluded_missing_date", POMINIETE_SUGESTIE["excluded_missing_date"]
    if not has_p:
        return False, "excluded_missing_product", POMINIETE_SUGESTIE["excluded_missing_product"]
    return True, IMPORT_ACCEPTED, ""


def is_internal_email(email: str) -> bool:
    return bool(email and INTERNAL_EMAIL_RE.search(email))


def sanitize_email(email: str) -> tuple[str, str]:
    email = (email or "").strip().lower()
    if not email:
        return "", ""
    if is_internal_email(email):
        return "", email
    if REJECT_EMAIL_RE.search(email):
        return "", email
    return email, ""


def find_qty_products(text: str) -> list[tuple[str, str]]:
    return [(qty, code) for qty, code in QTY_PRODUCT_RE.findall(text or "")]


def find_qty_product_matches(text: str) -> list[tuple[int, int, str, str, str]]:
    """Zwraca: start, end, qty, code, surowy."""
    out: list[tuple[int, int, str, str, str]] = []
    for m in QTY_PRODUCT_RE.finditer(text or ""):
        out.append((m.start(), m.end(), m.group(1), m.group(2), m.group(0)))
    return out


def find_standalone_products(text: str, occupied: list[tuple[int, int]], qty_codes: set[str]) -> list[str]:
    found: list[str] = []
    for m in STANDALONE_PRODUCT_RE.finditer(text or ""):
        span = (m.start(), m.end())
        if span_covered(span, occupied):
            continue
        code = m.group(1)
        if is_embedded_code(code, qty_codes):
            continue
        norm = norm_code(code)
        if norm in {norm_code(c) for c in qty_codes}:
            continue
        found.append(code)
        occupied.append(span)
    return found


def find_unknown_qty_products(text: str, occupied: list[tuple[int, int]], qty_codes: set[str]) -> list[tuple[str, str, str]]:
    """Zwraca qty, tail, surowy dla tekstów z ilością spoza słownika."""
    out: list[tuple[str, str, str]] = []
    for m in UNKNOWN_QTY_RE.finditer(text or ""):
        span = (m.start(), m.end())
        if span_covered(span, occupied):
            continue
        qty, tail = m.group(1), m.group(2).strip()
        if has_footing_product(tail):
            continue
        if is_embedded_code(tail, qty_codes):
            continue
        out.append((qty, tail, m.group(0)))
        occupied.append(span)
    return out
