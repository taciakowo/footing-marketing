# Footing Panel – szkic modelu danych (SQLite)

**Status:** dokument projektowy. **Pełna migracja nie jest wdrożona.**

CSV pozostają eksportami i raportami. Docelowa baza operacyjna: **SQLite** (lokalnie, obok `02-output-private/`).

## UI: dwa miejsca pracy

Panel operacyjny: **Klienci** | **Zamówienia**. Bufor, DO-SPRAWDZENIA i kontakty niepowiązane są warstwą danych, nie osobnymi głównymi ekranami.

## Tabele bufora (kandydaci)

### client_candidates

Odpowiednik `BUFOR-KLIENCI-DO-AKCEPTACJI.csv`.

| Kolumna | Opis |
|---------|------|
| candidate_id | Np. BC-000001 |
| status_bufora | do_akceptacji, wymaga_korekty, odrzucone, zaakceptowane |
| powod_bufora | kandydat_z_komunikacji, quick_order, konflikt_dopasowania_klienta |
| tytul_sprawy | Bez prefiksów BUFOR/NOWY |
| zrodlo, source_id | SMS, email, quick_order + message_id / event_id |
| hash | Dedup kandydata |
| sugerowane_klient_id | Po dopasowaniu (nie nadpisuje danych czystych) |

### order_candidates / item_candidates

Odpowiednik `BUFOR-ZAMOWIENIA-*` i `BUFOR-POZYCJE-*`. Powiązanie `klient_candidate_id`, `zamowienie_candidate_id`.

### acceptance_events (przyszłość)

Zdarzenie `accepted_candidate`: kto, kiedy, co przeniesiono, nowy vs istniejący klient.

## Tabele
### customers

Klient Footing – źródło prawdy.

| Kolumna | Opis |
|---------|------|
| id | PK |
| klient_id | Np. K-603595693 |
| nazwa_klienta | Nazwa operacyjna (wpis użytkownika / quick order) |
| segment | Segment marketingowy / operacyjny |
| status | aktywny, archiwum, … |
| uwagi | Pole użytkowe |
| created_at, updated_at | Techniczne |

### phones

| Kolumna | Opis |
|---------|------|
| id | PK |
| customer_id | FK → customers |
| telefon | E.164, unikalny |
| glowny | 0/1 |
| zrodlo | google_contacts_read, quick_order, reczny |

### events

Zdarzenia operacyjne (quick order, notatka, połączenie).

| Kolumna | Opis |
|---------|------|
| id | PK |
| event_id | Np. QO-20260627… |
| customer_id | FK (opcjonalnie przed match) |
| telefon | |
| data | Data zdarzenia |
| tytul_sprawy | Tytuł sprawy Footing (nie nazwa Google) |
| items_text | Surowy tekst pozycji |
| inwestycja | Opcjonalnie |
| zrodlo | quick_order, reczny, import |
| status | do_akceptacji, zaakceptowane, odrzucone |
| status_sprawdzenia | ok, brak_ilosci, produkt_spoza_slownika, … |
| uwagi | |
| raw_json | Opcjonalny payload |
| created_at | |

### orders

| Kolumna | Opis |
|---------|------|
| id | PK |
| order_id | Np. O-00123 |
| customer_id | FK |
| data_zamowienia | |
| tytul_sprawy | |
| zastosowanie | |
| segment | |
| status_sprawdzenia | |
| uwagi | |
| zrodlo_glowne | google_contacts_read, quick_order, panel |
| created_at, updated_at | |

### order_items

| Kolumna | Opis |
|---------|------|
| id | PK |
| order_item_id | |
| order_id | FK |
| produkt | Kod bazowy |
| wariant | |
| nr_katalogowy | |
| ilosc | NULL dozwolone – bez domyślnej 1 |
| status_sprawdzenia | ok, do_sprawdzenia_brak_ilosci, produkt_spoza_slownika |
| uwagi | |
| zrodlo | |

### products

Słownik produktów Footing (sync z `04-produkty/`).

| Kolumna | Opis |
|---------|------|
| id | PK |
| kod | Z25-K130 |
| nazwa | Opis marketingowy |
| aktywny | 0/1 |
| uwagi | |

### shipments

Moduł wysyłek – rezerwacja pod przyszły panel.

| Kolumna | Opis |
|---------|------|
| id | PK |
| order_id | FK |
| status | |
| adres, telefon, email | |
| uwagi | |

### contact_snapshots

**Odczyt** z Google Contacts – bez write-back.

| Kolumna | Opis |
|---------|------|
| id | PK |
| contact_id | resourceName Google |
| telefon | |
| nazwa_kontaktu_google | **Tylko odczyt** – snapshot |
| email | |
| synced_at | |

## Zasady

1. `nazwa_kontaktu_google` nigdy nie jest aktualizowana przez panel ani quick order.
2. `tytul_sprawy` należy do Footing System.
3. Brak ilości → `status_sprawdzenia = do_sprawdzenia_brak_ilosci`, nie `ilosc = 1`.
4. Produkt spoza słownika → `produkt_spoza_slownika`, wymaga akceptacji w panelu.
5. Pole `uwagi` w UI i eksportach **przed** polami technicznymi (id, hash, source_id).
6. Dane z bufora **nie nadpisują** danych czystych automatycznie.
7. **Produkty / magazyn / Woo sync** – przyszły etap, poza bieżącym MVP panelu.

## Mapowanie CSV → SQLite (przyszłość)

| CSV (przejściowy) | Tabela |
|-------------------|--------|
| KLIENCI.csv | customers + phones (czyste) |
| ZAMOWIENIA.csv | orders (czyste) |
| POZYCJE-ZAMOWIEN.csv | order_items (czyste) |
| bufor/BUFOR-KLIENCI-*.csv | client_candidates |
| bufor/BUFOR-ZAMOWIENIA-*.csv | order_candidates |
| bufor/BUFOR-POZYCJE-*.csv | item_candidates |
| QUICK-ORDER-EVENTS.csv | events (surowe) |
| KONTAKTY-Z-KOMUNIKACJI-NIEPOWIAZANE.csv | unrelated_comm_log |
| contacts_cache.csv | contact_snapshots |