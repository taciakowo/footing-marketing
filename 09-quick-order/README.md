# Footing Quick Order

Szybki **łącznik** między telefonem a Footing System – **nie jest pełnym CRM**.

## Skąd trafia zdarzenie

- historia połączenia
- SMS
- udostępniony numer
- udostępniony kontakt / tekst

## Minimalne dane (wymagane)

| Pole JSON | Opis |
|-----------|------|
| phone | Numer telefonu |
| event_date / data | Data zdarzenia |
| items_text | Ilość + produkt, np. `4xZ25-K130` |

## Opcjonalne

| Pole JSON | Opis |
|-----------|------|
| inwestycja / investment | Np. Pergola |
| customer_name_raw | Nazwa klienta – tylko jeśli użytkownik wpisze |
| notatka / note | Krótka notatka |
| shared_text_raw | Surowy tekst z udostępnienia |
| source | call_log, sms, share, … |

## Przetwarzanie

Skrypt: `01-system/quick_order_events.py`

1. Wczytuje JSON zdarzenia
2. Normalizuje telefon
3. Waliduje wymagane pola
4. Rozpoznaje produkty z `items_text`
5. Buduje **tytul_sprawy** (Footing System – nie nazwa Google)
6. Zapisuje:
   - `02-output-private/quick-order/QUICK-ORDER-EVENTS.csv`
   - `02-output-private/quick-order/QUICK-ORDER-DO-AKCEPTACJI.csv`

## Google Contacts

Quick Order **nie zapisuje** do Google Contacts i **nie tworzy** plików zmian Google.

## Pełna obsługa zamówień

Akceptacja, korekta ilości i produktów → **Footing Panel** (`10-footing-panel/`).

## Przykład uruchomienia

```
python 01-system/quick_order_events.py 09-quick-order/examples/quick_order_event.example.json
```

## Format tytul_sprawy

```
YYYY.MM.DD Klient ILOSCxPRODUKT [INWESTYCJA] [SKROT_NAZWY_KLIENTA]
```

Przykład: `2026.06.27 Klient 4xZ25-K130 Pergola Kowalski`

Bez ilości – tytuł **nie** zawiera fikcyjnego `1x`.
