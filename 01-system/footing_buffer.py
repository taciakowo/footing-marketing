"""Bufor akceptacji Footing – kandydaci z SMS/e-mail/Quick Order."""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from footing_csv import normalize_text, write_csv as csv_write
from footing_order_core import (
    ItemsParseResult,
    ParsedLineItem,
    build_tytul_sprawy,
    extract_skrot_nazwy,
    format_event_date_display,
    normalize_event_date,
    parse_items_text,
)

NIP_RE = re.compile(r"\bNIP\b\s*[:\-]?\s*(\d[\d\-]{8,12})", re.I)
INVOICE_RE = re.compile(r"faktur|rachunek|dane\s+do\s+faktury|dane\s+do\s+rachunku", re.I)
DELIVERY_RE = re.compile(r"dostaw|wysyłk|wysylk|adres\s+dostaw", re.I)
ORDER_INTENT_RE = re.compile(
    r"zamawiam|zamówienie|zamowienie|poprosz[eę]|prosz[eę]\s+o|wycen|potwierdzam\s+zam",
    re.I,
)
CLIENT_NAME_RE = re.compile(
    r"(?:nazwa|firma|klient)\s*[:\-]\s*([A-ZĄĆĘŁŃÓŚŹŻ][^\n,;]{2,60})",
    re.I,
)
POSTAL_RE = re.compile(r"\b(\d{2}-\d{3})\b")
EMAIL_INLINE_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SYSTEM_NOTIFICATION_RE = re.compile(
    r"newsletter|no-?reply|noreply|donotreply|mailer-daemon|bounce|"
    r"@nazwa\.pl|powiadomienia\.|informacyjny\.|"
    r"\ballegro\b.*(?:zamówien|status|paczk)|apaczka|ceneo|"
    r"woocommerce.*(?:status|zamówienie\s+#)|paczka\s+o\s+nr|"
    r"inteligo|alior\s+bank|orange\b|google\s+alert|"
    r"praw[eo]\s+pracy|zmian\s+w\s+prawie|subskrypcj|wypisz\s+si[eę]",
    re.I,
)
NON_COMMERCIAL_RE = re.compile(
    r"praw[eo]\s+pracy|zmian\s+w\s+prawie|newsletter|RODO|marketing\s+automatyczny",
    re.I,
)

BUFOR_DIR_NAME = "bufor"

BUFOR_KLIENCI_COLS = [
    "status_bufora", "powod_bufora", "tytul_sprawy", "zrodlo", "data", "telefon", "email",
    "nazwa_klienta", "adres", "nr_adresu", "nr_lokalu", "kod_pocztowy", "miasto", "nip",
    "produkty", "sugestia", "uwagi", "fragment_tresci",
    "source_id", "candidate_id", "hash", "user_merge_key", "source_ids", "liczba_zrodel", "created_at",
]
BUFOR_ZAMOWIENIA_COLS = [
    "status_bufora", "powod_bufora", "data_zamowienia", "tytul_sprawy", "zrodlo", "telefon",
    "produkty", "ilosc_sztuk", "liczba_pozycji", "inwestycja", "kwota", "dostawa",
    "adres_dostawy", "email", "nazwa_klienta", "status_sprawdzenia", "sugestia", "uwagi",
    "zamowienie_candidate_id", "klient_candidate_id", "source_id", "hash",
    "user_merge_key", "source_ids", "liczba_zrodel", "created_at",
]
BUFOR_POZYCJE_COLS = [
    "status_bufora", "powod_bufora", "data_zamowienia", "tytul_sprawy", "zrodlo", "telefon",
    "ilosc", "produkt", "wariant", "nr_katalogowy", "opis_pozycji", "inwestycja",
    "status_sprawdzenia", "sugestia", "uwagi",
    "pozycja_candidate_id", "zamowienie_candidate_id", "klient_candidate_id", "source_id",
    "hash", "user_merge_key", "source_ids", "liczba_zrodel", "created_at",
]
UNRELATED_COLS = [
    "powod", "telefon", "email", "nazwa_lub_nadawca", "pierwsza_data", "ostatnia_data",
    "zrodlo", "fragment_tresci", "sugestia", "uwagi", "source_id", "hash",
]

COMMERCIAL_MSG_TYPES = frozenset({
    "wycena", "zapytanie", "podsumowanie_zamowienia", "potwierdzenie_platnosci",
    "prośba_o_dane",
})
STRONG_FOOTING = re.compile(
    r"footing\.pl|\bZ2[567]\b|\bZ17\b|\bfundament|\bkotw|\bocynk|"
    r"stop[aąęy]\s+fundament|podstaw[aąęy]", re.I,
)

LIMIT_TYTUL = 120
LIMIT_PRODUKTY = 160
LIMIT_OPIS = 120

STOP_PHRASES = (
    r"Dane do przelewu", r"Nr rach", r"Numer rachunku", r"mBank", r"Blik", r"Tytuł:",
    r"Pozdrawiam", r"Z poważaniem", r"Wysłane z", r"Sent from", r"Odbiorca:",
    r"Razem do zapłaty", r"Razem:", r"Dostawa:", r"Adres dostawy:", r"Faktura:",
    r"NIP:", r"Tel\.", r"Telefon", r"Mob\.", r", dane:",
)
STOP_PHRASE_RE = re.compile("|".join(re.escape(p) for p in STOP_PHRASES), re.I)
APPLICATION_SHORT_RE = re.compile(
    r"\b(pergol\w*|altan\w*|wiata\w*|domek\w*|fotowoltaik\w*|ogrodzen\w*)\b", re.I,
)
BANK_NOISE_RE = re.compile(
    r"przelew|rachunek|mbank|blik|IBAN|\d{26}|konto\s+bank", re.I,
)
PHONE_IN_TEXT_RE = re.compile(r"\+?\d{9,12}|\b\d{3}[\s\-]\d{3}[\s\-]\d{3}\b")
PRODUCT_GARBAGE_RE = re.compile(
    r"\.png|\.jpg|\.gif|\.jpeg|width\s*=|height\s*=|alt\s*=|<|>|https?://|www\.|woocommerce|"
    r"border\s*=|style\s*=",
    re.I,
)
HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html_noise(text: str) -> str:
    text = HTML_TAG_RE.sub(" ", text or "")
    text = PRODUCT_GARBAGE_RE.sub(" ", text)
    return normalize_text(text)


