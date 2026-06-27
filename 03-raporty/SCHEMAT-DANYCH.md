# Footing System – schemat danych

Wygenerowano: 2026-06-26

Przepływ danych od źródeł do plików wynikowych. **Bez danych osobowych.**

| Źródło | Skrypt / moduł | Plik wynikowy | Prywatny / publiczny | Zastosowanie |
| ------ | -------------- | ------------- | -------------------- | ------------ |
| **Google Contacts** | `sync_google_contacts.py` | `00-inbox/contacts_cache.csv` | Prywatny | Główne źródło kontaktów-zamówień (filtr: Klient + data + produkt) |
| **Google Contacts** | `sync_google_contacts.py` | `02-output-private/kontrola/GOOGLE-CONTACTS-POMINIETE.csv` | Prywatny | Diagnostyka odrzuconych kontaktów |
| **Google Contacts** | `update_footing_database.py` | `02-output-private/KLIENCI.csv`, `ZAMOWIENIA.csv`, `POZYCJE-ZAMOWIEN.csv`, `ZAMOWIENIA-WIDOK.csv` | Prywatny | CRM – klienci i zamówienia |
| **Google Contacts** | `update_footing_database.py` | `03-raporty/PODSUMOWANIE.md` | Publiczny | Statystyki zbiorcze bez PII |
| **SMS XML** | `update_footing_database.py` | `02-output-private/KOMUNIKACJA.csv` | Prywatny | Historia SMS powiązana z klientami |
| **SMS XML** | `update_footing_database.py` | `02-output-private/KLIENCI.csv` (e-mail, daty) | Prywatny | Uzupełnienie danych klienta z SMS |
| **SMS XML** | `shipping_export.py` | `02-output-private/WYSYLKI.csv` | Prywatny | Adresy „Dostawa do:” z SMS |
| **IMAP / e-mail** | `fetch_emails_imap.py` | `00-inbox/email_cache.csv` | Prywatny | Cache wiadomości e-mail |
| **IMAP / e-mail** | `update_footing_database.py` | `02-output-private/KOMUNIKACJA.csv`, `EMAIL-KONTAKTY.csv` | Prywatny | Komunikacja i kontakty po e-mailu |
| **IMAP / e-mail** | `update_footing_database.py` | `02-output-private/marketing/BREVO-KONTAKTY-001.csv` | Prywatny | E-mail klienta do eksportu Brevo |
| **VCF fallback** | `update_footing_database.py` | `02-output-private/DIAGNOSTYKA-VCF.csv` | Prywatny | Tylko gdy brak `contacts_cache.csv` |
| **VCF fallback** | `update_footing_database.py` | Te same pliki CRM co Google | Prywatny | Awaryjne źródło kontaktów |
| **CEIDG** | *(planowany importer)* | `02-output-private/marketing/BREVO-CEIDG-001.csv` | Prywatny | Osobna baza B2B – **nie wdrożone** |
| **CEIDG** | *(planowany)* | `03-raporty/` (raport segmentów B2B) | Publiczny | Statystyki bez PII – **plan** |
| **WooCommerce** | *(audyt `08-legacy-audit/`)* | *(brak)* | — | Docelowo zamówienia sklepowe – **nie wdrożone** |
| **Google Sheets** | *(legacy sync – audyt)* | *(brak)* | — | Docelowo operacje / stany – **nie wdrożone** |
| **Brevo** | `update_footing_database.py` (`build_brevo_exports`) | `02-output-private/marketing/BREVO-KONTAKTY-001.csv` | Prywatny | Eksport CSV do importu w panelu Brevo |
| **Brevo** | `update_footing_database.py` | `02-output-private/marketing/BREVO-DO-SPRAWDZENIA.csv` | Prywatny | Kontakty do ręcznej weryfikacji |
| **Brevo** | `update_footing_database.py` | `03-raporty/MAILING-001.md` | Publiczny | Raport kampanii – liczby, segmenty |
| **aPaczka** | `shipping_export.py` | `02-output-private/APACZKA-IMPORT-001.csv` | Prywatny | Przygotowanie przesyłek (bez API) |
| **aPaczka** | `shipping_export.py` | `02-output-private/WYSYLKI.csv`, `PACZKI.csv` | Prywatny | Model wysyłek i paczek |
| **aPaczka** | `shipping_export.py` | `02-output-private/WYSYLKI-DO-SPRAWDZENIA.csv` | Prywatny | Wysyłki z brakami danych |
| **aPaczka** | `shipping_export.py` | `02-output-private/KLUCZ-WYSYLKOWY.csv` | Prywatny | Klucz wagowo-objętościowy (ręcznie) |
| **aPaczka** | `shipping_export.py` | `03-raporty/WYSYLKI.md` | Publiczny | Raport wysyłek – bez PII |
| **aPaczka API** | *(plan `07-integracje/apaczka/`)* | *(brak)* | — | Nadawanie, etykiety, tracking – **nie wdrożone** |

## Diagram przepływu (uproszczony)

```
00-inbox/                    01-system/                      02-output-private/
┌─────────────────┐         ┌──────────────────────┐         ┌─────────────────────┐
│ contacts_cache  │────────▶│ sync_google_contacts │         │ KLIENCI.csv         │
│ sms.xml         │────────▶│ update_footing_      │────────▶│ ZAMOWIENIA.csv      │
│ email_cache     │────────▶│   database.py        │         │ KOMUNIKACJA.csv     │
│ contacts.vcf    │  (fb)   │ shipping_export.py   │────────▶│ WYSYLKI.csv         │
└─────────────────┘         └──────────────────────┘         │ marketing/BREVO-*.csv│
                                        │                      └─────────────────────┘
                                        ▼
                               03-raporty/ (bez PII)
                               PODSUMOWANIE, WYSYLKI,
                               MAILING-001, STAN-SYSTEMU
```

## Moduły pomocnicze

| Moduł | Rola w schemacie |
|-------|------------------|
| `footing_import_rules.py` | Filtr Google, kody produktów, e-maile wewnętrzne |
| `shipping_export.py` | Wysyłki, paczki, APACZKA-IMPORT, KLUCZ-WYSYLKOWY |

## Legenda

- **Prywatny** – folder `00-inbox/` lub `02-output-private/`, ignorowany przez Git.
- **Publiczny** – `03-raporty/` – wyłącznie agregaty, bez telefonów, e-maili, adresów.
