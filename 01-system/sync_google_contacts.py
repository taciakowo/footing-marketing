#!/usr/bin/env python3
"""Pobiera kontakty z Google Contacts (People API) – wyłącznie odczyt.

Footing System nie modyfikuje nazw kontaktów Google. Brak updateContact / write-back.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

sys.path.insert(0, str(Path(__file__).resolve().parent))
from footing_import_rules import IMPORT_ACCEPTED, evaluate_google_contact  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "00-inbox"
OUT_PRIVATE = ROOT / "02-output-private"
KONTROLA_DIR = OUT_PRIVATE / "kontrola"
CREDENTIALS_PATH = INBOX / "google_credentials.json"
TOKEN_PATH = INBOX / "google_token.json"
OUTPUT_PATH = INBOX / "contacts_cache.csv"
POMINIETE_PATH = KONTROLA_DIR / "GOOGLE-CONTACTS-POMINIETE.csv"

SCOPES = ["https://www.googleapis.com/auth/contacts.readonly"]
PERSON_FIELDS = "names,emailAddresses,phoneNumbers,organizations,biographies"
OUTPUT_COLUMNS = [
    "contact_id",
    "nazwa_kontaktu",
    "imie",
    "nazwisko",
    "firma",
    "telefon",
    "email",
    "notatka",
    "zrodlo",
    "import_reason",
]
POMINIETE_COLUMNS = ["nazwa_kontaktu", "telefon", "email", "powod_pominiecia", "sugestia"]


def get_credentials() -> Credentials:
    if not CREDENTIALS_PATH.exists():
        print(f"Brak pliku: {CREDENTIALS_PATH}")
        print("Utwórz OAuth credentials w Google Cloud Console i zapisz jako google_credentials.json.")
        sys.exit(1)

    creds: Credentials | None = None
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


def _first(items: list[dict], key: str, default: str = "") -> str:
    if not items:
        return default
    return (items[0].get(key) or default).strip()


def parse_person(person: dict) -> tuple[dict[str, str], list[str]]:
    names = person.get("names") or []
    display = _first(names, "displayName")
    given = _first(names, "givenName")
    family = _first(names, "familyName")
    if not display:
        display = " ".join(p for p in (given, family) if p).strip()

    orgs = person.get("organizations") or []
    firma = _first(orgs, "name")

    bios = person.get("biographies") or []
    notatka = _first(bios, "value")

    phones = [p.get("value", "").strip() for p in (person.get("phoneNumbers") or []) if p.get("value")]
    emails = [e.get("value", "").strip() for e in (person.get("emailAddresses") or []) if e.get("value")]

    base = {
        "contact_id": person.get("resourceName", ""),
        "nazwa_kontaktu": display,
        "imie": given,
        "nazwisko": family,
        "firma": firma,
        "telefon": phones[0] if phones else "",
        "email": emails[0] if emails else "",
        "notatka": notatka,
        "zrodlo": "google_contacts",
    }
    return base, phones[1:]


def fetch_all_connections(service) -> list[dict]:
    connections: list[dict] = []
    page_token: str | None = None
    while True:
        request = service.people().connections().list(
            resourceName="people/me",
            pageSize=1000,
            personFields=PERSON_FIELDS,
            pageToken=page_token,
        )
        response = request.execute()
        connections.extend(response.get("connections") or [])
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return connections


def person_to_rows(base: dict[str, str], extra_phones: list[str]) -> list[dict[str, str]]:
    rows = [base]
    for phone in extra_phones:
        row = dict(base)
        row["telefon"] = phone
        rows.append(row)
    return rows


def sync_contacts() -> tuple[Path, Path, dict[str, int]]:
    INBOX.mkdir(parents=True, exist_ok=True)
    KONTROLA_DIR.mkdir(parents=True, exist_ok=True)
    creds = get_credentials()
    service = build("people", "v1", credentials=creds, cache_discovery=False)
    people = fetch_all_connections(service)

    rows: list[dict[str, str]] = []
    pominiete: list[dict[str, str]] = []
    saved_ids: set[str] = set()
    skip_reasons: Counter = Counter()

    for person in people:
        base, extra_phones = parse_person(person)
        accepted, reason, sugestia = evaluate_google_contact(base["nazwa_kontaktu"])
        if not accepted:
            skip_reasons[reason] += 1
            pominiete.append({
                "nazwa_kontaktu": base["nazwa_kontaktu"],
                "telefon": base["telefon"],
                "email": base["email"],
                "powod_pominiecia": reason,
                "sugestia": sugestia,
            })
            continue
        saved_ids.add(base["contact_id"])
        base["import_reason"] = IMPORT_ACCEPTED
        rows.extend(person_to_rows(base, extra_phones))

    pd.DataFrame(rows, columns=OUTPUT_COLUMNS).to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    pd.DataFrame(pominiete, columns=POMINIETE_COLUMNS).to_csv(
        POMINIETE_PATH, index=False, encoding="utf-8-sig",
    )
    stats = {
        "fetched": len(people),
        "saved": len(saved_ids),
        "skipped": len(people) - len(saved_ids),
        "skipped_missing_date": skip_reasons.get("excluded_missing_date", 0),
        "skipped_missing_product": skip_reasons.get("excluded_missing_product", 0),
        "rows": len(rows),
    }
    return OUTPUT_PATH, POMINIETE_PATH, stats


def main() -> int:
    print("=== Footing System – sync_google_contacts ===")
    print("Tryb: read-only – brak zapisu do Google Contacts")
    path, pominiete_path, stats = sync_contacts()
    print(f"Pobrano z Google:              {stats['fetched']} kontaktów")
    print(f"Zaakceptowano (zapis cache):   {stats['saved']} kontaktów ({stats['rows']} wierszy)")
    print(f"Pominięto:                     {stats['skipped']} kontaktów")
    print(f"Pominięto – brak daty:         {stats['skipped_missing_date']} kontaktów")
    print(f"Pominięto – brak produktu:     {stats['skipped_missing_product']} kontaktów")
    print(f"Cache:                         {path}")
    print(f"Diagnostyka pominiętych:       {pominiete_path}")
    print("Uruchom: python 01-system/update_footing_database.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
