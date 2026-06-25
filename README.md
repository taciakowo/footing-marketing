# Footing System

Lokalny system operacyjny małej firmy Footing: sprzedaż, klienci, zamówienia, komunikacja, SEO, kampanie, produkcja.

> **Repozytorium GitHub:** nadal `footing-marketing` (bez zmiany nazwy remote).  
> **Docelowa nazwa projektu:** `footing-system` (folder lokalny: `C:\dev\footing-system` po migracji).

## Szybki start

1. Wrzuć pliki do `00-inbox/`:
   - `sms.xml` – eksport SMS z telefonu
   - `contacts.vcf` – kontakty (nazwa = główne źródło zamówienia)
   - `email_cache.csv` – opcjonalnie e-maile (lub pobierz przez IMAP)

2. Skopiuj konfigurację:
   ```powershell
   copy 01-system\config.example.json 01-system\config.json
   ```

3. Uruchom aktualizację bazy:
   ```powershell
   python 01-system\update_footing_database.py
   ```

4. Opcjonalnie – pobierz e-maile (IMAP):
   ```powershell
   python 01-system\fetch_emails_imap.py
   python 01-system\update_footing_database.py
   ```

## Struktura

```
footing-system/
├── 00-inbox/              ← ręczne pliki wejściowe (NIE w Git)
├── 01-system/             ← skrypty Python
├── 02-output-private/     ← CSV z danymi klientów (NIE w Git)
├── 03-raporty/            ← raporty .md bez danych osobowych (Git OK)
├── 04-produkty/
├── 05-kampanie/
├── 06-landingi/
└── README.md
```

## Zasady danych

| Źródło | Rola |
|--------|------|
| **Nazwa kontaktu (VCF)** | Główne: data, produkty, ilości, zastosowanie |
| **SMS / e-mail** | Pomocnicze: adres, kwota, e-mail, pytania – **bez nadpisywania** kontaktu |
| **+48888338495** | Numer firmowy – wykluczony z klientów i zamówień |

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

`.gitignore` blokuje: `00-inbox/`, `02-output-private/`, `*.csv`, `*.xml`, `*.vcf`, `config.json`.

Do repozytorium trafiają wyłącznie: skrypty, dokumentacja `.md`, szablony kampanii.

## Migracja z `footing-marketing`

Stare foldery (`06-raporty/`, `10-sms/`, `00-projekt/`) zostały zastąpione strukturą powyżej.  
Dane wejściowe przenieś ręcznie do `00-inbox/`.
