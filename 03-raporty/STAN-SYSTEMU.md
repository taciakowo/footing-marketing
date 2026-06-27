# Footing System – stan projektu

Wygenerowano: 2026-06-26

Dokument zbiorczy do kontynuacji pracy bez utraty kontekstu. **Bez danych osobowych.**

---

# 1. Cel Footing System

Footing System to lokalny system operacyjny małej firmy Footing – **nie pełny CRM/ERP**. Służy do zarządzania codzienną pracą firmy w jednym miejscu na komputerze lokalnym.

Obszary systemu:

| Obszar | Opis |
|--------|------|
| **Sprzedaż** | Zamówienia, klienci, pozycje produktowe, widok CRM |
| **Klienci** | Baza z Google Contacts, SMS, e-mail |
| **Zamówienia** | Parsowanie z nazw kontaktów (data + Klient + produkt Footing) |
| **Komunikacja** | SMS XML, cache e-mail / IMAP |
| **Marketing** | Segmenty, SEO, eksport do Brevo |
| **CEIDG** | Osobna baza potencjalnych klientów B2B (planowana) |
| **Brevo** | Eksport kontaktów własnych do pierwszej kampanii |
| **Wysyłki** | Model danych logistycznych, przygotowanie pod aPaczka |
| **Integracje (przyszłe)** | WooCommerce, Google Sheets, aPaczka API, Allegro, OLX |

---

# 2. Aktualna struktura folderów

| Folder | Rola | Git |
|--------|------|-----|
| `00-inbox/` | Dane wejściowe: SMS, e-mail, Google OAuth, cache kontaktów | **Prywatny – ignorowany** |
| `01-system/` | Skrypty Python (parser, sync, eksport) | Śledzony |
| `02-output-private/` | CSV z klientami, wysyłkami, Brevo | **Prywatny – ignorowany** |
| `03-raporty/` | Raporty zbiorcze bez PII | Śledzony |
| `04-produkty/` | Wiedza o produktach Footing | Śledzony |
| `05-sprzedaz/` | Pion operacyjny: zamówienia, wysyłki, magazyn (doc.), Woo sync (doc.) | Śledzony |
| `06-marketing/` | Pion marketingowy: kampanie, segmenty, SEO, Brevo (doc.) | Śledzony |
| `07-integracje/` | Adaptery API – dokumentacja integracji | Śledzony |
| `08-legacy-audit/` | Audyt starego synchronizatora Woo ↔ Sheets | Śledzony |

**Foldery prywatne (nigdy w Git):** `00-inbox/`, `02-output-private/` oraz pliki wzorcowe danych (`*.csv`, `*.xml`, `*.vcf`, `config.json`, credentials Google).

**Foldery przejściowe (legacy, treść do migracji):** `05-kampanie/`, `06-landingi/` → docelowo `06-marketing/`.

---

# 3. Aktywne skrypty (`01-system/`)

| Skrypt | Rola |
|--------|------|
| `sync_google_contacts.py` | Pobiera kontakty z Google People API; filtr: **Klient + pełna data + kod produktu Footing** → `contacts_cache.csv` |
| `update_footing_database.py` | Główny pipeline: kontakty + SMS + e-mail → CRM, segmenty, Brevo, wysyłki, raporty |
| `fetch_emails_imap.py` | Opcjonalny pobór e-maili przez IMAP do `email_cache.csv` |
| `footing_import_rules.py` | Wspólne reguły: filtr Google, kody produktów, e-maile wewnętrzne |
| `shipping_export.py` | Generowanie `WYSYLKI.csv`, `PACZKI.csv`, `APACZKA-IMPORT-001.csv` (bez API) |
| `vcf_surowe_linie.py` | Diagnostyka surowych linii VCF (debug kodowania) |
| `requirements.txt` | Zależności Python (google-api, pandas, auth) |
| `config.example.json` | Szablon konfiguracji IMAP (kopia → `config.json`, poza Git) |

**Typowy przebieg:**

```powershell
python 01-system\sync_google_contacts.py
python 01-system\update_footing_database.py
```

Opcjonalnie przed update:

```powershell
python 01-system\fetch_emails_imap.py
```

---

# 4. Źródła danych

## Aktualne (wdrożone)

| Źródło | Plik / mechanizm | Status |
|--------|------------------|--------|
| **Google Contacts** | `00-inbox/contacts_cache.csv` via OAuth | Działa; filtr ścisły |
| **SMS** | `00-inbox/sms.xml` | Działa |
| **E-mail / IMAP** | `00-inbox/email_cache.csv` | Działa (cache + opcjonalny fetch) |
| **VCF fallback** | `00-inbox/contacts.vcf` | Tylko gdy brak cache Google |