def looks_like_product_text(s: str) -> bool:
    s = (s or "").strip()
    if not s or len(s) > 80:
        return False
    if PRODUCT_GARBAGE_RE.search(s) or BANK_NOISE_RE.search(s) or PHONE_IN_TEXT_RE.search(s):
        return False
    if re.search(r"\d{10,}", s) or '"' in s:
        return False
    return True


def filter_parsed_items(parsed: ItemsParseResult) -> ItemsParseResult:
    good: list[ParsedLineItem] = []
    for it in parsed.items:
        code = it.nr_katalogowy or it.produkt
        if it.znany_slownik and looks_like_product_text(code):
            good.append(it)
        elif it.znany_slownik:
            continue
        elif looks_like_product_text(code):
            good.append(it)
    parts: list[str] = []
    total_qty = 0
    worst = "ok"
    for it in good:
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
    out = ItemsParseResult(
        items=good,
        liczba_pozycji=len(good),
        ilosc_sztuk=total_qty,
        produkty_tekst="; ".join(parts),
        status_sprawdzenia=worst if good else "wymaga_korekty",
        uwagi=list(parsed.uwagi),
    )
    if not good and parsed.items:
        out.uwagi.append("odfiltrowano_pozycje_nieproduktowe")
    return out


def truncate_at_stoplist(text: str) -> str:
    if not text:
        return ""
    m = STOP_PHRASE_RE.search(text)
    return text[: m.start()].strip() if m else text.strip()


def limit_field(text: str, max_len: int) -> tuple[str, bool]:
    text = normalize_text(text)
    if len(text) <= max_len:
        return text, False
    cut = text[:max_len].rsplit(" ", 1)[0].strip() if " " in text[:max_len] else text[:max_len].strip()
    return cut or text[:max_len], True


def extract_inwestycja_short(text: str, hint: str = "") -> str:
    for src in (hint, truncate_at_stoplist(text)[:300]):
        if not src:
            continue
        m = APPLICATION_SHORT_RE.search(src)
        if m:
            return m.group(1).capitalize()
    return ""


def sanitize_produkty_text(produkty: str) -> str:
    if not produkty:
        return ""
    s = truncate_at_stoplist(produkty)
    if BANK_NOISE_RE.search(s) or PHONE_IN_TEXT_RE.search(s):
        return ""
    return s.strip()


def prepare_parse_window(raw_text: str) -> tuple[str, str]:
    full = strip_html_noise(normalize_text(raw_text))
    window = truncate_at_stoplist(full)
    if len(window) > 500:
        window = window[:500].strip()
    return window, full


def resanitize_buffer_row(row: dict, typ: str) -> None:
    fragment = row.get("fragment_tresci") or ""
    data = row.get("data") or row.get("data_zamowienia") or ""
    notes: list[str] = []
    if fragment:
        parsed, tytul, produkty, inwestycja, _skrot, _full, field_notes = prepare_buffer_fields(
            fragment, data, row.get("inwestycja", ""),
        )
        notes.extend(field_notes)
        row["tytul_sprawy"] = tytul
        if typ in ("klient", "zamowienie"):
            row["produkty"] = produkty
            row["inwestycja"] = inwestycja
            if typ == "zamowienie":
                row["ilosc_sztuk"] = parsed.ilosc_sztuk
                row["liczba_pozycji"] = parsed.liczba_pozycji
                if parsed.status_sprawdzenia != "ok":
                    row["status_sprawdzenia"] = parsed.status_sprawdzenia
    else:
        for field, limit in (
            ("tytul_sprawy", LIMIT_TYTUL),
            ("produkty", LIMIT_PRODUKTY),
            ("opis_pozycji", LIMIT_OPIS),
        ):
            if field not in row:
                continue
            val = truncate_at_stoplist(strip_html_noise(row.get(field) or ""))
            val = sanitize_produkty_text(val) if field == "produkty" else val
            val, truncated = limit_field(val, limit)
            if truncated:
                notes.append("skrocono_opis_zrodlowy")
            row[field] = val
    tytul = row.get("tytul_sprawy", "")
    if (
        PRODUCT_GARBAGE_RE.search(tytul)
        or BANK_NOISE_RE.search(tytul)
        or len(tytul) > LIMIT_TYTUL
    ):
        date_disp = format_event_date_display(normalize_event_date(data))
        prod = sanitize_produkty_text(row.get("produkty", ""))
        rebuilt = f"{date_disp} Klient {prod}".strip() if prod else f"{date_disp} Klient"
        row["tytul_sprawy"], truncated = limit_field(rebuilt, LIMIT_TYTUL)
        if truncated:
            notes.append("skrocono_opis_zrodlowy")
    if notes:
        uw = row.get("uwagi") or ""
        for n in notes:
            if n not in uw:
                uw = f"{uw}; {n}".strip("; ")
        row["uwagi"] = uw


