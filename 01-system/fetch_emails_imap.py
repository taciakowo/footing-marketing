#!/usr/bin/env python3
"""Pobiera e-maile przez IMAP i dopisuje do 00-inbox/email_cache.csv."""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "00-inbox"
CONFIG = ROOT / "01-system" / "config.json"
CONFIG_EXAMPLE = ROOT / "01-system" / "config.example.json"
CACHE = INBOX / "email_cache.csv"

CACHE_COLS = ["email", "data", "temat", "tresc", "kierunek", "telefon", "typ"]

IMAP_CREDENTIALS_MSG = (
    "Brak FOOTING_EMAIL lub FOOTING_EMAIL_PASSWORD. "
    "Ustaw je w zmiennych środowiskowych Windows."
)


def get_imap_credentials(*, required: bool = True) -> tuple[str, str] | None:
    user = os.environ.get("FOOTING_EMAIL", "").strip()
    password = os.environ.get("FOOTING_EMAIL_PASSWORD", "").strip()
    if not user or not password:
        if required:
            print(IMAP_CREDENTIALS_MSG)
        return None
    return user, password


def load_config() -> dict:
    path = CONFIG if CONFIG.exists() else CONFIG_EXAMPLE
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def decode_mime(value: str) -> str:
    parts = []
    for chunk, enc in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return " ".join(parts)


def fetch_imap(cfg: dict, *, required_credentials: bool = True) -> list[dict] | None:
    creds = get_imap_credentials(required=required_credentials)
    if creds is None:
        return None

    user, password = creds
    host = cfg.get("imap_host", "").strip()
    if not host:
        print("Brak imap_host w config.json")
        return None

    try:
        import imaplib
    except ImportError:
        print("Brak modułu imaplib")
        return None

    port = int(cfg.get("imap_port", 993))
    folder = cfg.get("mailbox", "INBOX")
    days = int(cfg.get("days_back", 30))
    since = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

    rows: list[dict] = []
    mail = imaplib.IMAP4_SSL(host, port)
    mail.login(user, password)
    mail.select(folder)
    _, data = mail.search(None, f'(SINCE "{since}")')
    ids = data[0].split()
    for num in ids[-200:]:
        _, msg_data = mail.fetch(num, "(RFC822)")
        msg = message_from_bytes(msg_data[0][1])
        subject = decode_mime(msg.get("Subject", ""))
        from_addr = decode_mime(msg.get("From", ""))
        email = from_addr
        if "<" in from_addr:
            email = from_addr.split("<")[-1].rstrip(">")
        date_hdr = msg.get("Date", "")
        try:
            dt = parsedate_to_datetime(date_hdr)
            date_str = dt.strftime("%Y-%m-%d")
        except (TypeError, ValueError, IndexError):
            date_str = ""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="replace")
        rows.append({
            "email": email.strip(),
            "data": date_str,
            "temat": subject[:200],
            "tresc": body[:5000],
            "kierunek": "przychodząca",
            "telefon": "",
            "typ": "email",
        })
    mail.logout()
    return rows


def merge_cache(new_rows: list[dict]) -> int:
    INBOX.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    seen: set[str] = set()
    if CACHE.exists():
        with CACHE.open(encoding="utf-8-sig") as f:
            existing = list(csv.DictReader(f))
            for r in existing:
                seen.add(f"{r.get('email','')}|{r.get('data','')}|{r.get('temat','')[:40]}")
    added = 0
    for r in new_rows:
        key = f"{r['email']}|{r['data']}|{r['temat'][:40]}"
        if key not in seen:
            seen.add(key)
            existing.append(r)
            added += 1
    with CACHE.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CACHE_COLS, lineterminator="\n")
        w.writeheader()
        w.writerows({c: row.get(c, "") for c in CACHE_COLS} for row in existing)
    return added


def refresh_email_cache_if_configured(cfg: dict) -> int:
    """Odświeża cache e-maili, gdy ustawiono zmienne środowiskowe i imap_host."""
    if not cfg.get("imap_host", "").strip():
        return 0
    if not os.environ.get("FOOTING_EMAIL", "").strip() or not os.environ.get("FOOTING_EMAIL_PASSWORD", "").strip():
        return 0
    rows = fetch_imap(cfg, required_credentials=False)
    if not rows:
        return 0
    return merge_cache(rows)


def main() -> int:
    cfg = load_config()
    rows = fetch_imap(cfg, required_credentials=True)
    if rows is None:
        return 1
    if not rows:
        print("Brak nowych e-maili z IMAP")
        return 0
    added = merge_cache(rows)
    print(f"Zapisano {added} nowych e-maili do {CACHE}")
    print("Uruchom: python 01-system/update_footing_database.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