## Planowane (dokumentacja / audyt, bez pełnej implementacji)

| Źródło | Docelowe użycie |
|--------|-----------------|
| **CEIDG CSV** | Osobna baza B2B → `BREVO-CEIDG-001.csv` |
| **WooCommerce** | Zamówienia sklepowe (audyt w `08-legacy-audit/`) |
| **Google Sheets** | Operacje / arkusze (legacy sync – nie przenosić 1:1) |
| **Brevo API** | Import list z CSV (obecnie tylko eksport plików) |
| **aPaczka API** | Nadawanie przesyłek (obecnie tylko `APACZKA-IMPORT-001.csv`) |
| **Allegro / OLX** | Segmentacja i leady (dokumentacja w `07-integracje/`) |

---

# 5. Pliki prywatne generowane przez system

Wszystkie w `02-output-private/` – **bez PII w tym dokumencie**.

| Plik | Zastosowanie |
|------|--------------|
| `KLIENCI.csv` | Baza klientów (CRM) – sortowanie po dacie, produkt, segment |
| `ZAMOWIENIA.csv` | Jedno zamówienie = jeden wiersz |
| `ZAMOWIENIA-WIDOK.csv` | Widok CRM – zamówienie z pozycjami w jednej kolumnie |
| `POZYCJE-ZAMOWIEN.csv` | Pozycje produktowe (tabela techniczna) |
| `KOMUNIKACJA.csv` | SMS + e-mail powiązane z klientami |
| `EMAIL-KONTAKTY.csv` | Kontakty zidentyfikowane po e-mailu |
| `SEGMENTY-KLIENTOW.csv` | Segmentacja operacyjna |
| `SEO-FRAZY.csv` | Frazy z komunikacji (SEO) |
| `DO-SPRAWDZENIA.csv` | Błędy jakości danych CRM |
| `WYSYLKI.csv` | Logiczne wysyłki (1 wiersz = 1 wysyłka) |
| `PACZKI.csv` | Fizyczne paczki / palety |
| `WYSYLKI-DO-SPRAWDZENIA.csv` | Wysyłki z brakami adresu, wagi, kategorii |
| `APACZKA-IMPORT-001.csv` | Tylko wysyłki `gotowe_do_nadania` (bez API) |
| `KLUCZ-WYSYLKOWY.csv` | Klucz wagowo-objętościowy (uzupełniany lokalnie) |
| `marketing/BREVO-KONTAKTY-001.csv` | Eksport do Brevo – klienci własni |
| `marketing/BREVO-DO-SPRAWDZENIA.csv` | Kontakty wymagające weryfikacji przed mailingiem |
| `kontrola/GOOGLE-CONTACTS-POMINIETE.csv` | Diagnostyka odrzuconych kontaktów Google |
| `DIAGNOSTYKA-VCF.csv` | Diagnostyka VCF (gdy użyty fallback) |

**Obecność plików (sprawdzenie lokalne):** kluczowe pliki inbox i output istnieją na dysku roboczym.

---

# 6. Raporty publiczne (bez danych osobowych)

| Raport | Zawartość |
|--------|-----------|
| `PODSUMOWANIE.md` | Liczby: klienci, zamówienia, pozycje, komunikacja; ranking produktów |
| `SPRZEDAZ.md` | Agregaty sprzedażowe |
| `SEO.md` | Frazy z komunikacji |
| `KAMPANIE.md` | Status kampanii |
| `PRODUKCJA.md` | Szacunkowe ilości produktów do produkcji |
| `WYSYLKI.md` | Statystyki wysyłek, kategorie, brakujące pola |
| `MAILING-001.md` | Eksport Brevo – liczby, segmenty, jakość danych |
| `ARCHITEKTURA-SYSTEMU.md` | Architektura warstw i pionów |
| `STAN-SYSTEMU.md` | Ten dokument |
| `DZIENNY-RAPORT.md` | Krótki raport sesji |
| `SCHEMAT-DANYCH.md` | Tabela przepływu danych |

---

# 7. Aktualny stan Google Contacts