def resanitize_buffer_store(store: BufferStore) -> None:
    for row in store.klienci:
        resanitize_buffer_row(row, "klient")
    for row in store.zamowienia:
        resanitize_buffer_row(row, "zamowienie")
    for row in store.pozycje:
        tytul = truncate_at_stoplist(strip_html_noise(row.get("tytul_sprawy") or ""))
        tytul, trunc = limit_field(tytul, LIMIT_TYTUL)
        row["tytul_sprawy"] = tytul
        if trunc:
            uw = row.get("uwagi") or ""
            if "skrocono_opis_zrodlowy" not in uw:
                row["uwagi"] = f"{uw}; skrocono_opis_zrodlowy".strip("; ")
        produkt, nr_kat, opis, status, opis_trunc = clean_line_item_for_buffer(
            ParsedLineItem(
                ilosc=row.get("ilosc", ""),
                produkt=row.get("produkt", ""),
                wariant=row.get("wariant", ""),
                nr_katalogowy=row.get("nr_katalogowy", ""),
                surowy=row.get("opis_pozycji", ""),
                znany_slownik=bool(row.get("nr_katalogowy")),
                status_sprawdzenia=row.get("status_sprawdzenia", "ok"),
            )
        )
        row["produkt"] = produkt
        row["nr_katalogowy"] = nr_kat
        row["opis_pozycji"] = opis
        row["status_sprawdzenia"] = status
        if opis_trunc:
            uw = row.get("uwagi") or ""
            if "skrocono_opis_zrodlowy" not in uw:
                row["uwagi"] = f"{uw}; skrocono_opis_zrodlowy".strip("; ")


def prepare_buffer_fields(
    raw_text: str,
    data: str,
    inwestycja_hint: str = "",
) -> tuple[ItemsParseResult, str, str, str, str, str, list[str]]:
    parse_window, full = prepare_parse_window(raw_text)
    parsed = filter_parsed_items(parse_items_text(parse_window))
    inwestycja = extract_inwestycja_short(full, inwestycja_hint)
    skrot = extract_skrot_nazwy(truncate_at_stoplist(full)[:200])
    tytul = build_tytul_sprawy(data or datetime.now().strftime("%Y-%m-%d"), parsed, inwestycja, skrot)
    produkty_raw = sanitize_produkty_text(parsed.produkty_tekst)
    produkty, trunc_p = limit_field(produkty_raw, LIMIT_PRODUKTY)
    tytul, trunc_t = limit_field(tytul, LIMIT_TYTUL)
    notes: list[str] = []
    if trunc_p or trunc_t:
        notes.append("skrocono_opis_zrodlowy")
    return parsed, tytul, produkty, inwestycja, skrot, full, notes


def clean_line_item_for_buffer(it: ParsedLineItem) -> tuple[str, str, str, str, bool]:
    produkt = truncate_at_stoplist(it.produkt or "")[:60].strip()
    nr = truncate_at_stoplist(it.nr_katalogowy or "")[:40].strip()
    if BANK_NOISE_RE.search(nr) or BANK_NOISE_RE.search(produkt):
        nr, produkt = "", ""
    if it.znany_slownik and it.nr_katalogowy:
        opis_base = it.nr_katalogowy
        if it.wariant:
            opis_base = f"{it.produkt}-{it.wariant}" if it.produkt else it.nr_katalogowy
    else:
        opis_base = nr or produkt or (it.nr_katalogowy or "")[:60]
    opis, truncated = limit_field(opis_base, LIMIT_OPIS)
    status = it.status_sprawdzenia
    if not nr and not produkt and not it.znany_slownik:
        status = "wymaga_korekty"
    return produkt, nr, opis, status, truncated


def normalize_merge_token(val: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(val).lower()).strip()


def build_user_merge_key(typ: str, row: dict) -> str:
    if typ == "klient":
        parts = (
            typ,
            normalize_merge_token(row.get("telefon", "")),
            normalize_merge_token(row.get("email", "")),
            normalize_merge_token(row.get("data", "")),
            normalize_merge_token(row.get("tytul_sprawy", "")),
            normalize_merge_token(row.get("produkty", "")),
            "",
            "",
        )
    elif typ == "zamowienie":
        parts = (
            typ,
            normalize_merge_token(row.get("telefon", "")),
            normalize_merge_token(row.get("email", "")),
            normalize_merge_token(row.get("data_zamowienia", "")),
            normalize_merge_token(row.get("tytul_sprawy", "")),
            normalize_merge_token(row.get("produkty", "")),
            normalize_merge_token(row.get("ilosc_sztuk", "")),
            normalize_merge_token(row.get("adres_dostawy", "")),
        )
    else:
        parts = (
            typ,
            normalize_merge_token(row.get("telefon", "")),
            "",
            normalize_merge_token(row.get("data_zamowienia", "")),
            normalize_merge_token(row.get("tytul_sprawy", "")),
            normalize_merge_token(row.get("nr_katalogowy", "") or row.get("produkt", "")),
            normalize_merge_token(row.get("ilosc", "")),
            "",
        )
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def merge_rows_by_user_key(rows: list[dict], typ: str) -> tuple[list[dict], int]:
    merged = 0
    by_key: dict[str, dict] = {}
    for row in rows:
        key = build_user_merge_key(typ, row)
        row["user_merge_key"] = key
        sid = (row.get("source_id") or "").strip()
        if key in by_key:
            existing = by_key[key]
            ids = [x for x in (existing.get("source_ids") or existing.get("source_id") or "").split("|") if x]
            if sid and sid not in ids:
                ids.append(sid)
            existing["source_ids"] = "|".join(sorted(ids))
            existing["liczba_zrodel"] = str(len(ids))
            uw = existing.get("uwagi") or ""
            if "scalono_duplikaty_bufora" not in uw:
                existing["uwagi"] = f"{uw}; scalono_duplikaty_bufora".strip("; ")
            merged += 1
        else:
            row["source_ids"] = sid
            row["liczba_zrodel"] = "1" if sid else "0"
            by_key[key] = row
    return list(by_key.values()), merged


