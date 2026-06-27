# Footing Panel – zakres (szkic)

## Cel

Umożliwić obsługę Footing bez:

- Cursora
- ręcznej edycji CSV
- uruchamiania skryptów z terminala
- dopisywania produktów w kodzie Python

## Dwa główne miejsca pracy

Panel ma **dwa obszary operacyjne** – użytkownik nie skacze po wielu buforach ani osobnych kolejkach:

### 1. Klienci

W jednym miejscu:

- klienci **zaakceptowani** (dane czyste),
- **kandydaci do akceptacji** z bufora (`BUFOR-KLIENCI-DO-AKCEPTACJI.csv`),
- konflikty dopasowania (`status_bufora = wymaga_korekty`),
- dane kontaktowe i adresowe,
- historia komunikacji klienta,
- ostrzeżenia z `DO-SPRAWDZENIA.csv` widoczne przy rekordzie.

Pola read-only: `nazwa_kontaktu_google` (snapshot Google).

Pole operacyjne: `nazwa_klienta`, adres, NIP, uwagi.

### 2. Zamówienia

W jednym miejscu:

- zamówienia **zaakceptowane** (dane czyste),
- **kandydaci do akceptacji** z bufora (`BUFOR-ZAMOWIENIA-DO-AKCEPTACJI.csv`),
- **pozycje do akceptacji** jako szczegóły zamówienia (nie osobna główna zakładka),
- korekta ilości – **bez domyślnego ustawiania 1**,
- produkty spoza słownika (`produkt_spoza_slownika`),
- statusy zamówień i `status_sprawdzenia`,
- Quick Order widoczny tutaj (nie jako osobny główny dział),
- wysyłki – gdy moduł aPaczki wróci do użycia.

`tytul_sprawy` należy do Footing – **bez prefiksów BUFOR/NOWY** w tytule; status bufora w polach `status_bufora`, `powod_bufora`.

## Trzy poziomy danych (technicznie)

| Poziom | Opis | Przykłady plików |
|--------|------|------------------|
| **Surowe** | Wejście z źródeł | Google cache, SMS, e-mail, Quick Order JSON |
| **Bufor** | Kandydaci do akceptacji | `02-output-private/bufor/BUFOR-*.csv` |
| **Czyste** | Zaakceptowane / historyczne | `KLIENCI.csv`, `ZAMOWIENIA.csv`, `POZYCJE-ZAMOWIEN.csv` |

Pliki buforowe istnieją technicznie; **UI nie rozbija pracy** na osobne główne ekrany dla każdego bufora.

## Kontakty niepowiązane

`KONTAKTY-Z-KOMUNIKACJI-NIEPOWIAZANE.csv` – raport techniczny (newsletter, no-reply, brak sygnału handlowego). **Nie** jest główną kolejką pracy.

## Akceptacja (przyszły etap)

Zdarzenie `accepted_candidate` (kto, kiedy, co przeniesiono, powiązanie z klientem). Na tym etapie: pola w buforze + dokumentacja – bez pełnej obsługi w UI.

## Użytkownik

Właściciel / operator Footing – szybka praca po rozmowie, SMS lub imporcie.

## Poza zakresem panelu (na start)

| Element | Powód |
|---------|--------|
| Zapis do Google Contacts | Polityka read-only |
| Zmiana nazw w Google | Historia w Footing, nie w telefonie |
| Edycja surowych CSV | CSV = eksport/raport, nie UI |
| CEIDG / Brevo mailing | Osobny tor |
| **Produkty / magazyn / Woo sync** | **Przyszły etap** – nie w bieżącym sprincie |

## Architektura docelowa

```
Źródła surowe  →  Bufor akceptacji  →  Footing Panel (Klienci | Zamówienia)  →  SQLite
Google (read-only)  →  cache           →  contact_snapshots
Eksport CSV      ←  raporty           ←  Footing System
```

## Cursor vs Panel

| Narzędzie | Rola |
|-----------|------|
| **Cursor** | Programowanie, refaktoryzacja, nowe moduły |
| **Footing Panel** | Codzienna operacja: akceptacje w Klienci i Zamówienia |