- **OAuth:** skonfigurowany lokalnie (`google_credentials.json`, `google_token.json` – poza Git).
- **People API:** musi być włączone w Google Cloud Console dla projektu OAuth.
- **Filtr importu:** do cache trafiają wyłącznie kontakty spełniające **jednocześnie**:
  1. słowo `Klient` w nazwie,
  2. pełna data (`YYYY.MM.DD` itd.),
  3. kod produktu Footing (Z25, Z26, K1, H2, W400 itd. – nie same słowa „pergola”, „kotwy”).
- **Wynik filtra (ostatnia synchronizacja):** z ~2198 kontaktów Google zaakceptowano ~171; reszta → `GOOGLE-CONTACTS-POMINIETE.csv`.
- **`contacts_cache.csv`:** prywatny, w `00-inbox/`.
- **`contacts.vcf`:** tylko fallback, gdy brak cache.

---

# 8. Aktualny stan CRM

| Plik | Rola |
|------|------|
| `KLIENCI.csv` | Główna baza klientów (~250 rekordów w ostatniej sesji) |
| `ZAMOWIENIA.csv` | Zamówienia (~171) |
| `POZYCJE-ZAMOWIEN.csv` | Pozycje produktów (~207) |
| `ZAMOWIENIA-WIDOK.csv` | Widok „jeden wiersz = jedno zamówienie” z `pozycje_tekst` |
| `DO-SPRAWDZENIA.csv` | Lista problemów jakości (~0 po ścisłym filtrze Google) |

**Źródło kontaktów w ostatniej sesji:** `google_contacts_cache`.

Parser rozpoznaje kody produktów z i bez myślnika (`Z25K130C`, `3xZ26-M20`, `K2K300` itd.). Brak ilości → status `do_sprawdzenia_brak_ilosci`.

---

# 9. Aktualny stan mailingu

- **Brevo:** konfiguracja opisana w dokumentacji (`05-kampanie/BREVO-KONFIGURACJA.md`, `06-marketing/brevo/`); system generuje pliki CSV do importu – **bez automatycznego wysyłania API**.
- **`BREVO-KONTAKTY-001.csv`:** tylko kontakty własni / klienci / kontrahenci z systemu Footing.
- **CEIDG:** osobna baza – **nie mieszać** z Google/SMS/e-mail.
- **`BREVO-CEIDG-001.csv`:** planowany osobny eksport (nie wdrożony).
- **Wykluczenia:** e-maile wewnętrzne (domeny/fragmenty: footing, taciak, taciakowo).

**Ostatnie liczby (MAILING-001.md):**

| Metryka | Liczba |
|---------|--------|
| Kontakty ogółem | 250 |
| Z e-mailem | 41 |
| Zakwalifikowane do Brevo | 4 |
| Do sprawdzenia | 3 |
| E-maile wewnętrzne wykluczone | 4 |

Główny problem jakości: **brak e-maili** u większości klientów w Google Contacts.

---

# 10. Aktualny stan wysyłek

Moduł: `shipping_export.py` + `05-sprzedaz/wysylki/`, integracja: `07-integracje/apaczka/`.

| Plik | Stan |
|------|------|
| `WYSYLKI.csv` | ~171 wysyłek (1:1 z zamówieniami) |
| `PACZKI.csv` | ~171 paczek (szkic – często 1 paczka na wysyłkę) |
| `WYSYLKI-DO-SPRAWDZENIA.csv` | Wysyłki z brakami (obecnie większość – brak klucza wagowego) |
| `APACZKA-IMPORT-001.csv` | **0** gotowych (wymaga uzupełnienia `KLUCZ-WYSYLKOWY.csv` i adresów) |
| `KLUCZ-WYSYLKOWY.csv` | Szkic (Z17, Z25, Z26, K1, K2, H1, H2, W400, W2001, W2002) – gabaryty puste |

**aPaczka API:** zaplanowane 6 etapów w README; **nie wdrażane** – zero wysyłek do API.

**Ostatnie liczby (WYSYLKI.md):** 0 gotowych do nadania; 171 do sprawdzenia; główne braki: waga, gabaryty, kod pocztowy.

---

# 11. Aktualny stan CEIDG

- CEIDG = **osobne źródło** potencjalnych klientów B2B (`zrodlo = ceidg`).
- **Nie mieszać** z kontaktami Google / SMS / e-mail / CRM transakcyjnym.
- Docelowy eksport: `02-output-private/marketing/BREVO-CEIDG-001.csv`.
- Obecny eksport `BREVO-KONTAKTY-001.csv` dotyczy wyłącznie bazy własnej.
- Dokumentacja: `06-marketing/segmenty/README.md` (sekcja CEIDG).
- **Status:** plan i zasady – **brak importera CEIDG w kodzie**.