def detect_commercial_signals(text: str, typ_wiadomosci: str = "") -> list[str]:
    text = normalize_text(text)
    parse_window = truncate_at_stoplist(text)
    signals: list[str] = []
    parsed = parse_items_text(parse_window)
    if parsed.items:
        signals.append("produkt_lub_ilosc")
    elif re.search(r"\d+\s*[*x×X]\s*\S+", parse_window, re.I):
        signals.append("produkt_lub_ilosc")
    if NIP_RE.search(text):
        signals.append("nip")
    if INVOICE_RE.search(text):
        signals.append("dane_do_faktury")
    if DELIVERY_RE.search(text) or POSTAL_RE.search(text):
        signals.append("dane_wysylki")
    if EMAIL_INLINE_RE.search(text):
        signals.append("email_w_tresci")
    if CLIENT_NAME_RE.search(text):
        signals.append("nazwa_klienta")
    if ORDER_INTENT_RE.search(text):
        signals.append("intencja_zamowienia")
    if typ_wiadomosci in COMMERCIAL_MSG_TYPES:
        signals.append(f"typ_{typ_wiadomosci}")
    if STRONG_FOOTING.search(text):
        signals.append("kontekst_footing")
    return signals


def candidate_hash(
    zrodlo: str,
    telefon: str = "",
    email: str = "",
    data: str = "",
    produkty: str = "",
    kwota: str = "",
    adres: str = "",
    fragment: str = "",
) -> str:
    payload = "|".join(
        normalize_text(p) for p in (zrodlo, telefon, email, data, produkty, kwota, adres, fragment[:200])
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def quick_order_content_hash(
    *,
    telefon: str,
    data: str,
    items_text: str,
    zrodlo: str = "quick_order",
    inwestycja: str = "",
    nazwa_klienta: str = "",
) -> str:
    """Stabilny hash treści zdarzenia – ten sam JSON daje ten sam hash."""
    parse_window, _ = prepare_parse_window(items_text or "")
    parsed = parse_items_text(parse_window)
    produkty = sanitize_produkty_text(parsed.produkty_tekst) or parse_window[:80]
    return candidate_hash(
        zrodlo,
        telefon,
        "",
        data,
        produkty,
        "",
        inwestycja,
        nazwa_klienta,
    )


def is_system_notification(text: str, email: str, temat: str) -> bool:
    blob = " ".join(filter(None, [text, email, temat]))
    return bool(SYSTEM_NOTIFICATION_RE.search(blob))


def extract_nip(text: str) -> str:
    m = NIP_RE.search(text or "")
    return re.sub(r"\D", "", m.group(1)) if m else ""


def extract_client_name(text: str) -> str:
    m = CLIENT_NAME_RE.search(text or "")
    return normalize_text(m.group(1)) if m else ""


def extract_postal_city(text: str) -> tuple[str, str]:
    m = POSTAL_RE.search(text or "")
    kod = m.group(1) if m else ""
    miasto = ""
    if m:
        after = text[m.end(): m.end() + 40].strip(" ,.-")
        parts = after.split()
        if parts:
            miasto = parts[0].strip(",.")
    return kod, miasto


def match_clean_clients(
    clean_clients: list[dict],
    telefon: str = "",
    email: str = "",
    nip: str = "",
    nazwa_klienta: str = "",
    miasto: str = "",
) -> tuple[list[str], str]:
    """Zwraca listę klient_id dopasowań i sugestię tekstową."""
    matches: set[str] = set()
    telefon = (telefon or "").strip()
    email = (email or "").strip().lower()
    nip = re.sub(r"\D", "", nip or "")
    nazwa = normalize_text(nazwa_klienta).lower()
    miasto_l = normalize_text(miasto).lower()

    for c in clean_clients:
        if telefon and c.get("telefon") == telefon:
            matches.add(c["klient_id"])
        if email and (c.get("email") or "").lower() == email:
            matches.add(c["klient_id"])
        if nip and re.sub(r"\D", "", c.get("nip") or "") == nip:
            matches.add(c["klient_id"])
        if nazwa and len(nazwa) >= 3:
            ck = normalize_text(c.get("nazwa_klienta") or "").lower()
            if ck and nazwa in ck or ck in nazwa:
                if not miasto_l or miasto_l in normalize_text(c.get("miasto") or "").lower():
                    matches.add(c["klient_id"])

    ordered = sorted(matches)
    if len(ordered) == 1:
        return ordered, f"Powiąż z istniejącym klientem {ordered[0]}"
    if len(ordered) > 1:
        return ordered, f"Konflikt dopasowania – sprawdź klientów: {', '.join(ordered)}"
    return [], "Utwórz nowego klienta po akceptacji w panelu"


class BufferStore:
    def __init__(self) -> None:
        self.klienci: list[dict] = []
        self.zamowienia: list[dict] = []
        self.pozycje: list[dict] = []
        self.unrelated: list[dict] = []
        self._hashes: set[str] = set()
        self._seq_k = self._seq_z = self._seq_p = 0
        self.user_merge_merged = 0

    def load_existing(self, bufor_dir: Path) -> None:
        paths = [
            (bufor_dir / "BUFOR-KLIENCI-DO-AKCEPTACJI.csv", "klienci"),
            (bufor_dir / "BUFOR-ZAMOWIENIA-DO-AKCEPTACJI.csv", "zamowienia"),
            (bufor_dir / "BUFOR-POZYCJE-DO-AKCEPTACJI.csv", "pozycje"),
            (bufor_dir.parent / "KONTAKTY-Z-KOMUNIKACJI-NIEPOWIAZANE.csv", "unrelated"),
        ]
        for path, key in paths:
            if not path.exists():
                continue
            with path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f, delimiter=";"):
                    h = (row.get("hash") or "").strip()
                    if h:
                        self._hashes.add(h)
                    getattr(self, key).append(row)
        for r in self.klienci:
            cid = r.get("candidate_id", "")
            if cid.startswith("BC-"):
                try:
                    self._seq_k = max(self._seq_k, int(cid.split("-")[-1]))
                except ValueError:
                    pass
        for r in self.zamowienia:
            zid = r.get("zamowienie_candidate_id", "")
            if zid.startswith("BZ-"):
                try:
                    self._seq_z = max(self._seq_z, int(zid.split("-")[-1]))
                except ValueError:
                    pass
        for r in self.pozycje:
            pid = r.get("pozycja_candidate_id", "")
            if pid.startswith("BP-"):
                try:
                    self._seq_p = max(self._seq_p, int(pid.split("-")[-1]))
                except ValueError:
                    pass

    def _next_id(self, prefix: str) -> str:
        if prefix == "BC":
            self._seq_k += 1
            return f"BC-{self._seq_k:06d}"
        if prefix == "BZ":
            self._seq_z += 1
            return f"BZ-{self._seq_z:06d}"
        self._seq_p += 1
        return f"BP-{self._seq_p:06d}"

    def add_unrelated(self, row: dict) -> bool:
        h = row.get("hash") or candidate_hash(
            row.get("zrodlo", ""), row.get("telefon", ""), row.get("email", ""),
            row.get("pierwsza_data", ""), fragment=row.get("fragment_tresci", ""),
        )
        if h in self._hashes:
            return False
        row["hash"] = h
        self._hashes.add(h)
        self.unrelated.append(row)
        return True

    def add_candidate(
        self,
        *,
        zrodlo: str,
        source_id: str,
        data: str,
        telefon: str,
        email: str,
        text: str,
        typ_wiadomosci: str,
        nazwa_nadawcy: str,
        clean_clients: list[dict],
        extract_supplement_fn,
        has_footing_product_fn,
        nr_katalogowy_fn,
    ) -> bool:
        text = normalize_text(text)
        if is_system_notification(text, email, nazwa_nadawcy):
            return self.add_unrelated({
                "powod": "powiadomienie_systemowe",
                "telefon": telefon,
                "email": email,
                "nazwa_lub_nadawca": nazwa_nadawcy,
                "pierwsza_data": data,
                "ostatnia_data": data,
                "zrodlo": zrodlo,
                "fragment_tresci": text[:200],
                "sugestia": "Brak sensu handlowego – archiwum techniczne",
                "uwagi": "",
                "source_id": source_id,
            })

        if NON_COMMERCIAL_RE.search(text):
            return self.add_unrelated({
                "powod": "tresc_niehandlowa",
                "telefon": telefon,
                "email": email,
                "nazwa_lub_nadawca": nazwa_nadawcy,
                "pierwsza_data": data,
                "ostatnia_data": data,
                "zrodlo": zrodlo,
                "fragment_tresci": text[:200],
                "sugestia": "Treść bez kontekstu zamówienia Footing",
                "uwagi": "",
                "source_id": source_id,
            })

        signals = detect_commercial_signals(text, typ_wiadomosci)
        if not signals and not has_footing_product_fn(text):
            return self.add_unrelated({
                "powod": "brak_sygnalu_handlowego",
                "telefon": telefon,
                "email": email,
                "nazwa_lub_nadawca": nazwa_nadawcy,
                "pierwsza_data": data,
                "ostatnia_data": data,
                "zrodlo": zrodlo,
                "fragment_tresci": text[:200],
                "sugestia": "Tylko ślad komunikacji bez kontekstu zamówienia",
                "uwagi": "",
                "source_id": source_id,
            })

        sup = extract_supplement_fn(text) if extract_supplement_fn else {}
        parsed, tytul, produkty, inwestycja, _skrot, full_text, field_notes = prepare_buffer_fields(text, data)
        kwota = sup.get("kwota_razem", "")
        adres_dostawy = sup.get("adres_dostawy", "")
        nip = extract_nip(text)
        nazwa_klienta = extract_client_name(text)
        kod, miasto = extract_postal_city(text)

        h = candidate_hash(zrodlo, telefon, email, data, produkty, kwota, adres_dostawy, text[:120])
        if h in self._hashes:
            return False

        matches, match_sug = match_clean_clients(
            clean_clients, telefon, email or sup.get("email", ""), nip, nazwa_klienta, miasto,
        )
        status_bufora = "wymaga_korekty" if len(matches) > 1 else "do_akceptacji"
        powod_bufora = "konflikt_dopasowania_klienta" if len(matches) > 1 else "kandydat_z_komunikacji"
        if matches and len(matches) == 1:
            match_sug = f"{match_sug}; nie nadpisuj danych zaakceptowanych automatycznie"

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cid = self._next_id("BC")
        zid = self._next_id("BZ") if parsed.items or produkty else ""
        uwagi_parts = [f"sygnały: {', '.join(signals)}"]
        uwagi_parts.extend(field_notes)

        client_row = {
            "status_bufora": status_bufora,
            "powod_bufora": powod_bufora,
            "tytul_sprawy": tytul,
            "zrodlo": zrodlo,
            "data": data,
            "telefon": telefon,
            "email": email or sup.get("email", ""),
            "nazwa_klienta": nazwa_klienta,
            "adres": adres_dostawy,
            "nr_adresu": "", "nr_lokalu": "",
            "kod_pocztowy": kod,
            "miasto": miasto,
            "nip": nip,
            "produkty": produkty,
            "sugestia": match_sug,
            "uwagi": "; ".join(uwagi_parts),
            "fragment_tresci": full_text[:500],
            "source_id": source_id,
            "candidate_id": cid,
            "hash": h,
            "created_at": now,
        }
        self.klienci.append(client_row)
        self._hashes.add(h)

        if zid:
            order_status = parsed.status_sprawdzenia
            if not produkty and parsed.status_sprawdzenia == "ok":
                order_status = "wymaga_korekty"
            zh = candidate_hash(zrodlo, telefon, email, data, produkty, kwota, adres_dostawy, f"order|{text[:80]}")
            if zh not in self._hashes:
                self.zamowienia.append({
                    "status_bufora": status_bufora,
                    "powod_bufora": powod_bufora,
                    "data_zamowienia": data,
                    "tytul_sprawy": tytul,
                    "zrodlo": zrodlo,
                    "telefon": telefon,
                    "produkty": produkty,
                    "ilosc_sztuk": parsed.ilosc_sztuk,
                    "liczba_pozycji": parsed.liczba_pozycji,
                    "inwestycja": inwestycja,
                    "kwota": kwota,
                    "dostawa": "",
                    "adres_dostawy": adres_dostawy,
                    "email": email or sup.get("email", ""),
                    "nazwa_klienta": nazwa_klienta,
                    "status_sprawdzenia": order_status,
                    "sugestia": match_sug,
                    "uwagi": "; ".join(uwagi_parts),
                    "zamowienie_candidate_id": zid,
                    "klient_candidate_id": cid,
                    "source_id": source_id,
                    "hash": zh,
                    "created_at": now,
                })
                self._hashes.add(zh)
                for it in parsed.items:
                    produkt, nr_kat, opis, item_status, opis_trunc = clean_line_item_for_buffer(it)
                    ph = candidate_hash(
                        zrodlo, telefon, "", data, nr_kat or produkt, it.ilosc, "", opis,
                    )
                    if ph in self._hashes:
                        continue
                    pid = self._next_id("BP")
                    poz_uwagi = list(field_notes)
                    if opis_trunc:
                        poz_uwagi.append("skrocono_opis_zrodlowy")
                    self.pozycje.append({
                        "status_bufora": status_bufora,
                        "powod_bufora": powod_bufora,
                        "data_zamowienia": data,
                        "tytul_sprawy": tytul,
                        "zrodlo": zrodlo,
                        "telefon": telefon,
                        "ilosc": it.ilosc,
                        "produkt": produkt,
                        "wariant": it.wariant,
                        "nr_katalogowy": nr_kat,
                        "opis_pozycji": opis,
                        "inwestycja": inwestycja,
                        "status_sprawdzenia": item_status,
                        "sugestia": match_sug,
                        "uwagi": "; ".join(poz_uwagi),
                        "pozycja_candidate_id": pid,
                        "zamowienie_candidate_id": zid,
                        "klient_candidate_id": cid,
                        "source_id": source_id,
                        "hash": ph,
                        "created_at": now,
                    })
                    self._hashes.add(ph)
        return True

    def add_quick_order(
        self,
        *,
        event_id: str,
        data: str,
        telefon: str,
        tytul_sprawy: str,
        parsed: ItemsParseResult,
        inwestycja: str,
        nazwa_klienta: str,
        kwota: str = "",
        adres_dostawy: str = "",
        email: str = "",
        status_sprawdzenia: str,
        uwagi: str,
        zrodlo: str,
        source_id: str,
        clean_clients: list[dict] | None = None,
        content_hash: str = "",
        items_text: str = "",
    ) -> bool:
        clean_clients = clean_clients or []
        inwestycja = extract_inwestycja_short(items_text, inwestycja)
        produkty, trunc_p = limit_field(sanitize_produkty_text(parsed.produkty_tekst), LIMIT_PRODUKTY)
        tytul, trunc_t = limit_field(tytul_sprawy, LIMIT_TYTUL)
        field_notes: list[str] = []
        if trunc_p or trunc_t:
            field_notes.append("skrocono_opis_zrodlowy")
        if not produkty and parsed.status_sprawdzenia == "ok":
            status_sprawdzenia = "wymaga_korekty"
        uwagi_final = "; ".join(filter(None, [uwagi, *field_notes]))
        fragment = normalize_text(items_text)[:500] if items_text else ""
        h = content_hash or candidate_hash(
            zrodlo, telefon, email, data, produkty, kwota, adres_dostawy, event_id,
        )
        if h in self._hashes:
            return False
        matches, match_sug = match_clean_clients(clean_clients, telefon, email, "", nazwa_klienta, "")
        status_bufora = "wymaga_korekty" if len(matches) > 1 else "do_akceptacji"
        powod_bufora = "konflikt_dopasowania_klienta" if len(matches) > 1 else "quick_order"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cid = self._next_id("BC")
        zid = self._next_id("BZ")

        self.klienci.append({
            "status_bufora": status_bufora,
            "powod_bufora": powod_bufora,
            "tytul_sprawy": tytul,
            "zrodlo": zrodlo,
            "data": data,
            "telefon": telefon,
            "email": email,
            "nazwa_klienta": nazwa_klienta,
            "adres": "", "nr_adresu": "", "nr_lokalu": "", "kod_pocztowy": "", "miasto": "", "nip": "",
            "produkty": produkty,
            "sugestia": match_sug,
            "uwagi": uwagi_final,
            "fragment_tresci": fragment,
            "source_id": source_id,
            "candidate_id": cid,
            "hash": h,
            "created_at": now,
        })
        self._hashes.add(h)

        zh = candidate_hash(zrodlo, telefon, email, data, produkty, kwota, adres_dostawy, f"qo-order|{h}")
        self.zamowienia.append({
            "status_bufora": status_bufora,
            "powod_bufora": powod_bufora,
            "data_zamowienia": data,
            "tytul_sprawy": tytul,
            "zrodlo": zrodlo,
            "telefon": telefon,
            "produkty": produkty,
            "ilosc_sztuk": parsed.ilosc_sztuk,
            "liczba_pozycji": parsed.liczba_pozycji,
            "inwestycja": inwestycja,
            "kwota": kwota,
            "dostawa": "",
            "adres_dostawy": adres_dostawy,
            "email": email,
            "nazwa_klienta": nazwa_klienta,
            "status_sprawdzenia": status_sprawdzenia,
            "sugestia": match_sug,
            "uwagi": uwagi_final,
            "zamowienie_candidate_id": zid,
            "klient_candidate_id": cid,
            "source_id": source_id,
            "hash": zh,
            "created_at": now,
        })
        self._hashes.add(zh)

        for it in parsed.items:
            produkt, nr_kat, opis, item_status, opis_trunc = clean_line_item_for_buffer(it)
            ph = candidate_hash(zrodlo, telefon, "", data, nr_kat or produkt, it.ilosc, "", opis)
            if ph in self._hashes:
                continue
            pid = self._next_id("BP")
            poz_uwagi = list(field_notes)
            if opis_trunc:
                poz_uwagi.append("skrocono_opis_zrodlowy")
            self.pozycje.append({
                "status_bufora": status_bufora,
                "powod_bufora": powod_bufora,
                "data_zamowienia": data,
                "tytul_sprawy": tytul,
                "zrodlo": zrodlo,
                "telefon": telefon,
                "ilosc": it.ilosc,
                "produkt": produkt,
                "wariant": it.wariant,
                "nr_katalogowy": nr_kat,
                "opis_pozycji": opis,
                "inwestycja": inwestycja,
                "status_sprawdzenia": item_status,
                "sugestia": match_sug,
                "uwagi": "; ".join(poz_uwagi),
                "pozycja_candidate_id": pid,
                "zamowienie_candidate_id": zid,
                "klient_candidate_id": cid,
                "source_id": source_id,
                "hash": ph,
                "created_at": now,
            })
            self._hashes.add(ph)
        return True

    def stats(self) -> dict:
        k_do = sum(1 for r in self.klienci if r.get("status_bufora") == "do_akceptacji")
        z_do = sum(1 for r in self.zamowienia if r.get("status_bufora") == "do_akceptacji")
        p_do = sum(1 for r in self.pozycje if r.get("status_bufora") == "do_akceptacji")
        korekta = sum(
            1 for r in self.klienci + self.zamowienia + self.pozycje
            if r.get("status_bufora") == "wymaga_korekty"
        )
        powody = Counter(
            r.get("powod_bufora") or r.get("powod", "")
            for r in self.klienci + self.zamowienia + self.unrelated
            if (r.get("powod_bufora") or r.get("powod"))
        )
        return {
            "klienci_do_akceptacji": k_do,
            "zamowienia_do_akceptacji": z_do,
            "pozycje_do_akceptacji": p_do,
            "wymaga_korekty": korekta,
            "powody": powody,
            "unrelated": len(self.unrelated),
            "user_merge_merged": self.user_merge_merged,
        }


