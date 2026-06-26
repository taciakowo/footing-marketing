#!/usr/bin/env python3
"""Pobiera kontakty z Google Contacts (People API) – tylko odczyt."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "00-inbox"
CREDENTIALS_PATH = INBOX / "google_credentials.json"
TOKEN_PATH = INBOX / "google_token.json"
OUTPUT_PATH = INBOX / "contacts_cache.csv"

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
]


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


def sync_contacts() -> Path:
    INBOX.mkdir(parents=True, exist_ok=True)
    creds = get_credentials()
    service = build("people", "v1", credentials=creds, cache_discovery=False)
    people = fetch_all_connections(service)

    rows: list[dict[str, str]] = []
    for person in people:
        base, extra_phones = parse_person(person)
        rows.extend(person_to_rows(base, extra_phones))

    df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    return OUTPUT_PATH


def main() -> int:
    print("=== Footing System – sync_google_contacts ===")
    path = sync_contacts()
    count = len(pd.read_csv(path, encoding="utf-8-sig"))
    print(f"Zapisano {count} wierszy kontaktów -> {path}")
    print("Uruchom: python 01-system/update_footing_database.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
