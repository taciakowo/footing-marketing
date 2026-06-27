# Kontrola CRM i kontaktów

Raport operacyjny – bez danych osobowych w Git (szczegóły w `02-output-private/`).

## Źródło prawdy

| System | Rola |
|--------|------|
| **Footing System** | Klienci, zdarzenia, zamówienia, pozycje, historia, statusy |
| **Google Contacts** | Odczyt numerów, odczyt istniejących nazw, identyfikacja, import historyczny |

## Google Contacts read-only

- **Nie modyfikujemy** nazw kontaktów Google
- Nie tworzymy plików `GOOGLE-CONTACTS-ZMIANY`, nie wywołujemy `updateContact`
- `nazwa_kontaktu_google` to pole **tylko do odczytu** (snapshot z cache)
- `tytul_sprawy` należy do Footing System – tytuł sprawy operacyjnej, nie nazwa w telefonie
- Historia zamówień jest w Footing System, nie w Google Contacts
- Quick Order tworzy **zdarzenie** i wpis **do akceptacji**, bez zapisu do Google
- **Footing Panel** (planowany) będzie służył do realnej obsługi – nie Cursor ani ręczne CSV

Szczegóły polityki zapisu: `07-integracje/google-contacts-write/README.md`

## Pola klienta

| Pole | Znaczenie |
|------|-----------|
| nazwa_kontaktu_google | Odczyt z Google / historyczna nazwa w telefonie (read-only) |
| nazwa_klienta | Realna nazwa klienta (SMS, e-mail, wysyłka, meta Google) – **nie** kopia nazwy kontaktu |
| tytul_sprawy | Tytuł sprawy / zamówienia w Footing (format: data + Klient + produkty + inwestycja + skrót) |

Nie używamy: `proponowana_nowa_nazwa_google`, `nazwa_autentyczna`, `customer_name_raw` w CSV (w JSON quick order `customer_name_raw` jest OK).

## Format CSV

| Reguła | Wartość |
|--------|---------|
| Separator | średnik `;` |
| Encoding | UTF-8 BOM (`utf-8-sig`) |
| Nagłówki | bez polskich znaków (`wartosc_zamowien`, `ilosc_produktow`, `ilosc_sztuk`) |

## Kolejność kolumn użytkowych

Pliki CRM zaczynają od pól dla człowieka, techniczne ID i hash na końcu:

- **KLIENCI.csv** – `nazwa_kontaktu_google`, daty, telefon, e-mail, `nazwa_klienta`, adres…
- **ZAMOWIENIA.csv** – `data_zamowienia`, `tytul_sprawy`, `nazwa_kontaktu_google`…
- **POZYCJE-ZAMOWIEN.csv** – data, kontakt, ilość, produkt…
- **ZAMOWIENIA-WIDOK.csv** – widok operacyjny bez ID technicznych
- **DO-SPRAWDZENIA.csv** – `typ_problemu`, data, tytuł, kontakt, fragment produktu…
- **QUICK-ORDER-DO-AKCEPTACJI.csv** – data, tytuł, telefon, produkty, status `do_akceptacji`

## Bufor akceptacji i dwa miejsca pracy

### Trzy poziomy danych

| Poziom | Rola |
|--------|------|
| **Surowe** | Google cache, SMS, e-mail, Quick Order JSON – materiał wejściowy |
| **Bufor** | Kandydaci w `02-output-private/bufor/BUFOR-*.csv` – `status_bufora = do_akceptacji` |
| **Czyste** | `KLIENCI.csv`, `ZAMOWIENIA.csv`, `POZYCJE-ZAMOWIEN.csv` – zaakceptowane / historycznie uznane |

### Routing komunikacji

| Sygnał | Gdzie trafia |
|--------|--------------|
| SMS/e-mail z produktem, ilością, NIP, wysyłką, wyceną | Bufor klienta (+ bufor zamówienia/pozycji gdy jest produkt) |
| Sam ślad bez sensu handlowego (newsletter, no-reply, nazwa.pl) | `KONTAKTY-Z-KOMUNIKACJI-NIEPOWIAZANE.csv` |
| Google Contacts: data + „Klient” | `KLIENCI.csv` (auto, historyczne) |
| Quick Order | Bufor + `QUICK-ORDER-EVENTS.csv` (nie Google, nie od razu czyste) |

### Footing Panel – dwa obszary

1. **Klienci** – zaakceptowani + kandydaci + konflikty dopasowania
2. **Zamówienia** – zaakceptowane + kandydaci + pozycje jako szczegóły

Pliki buforowe istnieją technicznie; użytkownik **nie** skacze po osobnych głównych ekranach bufora / DO-SPRAWDZENIA / niepowiązanych.

### Statusy, nie prefiksy w tytule

- `tytul_sprawy` **bez** `BUFOR`, `NOWY`, `NOWY BUFOR`
- Status bufora: `status_bufora`, `powod_bufora`, `status_sprawdzenia`
- Powiadomienia: `02-output-private/bufor/BUFOR-POWIADOMIENIA.md`

### Bezpieczeństwo danych

- Hash kandydata – brak duplikatów
- Dopasowanie do istniejącego klienta – sugestia, nie auto-nadpisanie
- Konflikt wielu matchy → `wymaga_korekty`
- Przyszła akceptacja: zdarzenie `accepted_candidate` (dokumentacja w `10-footing-panel/`)

## DO-SPRAWDZENIA.csv

Plik **nie jest buforem wszystkich nowych klientów**. Zawiera problemy danych już w torze handlowym:
| typ_problemu | Opis |
|--------------|------|
| brak_rozpoznanego_produktu | Kontakt z datą i „Klient”, ale bez produktu |
| do_sprawdzenia_brak_ilosci | Produkt bez ilości (nie zakładamy `1`) |
| produkt_spoza_slownika | Np. przęsła, kotwy spoza katalogu |
| data_i_ilosc_bez_kodu_produktu | Ilość w tekście bez rozpoznanego kodu |
| klient_wieloma_datami | Wiele dat w jednej nazwie kontaktu |
| konflikt_danych_buforowych | Różne dane w buforze vs zaakceptowanym kliencie |

Problem nowego kandydata może być jednocześnie w buforze i tutaj jako ostrzeżenie parsera.
## Quick Order

- Wejście: JSON (`09-quick-order/examples/`)
- Skrypt: `01-system/quick_order_events.py`
- Wyjście: `02-output-private/quick-order/`
- Status domyślny: `do_akceptacji`
- Brak zapisu do Google Contacts

## Walidacja produktów

| Sytuacja | status_sprawdzenia |
|----------|-------------------|
| Brak ilości przy znanym produkcie | do_sprawdzenia_brak_ilosci |
| Tekst spoza słownika (np. przęsła, KOT-S140) | produkt_spoza_slownika |
| Brak domyślnej ilości 1 | – (zawsze) |

Parser nie tworzy fałszywych pozycji z fragmentów kodu (np. K210 z K1-K210).

## CSV a codzienna praca

CSV w `02-output-private/` to **eksporty i raporty**.

Codzienna edycja zamówień **nie** odbywa się przez ręczne edytowanie CSV – docelowo Footing Panel + SQLite (`10-footing-panel/DATA-MODEL-DRAFT.md`).

## Cursor

Cursor służy **wyłącznie do programowania**. Nie jest narzędziem operacyjnym.