def buffer_field_max_lengths(store: BufferStore) -> dict[str, int]:
    def _max(rows: list[dict], field: str) -> int:
        return max((len(r.get(field) or "") for r in rows), default=0)

    all_rows = store.klienci + store.zamowienia + store.pozycje
    return {
        "tytul_sprawy": _max(all_rows, "tytul_sprawy"),
        "produkty": max(_max(store.klienci + store.zamowienia, "produkty"), 0),
        "opis_pozycji": _max(store.pozycje, "opis_pozycji"),
    }


def buffer_title_has_noise(store: BufferStore) -> bool:
    noise = re.compile(
        r"Dane do przelewu|Nr rach|Numer rachunku|mBank|Blik|Tytu[łl]:|"
        r"Pozdrawiam|Z poważaniem|Wysłane z|Sent from|Odbiorca:|"
        r"Razem do zapłaty|Adres dostawy:|Faktura:|NIP:|"
        r"(?:Tel\.|Telefon|Mob\.)\s*\+?\d|IBAN|\d{26}",
        re.I,
    )
    for rows in (store.klienci, store.zamowienia, store.pozycje):
        for r in rows:
            if noise.search(r.get("tytul_sprawy") or ""):
                return True
    return False


def write_buffer_exports(out_private: Path, store: BufferStore) -> Path:
    bufor_dir = out_private / BUFOR_DIR_NAME
    bufor_dir.mkdir(parents=True, exist_ok=True)
    resanitize_buffer_store(store)
    merged_total = 0
    store.klienci, m = merge_rows_by_user_key(store.klienci, "klient")
    merged_total += m
    store.zamowienia, m = merge_rows_by_user_key(store.zamowienia, "zamowienie")
    merged_total += m
    store.pozycje, m = merge_rows_by_user_key(store.pozycje, "pozycja")
    merged_total += m
    store.user_merge_merged = merged_total
    csv_write(bufor_dir / "BUFOR-KLIENCI-DO-AKCEPTACJI.csv", BUFOR_KLIENCI_COLS, store.klienci)
    csv_write(bufor_dir / "BUFOR-ZAMOWIENIA-DO-AKCEPTACJI.csv", BUFOR_ZAMOWIENIA_COLS, store.zamowienia)
    csv_write(bufor_dir / "BUFOR-POZYCJE-DO-AKCEPTACJI.csv", BUFOR_POZYCJE_COLS, store.pozycje)
    csv_write(out_private / "KONTAKTY-Z-KOMUNIKACJI-NIEPOWIAZANE.csv", UNRELATED_COLS, store.unrelated)
    return bufor_dir