**Najbliższy cel CEIDG:** import CSV → czyszczenie → segmentacja B2B → eksport Brevo → osobna kampania (nie łączyć z bazą klientów).

---

# 12. Co jest gotowe

- Struktura folderów Footing System (inbox, system, output, raporty, piony 05–08).
- `.gitignore` blokujący dane prywatne.
- Sync Google Contacts z OAuth i ścisłym filtrem zamówień Footing.
- Parser CRM: klienci, zamówienia, pozycje, komunikacja, segmenty, SEO.
- Widok CRM: `ZAMOWIENIA-WIDOK.csv`.
- Eksport Brevo: `BREVO-KONTAKTY-001.csv`, `BREVO-DO-SPRAWDZENIA.csv`, raport `MAILING-001.md`.
- Filtrowanie e-maili wewnętrznych.
- Moduł wysyłek: model danych, klucz wysyłkowy, raport `WYSYLKI.md`.
- Plik przygotowawczy aPaczka (bez API).
- Audyt legacy Woo ↔ Sheets (`08-legacy-audit/`).
- Dokumentacja integracji (Google, Brevo, aPaczka, Woo, kanały).

---

# 13. Co jest rozpoczęte, ale nieukończone

- **Mailing Brevo:** tylko 4 kontakty zakwalifikowane – niski pokrycie e-mailami.
- **CEIDG:** zasady bez implementacji importu i eksportu.
- **KLUCZ-WYSYLKOWY.csv:** szkic bez realnych gabarytów → 0 wysyłek gotowych do nadania.
- **Adresy dostawy:** większość wysyłek bez pełnego adresu z SMS/e-mail.
- **WooCommerce / Google Sheets:** audyt bez nowego synchronizatora.
- **aPaczka API:** plan 6 etapów, brak kodu API.
- **Allegro / OLX / social:** tylko README w `07-integracje/`.
- **Magazyn:** tylko dokumentacja w `05-sprzedaz/magazyn/`.
- **Migracja treści:** `05-kampanie/`, `06-landingi/` → `06-marketing/`.
- **Zmiany w Git:** wiele plików lokalnie zmodyfikowanych / nieśledzonych (patrz git status poniżej).

---

# 14. Najbliższy priorytet

**Priorytet najbliższy:**

**CEIDG → czyszczenie bazy → segmenty B2B → eksport Brevo → pierwsza kampania informacyjno-promocyjna.**

Równolegle (operacyjnie, bez blokowania CEIDG):

- Uzupełnianie e-maili klientów w Google Contacts (poprawa `BREVO-KONTAKTY-001.csv`).
- Uzupełnianie `KLUCZ-WYSYLKOWY.csv` i adresów „Dostawa do:” w SMS (poprawa wysyłek).

---

# 15. Ryzyka

1. **Dane prywatne nie mogą trafić do Git** – inbox, output, CSV, credentials, config lokalny.
2. **CEIDG nie mieszać z klientami** transakcyjnymi – osobne pliki, osobna kampania, osobna zgoda.
3. **Mailing wymaga ostrożności prawnej** – RODO, opt-in, segmentacja, test na małej grupie.
4. **Nie wysyłać wszystkiego naraz** – najpierw mała kampania testowa (np. segment kotwy: 4 kontakty).
5. **Nie mieszać obsługi sprzedaży z kampaniami zewnętrznymi** – CRM transakcyjny ≠ baza CEIDG.
6. **Nie wdrażać jeszcze pełnej automatyzacji aPaczka** – najpierw klucz wysyłkowy i ręczny import CSV.
7. **Nie przenosić starego synchronizatora WooCommerce 1:1** – tylko audyt i małe moduły read-only.
8. **People API** – bez włączenia API sync Google nie zadziała.

---

# Metryki z ostatniej sesji (2026-06-26)

| Obszar | Metryka | Wartość |
|--------|---------|---------|
| CRM | Klienci | 250 |
| CRM | Zamówienia | 171 |
| CRM | Pozycje | 207 |
| CRM | Komunikacja | 670 |
| Google | Zaakceptowane kontakty (cache) | ~171 |
| Mailing | Zakwalifikowane do Brevo | 4 |
| Wysyłki | Gotowe do nadania | 0 |
| Wysyłki | Do sprawdzenia | 171 |

Szczegóły: `PODSUMOWANIE.md`, `MAILING-001.md`, `WYSYLKI.md`.
