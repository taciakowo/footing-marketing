# Struktura plików Footing System

Wygenerowano: audyt architektury (2026-07-01, korekta statusu Sheets).  
Repozytorium: `https://github.com/taciakowo/footing-system.git` · gałąź: `main`.

Projekt wyrósł z wcześniejszego `footing-marketing`; obecna nazwa repo i folderu lokalnego to **`footing-system`**.

---

## Status Google Sheets Product Master

Moduł: `01-system/product_sheet_sync.py` · zakładka `baza_produktow_footing`.

| Warstwa | Status |
|---------|--------|
| Google Sheets API | Włączone, działa (read-only) |
| `--snapshot-only` | OK — 142 produkty, 112 kolumn |
| `--inspect-validations` | OK — 852 walidacji / list rozwijanych |
| `--export-woo` | OK — `PRODUKTY-WOO-EXPORT.csv` |
| `--inspect-formulas` | **Do dopracowania** — obecnie 0 wykrytych formuł |

Snapshoty prywatne: separator CSV **`;`** (`Import-Csv ... -Delimiter ';'`).

## Prywatne foldery (poza Git)

| Folder | Status Git | Pliki (szac.) | Kategorie |
|--------|------------|---------------|-----------|
| `00-inbox/` | `.gitignore` | 9 | OAuth JSON, cache kontaktów, SMS XML, VCF, CSV wejściowe, arkusze robocze |
| `02-output-private/` | `.gitignore` | 62 | CRM, bufor, wysyłki, marketing CEIDG/Brevo, produkty, quick-order, archiwum |

**Kontrola:** `git ls-files | Select-String "00-inbox|02-output-private"` → brak wyników (OK).

`00-inbox/` podfoldery: `input/`, `_odstawione/`.  
`02-output-private/` podfoldery: `bufor/`, `marketing/`, `produkty/`, `quick-order/`, `ceidg/`, `kontrola/`, `archiwum-stare/`, `_archiwum/`.

---

## Drzewo publiczne (skrót)

```
footing-system/
├── README.md
├── .gitignore
├── 01-system/              ← 13 modułów Python + requirements + config.example.json
├── 03-raporty/             ← 16 raportów .md (publiczne agregaty)
├── 04-produkty/            ← wiedza produktowa + Google Sheet Product Master
├── 05-sprzedaz/            ← pion operacyjny (README + podfoldery planowane)
├── 05-kampanie/            ← legacy (3 pliki .md)
├── 06-marketing/           ← pion marketingowy (7 plików)
├── 06-landingi/            ← legacy (landing + PDF)
├── 07-integracje/          ← 18 adapterów README
├── 08-legacy-audit/        ← audyt starego synchronizatora (7 plików)
├── 09-quick-order/         ← spec + przykład JSON
└── 10-footing-panel/       ← szkic panelu (3 pliki .md)
```

**Pliki śledzone przez Git:** 84 (stan audytu).

---

## 01-system/ – moduły Python

| Plik | Typ | CLI |
|------|-----|-----|
| `update_footing_database.py` | orchestrator CRM | tak |
| `sync_google_contacts.py` | integracja Google Contacts | tak |
| `fetch_emails_imap.py` | integracja IMAP | tak |
| `prepare_ceidg_mailing.py` | marketing CEIDG/Brevo | tak |
| `product_sheet_sync.py` | produkty Google Sheet | tak |
| `quick_order_events.py` | Quick Order → bufor | tak |
| `vcf_surowe_linie.py` | diagnostyka VCF | tak |
| `footing_buffer.py` | biblioteka bufora | nie |
| `shipping_export.py` | biblioteka wysyłek | nie |
| `footing_order_core.py` | biblioteka parsowania pozycji | nie |
| `footing_import_rules.py` | biblioteka reguł importu | nie |
| `footing_csv.py` | biblioteka zapisu CSV | nie |
| `requirements.txt` | zależności pip | — |
| `config.example.json` | szablon konfiguracji | — |

**Kompilacja:** wszystkie moduły `.py` przechodzą `python -m py_compile` (stan audytu).

---

## 03-raporty/ – raporty publiczne

| Plik | Temat |
|------|-------|
| `ARCHITEKTURA-SYSTEMU.md` | architektura (poprzednia wersja) |
| `ARCHITEKTURA-AKTUALNA-FOOTING-SYSTEM.md` | **audyt aktualny (ten cykl)** |
| `STRUKTURA-PLIKOW-FOOTING-SYSTEM.md` | **ten dokument** |
| `SCHEMAT-DANYCH.md` | schemat danych CRM |
| `STAN-SYSTEMU.md` | stan systemu |
| `PODSUMOWANIE.md` | agregaty operacyjne |
| `PRODUKCJA.md` | ranking produktów |
| `SPRZEDAZ.md`, `WYSYLKI.md` | sprzedaż / wysyłki |
| `CEIDG-MAILING-001.md` | statystyki CEIDG (bez PII) |
| `SPRINT-MAILING-001.md`, `MAILING-001.md`, `KAMPANIE.md`, `WYNIKI-KAMPANII.md` | mailing |
| `SEO.md`, `DZIENNY-RAPORT.md` | SEO / dzienny |
| `KONTEKST-DLA-NOWEGO-CHATU.md`, `KONTROLA-CRM-KONTAKTY.md` | kontekst / kontrola |

---

## 04-produkty/ – dokumentacja produktowa

| Plik | Zawartość |
|------|-----------|
| `README.md` | indeks, źródło prawdy = Google Sheet |
| `PRODUKTY.md` | opis asortymentu Footing |
| `GOOGLE-SHEET-PRODUCT-MASTER.md` | Product Master, sync, audyt, Woo export |

Google Sheet: ID `1YtWrOgyJgNXFYaSg5-TeApJOOP3R25b9b62TT7lZqXE`, zakładka `baza_produktow_footing`.

---

## 07-integracje/ – adaptery (dokumentacja)

`google/`, `google-contacts-write/`, `woocommerce/`, `brevo/`, `apaczka/`, `analytics/`, `search-console/`, `merchant-center/`, kanały social (`facebook-instagram/`, `x/`, `linkedin/`, `tiktok/`, `youtube/`, `pinterest/`), marketplace (`allegro/`, `etsy/`, `olx/`), `slack/`.

Większość to **plan / zakres** – kod produkcyjny adapterów w `07-integracje/` jeszcze minimalny. Działające skrypty integracji są w `01-system/`.

---

## Foldery legacy / przejściowe

| Folder | Status |
|--------|--------|
| `05-kampanie/` | treść do migracji → `06-marketing/kampanie/` |
| `06-landingi/` | treść do migracji → `06-marketing/landingi/` |
| `02-output-private/_archiwum/` | stary `06-raporty/`, `10-sms/` (prywatne) |
| `08-legacy-audit/` | monolit Woo↔Sheets Apps Script – tylko audyt |

---

## Zasada prywatności raportów

Publiczne `.md` w `03-raporty/` i `04-produkty/` **nie zawierają** telefonów, e-maili klientów, adresów, NIP-ów, treści SMS/e-mail, rekordów CEIDG/Brevo ani zawartości prywatnych CSV.
