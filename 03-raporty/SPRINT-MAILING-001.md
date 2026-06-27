# FOOTING MAILING SPRINT 001

Status: **aktywny**
Tryb: wąski sprint – tylko CEIDG i pierwszy mailing B2B.

---

# Cel sprintu

Pierwszy mailing informacyjno-promocyjny do firm z CEIDG.

---

# Zakres aktywny

Tylko **CEIDG**, **segmentacja** i **eksport Brevo**.

| Obszar | Pliki / skrypt |
|--------|----------------|
| Import i czyszczenie | `01-system/prepare_ceidg_mailing.py` |
| Wejście | `02-output-private/ceidg/input/` |
| Wynik roboczy | `02-output-private/ceidg/output/CEIDG-CZYSTE.csv` |
| Kontrola jakości | `02-output-private/ceidg/kontrola/CEIDG-DO-SPRAWDZENIA.csv` |
| Eksport Brevo | `02-output-private/marketing/BREVO-CEIDG-001.csv` |
| Raport | `03-raporty/CEIDG-MAILING-001.md` |
| Dokumentacja | `06-marketing/segmenty/README.md`, `06-marketing/brevo/README.md` |

**Nie mieszać** z bazą klientów własnych (`BREVO-KONTAKTY-001.csv`).

---

# Zakres zamrożony

Moduły pozostają w strukturze repozytorium, ale **nie rozwijamy** ich w tym sprincie:

- wysyłki (`shipping_export.py`, `WYSYLKI.csv`, aPaczka)
- aPaczka (API i import)
- WooCommerce
- Google Sheets
- magazyn
- social media
- audyt legacy (`08-legacy-audit/`)
- Google Contacts klientów własnych (`sync_google_contacts.py`)
- CRM klientów własnych (`update_footing_database.py`, `KLIENCI.csv`, `ZAMOWIENIA.csv` itd.)

---

# Minimalny wynik sprintu

- [ ] `CEIDG-CZYSTE.csv` – oczyszczona baza robocza
- [ ] `BREVO-CEIDG-001.csv` – lista priorytet A/B do importu
- [ ] `CEIDG-DO-SPRAWDZENIA.csv` – rekordy wymagające ręcznej decyzji
- [ ] `CEIDG-MAILING-001.md` – raport zbiorczy (bez PII)
- [ ] Gotowa lista do **ręcznego importu** w panelu Brevo (bez API w tym sprincie)

---

# Zakaz rozbudowy

- Nie dodawać nowych modułów ani folderów bez wyraźnego polecenia.
- Nie uruchamiać ani nie rozszerzać zamrożonych pipeline’ów.
- Nie łączyć CEIDG z Google Contacts, SMS, e-mail ani CRM własnym.
- Nie wysyłać maili ani nie podłączać Brevo API w kodzie – tylko plik CSV.

---

# Najbliższy krok

1. Wrzuć plik(i) CEIDG (`.csv`) do:

   `02-output-private/ceidg/input/`

2. Uruchom:

   ```powershell
   python 01-system\prepare_ceidg_mailing.py
   ```

3. Sprawdź raport `03-raporty/CEIDG-MAILING-001.md` i plik `BREVO-CEIDG-001.csv`.

4. Zaimportuj `BREVO-CEIDG-001.csv` ręcznie w Brevo – **test na małej partii** (segment A).

---

# Powiązane dokumenty

- `03-raporty/STAN-SYSTEMU.md` – pełny obraz systemu (referencja)
- `03-raporty/CEIDG-MAILING-001.md` – wynik ostatniego uruchomienia skryptu