def write_buffer_notification(bufor_dir: Path, store: BufferStore) -> Path:
    st = store.stats()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    powody_lines = "\n".join(f"- {k}: {v}" for k, v in st["powody"].most_common(10))
    urgent_k = sorted(store.klienci, key=lambda r: r.get("data", ""), reverse=True)[:5]
    urgent_z = sorted(store.zamowienia, key=lambda r: r.get("data_zamowienia", ""), reverse=True)[:5]
    urgent_lines = []
    for r in urgent_k:
        urgent_lines.append(
            f"- [Klient] {r.get('data', '')} | {r.get('status_bufora', '')} | "
            f"{r.get('powod_bufora', '')} | produkty: {(r.get('produkty') or '—')[:40]}"
        )
    for r in urgent_z:
        urgent_lines.append(
            f"- [Zamówienie] {r.get('data_zamowienia', '')} | {r.get('status_bufora', '')} | "
            f"{r.get('powod_bufora', '')} | {(r.get('tytul_sprawy') or '')[:50]}"
        )

    path = bufor_dir / "BUFOR-POWIADOMIENIA.md"
    path.write_text(
        f"# Bufor akceptacji – powiadomienia\n\n"
        f"Wygenerowano: {now}\n\n"
        f"## Podsumowanie\n\n"
        f"| Metryka | Liczba |\n|---|---:|\n"
        f"| Nowi klienci w buforze (do akceptacji) | {st['klienci_do_akceptacji']} |\n"
        f"| Nowe zamówienia w buforze (do akceptacji) | {st['zamowienia_do_akceptacji']} |\n"
        f"| Nowe pozycje w buforze (do akceptacji) | {st['pozycje_do_akceptacji']} |\n"
        f"| Wymagają korekty | {st['wymaga_korekty']} |\n"
        f"| Kontakty niepowiązane (techniczne) | {st['unrelated']} |\n\n"
        f"## Typy problemów / powodów\n\n{powody_lines or '_Brak_'}\n\n"
        f"## Najpilniejsze rekordy (wg daty)\n\n"
        + ("\n".join(urgent_lines) if urgent_lines else "_Brak rekordów w buforze_\n")
        + "\n\n## Footing Panel\n\n"
        f"Rekordy wymagają akceptacji w **dwóch głównych miejscach pracy**:\n\n"
        f"1. **Klienci** – kandydaci i konflikty dopasowania\n"
        f"2. **Zamówienia** – kandydaci, pozycje i korekty parsera\n\n"
        f"Pliki buforowe w `{BUFOR_DIR_NAME}/` są warstwą techniczną – użytkownik nie skacze po wielu ekranach.\n",
        encoding="utf-8-sig",
    )
    return path


