# Footing System

Lokalny system operacyjny małej firmy Footing: sprzedaż, klienci, zamówienia, komunikacja, SEO, kampanie, produkcja.

> **Repozytorium GitHub:** nadal `footing-marketing` (bez zmiany nazwy remote).  
> **Docelowa nazwa projektu:** `footing-system` (folder lokalny: `C:\dev\footing-system` po migracji).

## Architektura (dwa piony)

Footing System to lokalny system operacyjny małej firmy – **nie pełny CRM/ERP**.

| Pion | Folder |
|------|--------|
| Sprzedaż / operacje | `05-sprzedaz/` |
| Marketing / popyt | `06-marketing/` |
| Integracje (adaptery API) | `07-integracje/` |
| Audyt starego sync Woo↔Sheets | `08-legacy-audit/` |

Pełny opis: `03-raporty/ARCHITEKTURA-SYSTEMU.md`.

## Szybki start

1. Wrzuć pliki do `00-inbox/`:
   - `sms.xml` – eksport SMS z telefonu
   - `email_cache.csv` – opcjonalnie e-maile (lub pobierz przez IMAP)

2. Skopiuj konfigurację:
   ```powershell
   copy 01-system\config.example.json 01-system\config.json
   ```

3. **Kontakty – Google Contacts (główne źródło):**
   ```powershell
   pip install -r 01-system\requirements.txt
   python 01-system\sync_google_contacts.py
   python 01-system\update_footing_database.py
   ```

4. Opcjonalnie – pobierz e-maile (IMAP):
   ```powershell
   python 01-system\fetch_emails_imap.py
   python 01-system\update_footing_database.py
   ```

## Google Contacts – konfiguracja OAuth

### 1. Utwórz credentials w Google Cloud Console

1. Wejdź na [Google Cloud Console](https://console.cloud.google.com/).
2. Utwórz projekt (lub wybierz istniejący).
3. Włącz **Google People API** (*APIs & Services → Library → People API → Enable*).
4. Przejdź do *APIs & Services → Credentials → Create Credentials → OAuth client ID*.
5. Typ aplikacji: **Desktop app**.
6. Pobierz plik JSON credentials.

### 2. Zapisz credentials lokalnie

Skopiuj pobrany plik JSON jako:

```
00-inbox/google_credentials.json
```

Plik **nie trafia do Git** (jest w `.gitignore`).

### 3. Synchronizacja kontaktów

```powershell
python 01-system\sync_google_contacts.py
```

- Przy **pierwszym uruchomieniu** otworzy się przeglądarka – zaloguj się na konto Google z kontaktami.
- Token zapisze się w `00-inbox/google_token.json` (też poza Git).
- Wynik trafi do `00-inbox/contacts_cache.csv`.

Skrypt **tylko odczytuje** kontakty – nic nie modyfikuje w Google.

### 4. Aktualizacja bazy

```powershell
python 01-system\update_footing_database.py
```

Skrypt czyta kontakty z `contacts_cache.csv`. Jeśli cache nie istnieje, użyje awaryjnie `contacts.vcf`.

Źródło kontaktów widać w `03-raporty/PODSUMOWANIE.md`:
- `google_contacts_cache` – główne źródło
- `contacts_vcf_fallback` – awaryjne VCF

## Struktura

```
footing-system/
├── 00-inbox/              ← pliki wejściowe (NIE w Git)
│   ├── contacts_cache.csv       ← Google Contacts (auto)
│   ├── google_credentials.json  ← OAuth (ręcznie)
│   ├── google_token.json        ← token (auto)
│   ├── sms.xml
│   └── email_cache.csv
├── 01-system/             ← skrypty Python
├── 02-output-private/     ← CSV z danymi klientów (NIE w Git)
├── 03-raporty/            ← raporty .md bez danych osobowych (Git OK)
├── 04-produkty/
├── 05-sprzedaz/           ← pion operacyjny (Woo, magazyn – w przygotowaniu)
├── 06-marketing/          ← pion marketingowy
├── 07-integracje/         ← adaptery API
├── 08-legacy-audit/       ← audyt starego synchronizatora
├── 05-kampanie/           ← legacy (migracja → 06-marketing)
├── 06-landingi/           ← legacy (migracja → 06-marketing)
└── README.md
```

## Zasady danych

| Źródło | Rola |
|--------|------|
| **Google Contacts (cache)** | Główne: nazwa kontaktu → data, produkty, ilości, zastosowanie |
| **contacts.vcf** | Awaryjne, gdy brak cache Google |
| **SMS / e-mail** | Pomocnicze: adres, kwota, e-mail – **bez nadpisywania** kontaktu |
| **+48********* | Numer firmowy – wykluczony z klientów i zamówień |

### Przykład nazwy kontaktu

```
2026.06.23 Klient 3*Z26-M20 3xK98/6 Pergola
```

→ jedno zamówienie, dwie pozycje, zastosowanie Pergola.

## Pliki wyjściowe (prywatne)

`02-output-private/`:

- `KLIENCI.csv`, `ZAMOWIENIA.csv`, `POZYCJE-ZAMOWIEN.csv`
- `KOMUNIKACJA.csv`, `DO-SPRAWDZENIA.csv`
- `EMAIL-KONTAKTY.csv`, `SEO-FRAZY.csv`, `SEGMENTY-KLIENTOW.csv`

## Raporty publiczne

`03-raporty/` – tylko agregaty, **bez telefonów, e-maili, adresów i treści wiadomości**.

## Slack (opcjonalnie)

W `01-system/config.json` ustaw `slack_webhook_url` i `slack_notify_on_update: true`.

## Prywatność / Git

`.gitignore` blokuje m.in.: `00-inbox/`, `02-output-private/`, `google_credentials.json`, `google_token.json`, `contacts_cache.csv`, `*.csv`, `config.json`.

Do repozytorium trafiają wyłącznie: skrypty, dokumentacja `.md`, szablony kampanii.

## Migracja z `footing-marketing`

Stare foldery (`06-raporty/`, `10-sms/`, `00-projekt/`) zostały zastąpione strukturą powyżej.  
Kontakty migruj do Google Contacts lub trzymaj `contacts.vcf` jako fallback.
