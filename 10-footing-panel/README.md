# Footing Panel

Docelowy **panel operacyjny Footing** – prosta aplikacja do codziennej obsługi bez Cursora, terminala i ręcznej edycji CSV.

## Na tym etapie

Folder zawiera **zakres i szkic modelu danych**. Pełny panel nie jest jeszcze zbudowany.

## Dwa główne miejsca pracy

| Obszar | Co obejmuje |
|--------|-------------|
| **Klienci** | Zaakceptowani + kandydaci z bufora, konflikty dopasowania, dane kontaktowe, historia |
| **Zamówienia** | Zaakceptowane + kandydaci, pozycje (szczegóły), korekty, Quick Order, statusy |

Użytkownik **nie** pracuje osobno w: buforze klientów, buforze zamówień, buforze pozycji, DO-SPRAWDZENIA ani kontaktach niepowiązanych – te warstwy są techniczne lub widoczne jako ostrzeżenia przy Kliencie/Zamówieniu.

## Trzy poziomy danych

1. **Surowe** – Google, SMS, e-mail, Quick Order (materiał wejściowy)
2. **Bufor** – `02-output-private/bufor/` – kandydaci `do_akceptacji`
3. **Czyste** – `KLIENCI.csv`, `ZAMOWIENIA.csv`, … – tylko zaakceptowane / historycznie uznane

## Czego panel **nie robi** na starcie

- **Nie edytuje Google Contacts** (read-only)
- Nie zastępuje programowania w Cursorze
- Nie zarządza jeszcze **katalogiem produktów ani magazynem** (zapisany przyszły etap)

## Powiązane dokumenty

- `PANEL-SCOPE.md` – zakres funkcji
- `DATA-MODEL-DRAFT.md` – szkic SQLite (bufor, akceptacja, dane czyste)

## Źródło prawdy

**Footing System** (docelowo SQLite) jest źródłem prawdy dla klientów, zamówień i historii.

Google Contacts: wyłącznie **odczyt** (`nazwa_kontaktu_google`).