def merge_quick_order_files(out_private: Path, store: BufferStore, clean_clients: list[dict]) -> int:
    """Wczytaj QUICK-ORDER-EVENTS.csv do bufora (bez duplikatów hash)."""
    path = out_private / "quick-order" / "QUICK-ORDER-EVENTS.csv"
    if not path.exists():
        return 0
    added = 0
    seen_content: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        if not reader.fieldnames or "event_id" not in (reader.fieldnames or []):
            f.seek(0)
            reader = csv.DictReader(f)
        for row in reader:
            items_text = row.get("items_text") or row.get("produkty") or ""
            parse_window, _ = prepare_parse_window(items_text)
            parsed = parse_items_text(parse_window)
            content_h = (row.get("hash") or "").strip() or quick_order_content_hash(
                telefon=row.get("telefon", ""),
                data=row.get("data", ""),
                items_text=items_text,
                zrodlo=row.get("zrodlo", "quick_order"),
                inwestycja=row.get("inwestycja", ""),
                nazwa_klienta=row.get("nazwa_klienta", ""),
            )
            if content_h in seen_content:
                continue
            seen_content.add(content_h)
            if store.add_quick_order(
                event_id=row.get("event_id", ""),
                data=row.get("data", ""),
                telefon=row.get("telefon", ""),
                tytul_sprawy=row.get("tytul_sprawy", ""),
                parsed=parsed,
                inwestycja=row.get("inwestycja", ""),
                nazwa_klienta=row.get("nazwa_klienta", ""),
                email="",
                status_sprawdzenia=row.get("status_sprawdzenia", "ok"),
                uwagi=row.get("uwagi", ""),
                zrodlo=row.get("zrodlo", "quick_order"),
                source_id=row.get("event_id", ""),
                clean_clients=clean_clients,
                content_hash=content_h,
                items_text=items_text,
            ):
                added += 1
    return added
