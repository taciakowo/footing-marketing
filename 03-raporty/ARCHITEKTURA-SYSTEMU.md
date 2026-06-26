# Footing System – architektura

Lokalny system zarządzania małą firmą Footing. **Nie jest to pełny CRM/ERP** – skupiamy się na prostych, lokalnych narzędziach operacyjnych i marketingowych.

## Dwa piony biznesowe

| Pion | Folder | Odpowiedzialność |
|------|--------|------------------|
| **Sprzedaż / operacje** | `05-sprzedaz/` | WooCommerce, arkusze, magazyn, zamówienia, stany, synchronizacja |
| **Marketing / popyt** | `06-marketing/` | SEO, Brevo, kampanie, segmenty, treści, social, landingi |

Integracje zewnętrzne (`07-integracje/`) **nie zawierają logiki biznesowej** – tylko pobieranie/wysyłanie danych. Decyzje należą do pionu sprzedaż lub marketing.

## Warstwy systemu

```
00-inbox/           ← dane wejściowe (SMS, e-mail, cache Google Contacts) – NIE w Git
01-system/          ← skrypty lokalne (parser, sync kontaktów, IMAP)
02-output-private/  ← CSV z danymi klientów – NIE w Git
03-raporty/         ← raporty ogólne bez PII (Git OK)
04-produkty/        ← wiedza o produktach Footing
05-sprzedaz/        ← pion operacyjny (przyszły Woo ↔ Sheets)
06-marketing/       ← pion marketingowy
07-integracje/      ← adaptery API (Google, Woo, Brevo, kanały)
08-legacy-audit/    ← audyt starego synchronizatora (bez importu kodu)
```

## Co działa dziś (01-system)

| Skrypt | Rola |
|--------|------|
| `update_footing_database.py` | Analiza kontaktów, SMS, e-mail → CSV + raporty |
| `sync_google_contacts.py` | Pobieranie kontaktów z Google People API |
| `fetch_emails_imap.py` | Opcjonalny cache e-maili (IMAP) |
| `vcf_surowe_linie.py` | Diagnostyka surowych linii VCF |

**Źródło kontaktów:** `00-inbox/contacts_cache.csv` (Google), fallback: `contacts.vcf`.

## Foldery przejściowe (do migracji treści)

| Stary folder | Docelowy pion |
|--------------|---------------|
| `05-kampanie/` | `06-marketing/kampanie/` |
| `06-landingi/` | `06-marketing/landingi/` |

Treść nie została jeszcze przeniesiona – tylko przygotowano nową strukturę.

## Stary synchronizator WooCommerce ↔ Google Sheets

Istnieje jako **osobny, niedokończony projekt** (Google Apps Script + Node + WooCommerce).  
Materiał audytowy: `08-legacy-audit/`. **Nie wklejać kodu 1:1** do Footing System.

## Zasady na ten etap

1. Nie rozbudowywać parserów klientów/SMS/e-mail bez osobnego zlecenia.
2. Nie łączyć starego synchronizatora z `01-system` przed audytem.
3. Nowe funkcje sprzedażowe → `05-sprzedaz`; marketingowe → `06-marketing`.
4. Sekrety tylko lokalnie (`00-inbox/`, `.env`, `config.json`).

## Następny krok

Przeprowadzić audyt modułów starego synchronizatora według `08-legacy-audit/AUDYT-PLAN.md` i wybrać **jeden mały moduł** do przepisania (np. read-only log produktów).
