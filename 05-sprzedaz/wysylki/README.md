# Wysyłki

Moduł odpowiada za dane logistyczne Footing System – przygotowanie przesyłek bez wysyłania do API.

## Zakres

- dane odbiorcy (nazwa, firma, osoba kontaktowa),
- adres dostawy (ulica, nr domu, kod, miejscowość),
- kontakt do przesyłki (telefon, e-mail powiadomień),
- kategoria przesyłki (paczka, paleta, odbiór osobisty itd.),
- gabaryty i waga (z klucza wysyłkowego – bez zgadywania),
- status przygotowania wysyłki,
- eksport roboczy pod przyszłą integrację aPaczka.

## Pliki prywatne (generowane)

| Plik | Opis |
|------|------|
| `02-output-private/WYSYLKI.csv` | Jedna logiczna wysyłka = jeden wiersz |
| `02-output-private/PACZKI.csv` | Jedna fizyczna paczka / paleta = jeden wiersz |
| `02-output-private/WYSYLKI-DO-SPRAWDZENIA.csv` | Wysyłki wymagające ręcznej weryfikacji |
| `02-output-private/APACZKA-IMPORT-001.csv` | Tylko wysyłki `gotowe_do_nadania` (bez API) |
| `02-output-private/KLUCZ-WYSYLKOWY.csv` | Klucz wagowo-objętościowy – uzupełniany lokalnie |

Raport zbiorczy (bez PII): `03-raporty/WYSYLKI.md`

## Uruchomienie

```powershell
python 01-system/update_footing_database.py
```

Integracja API: `07-integracje/apaczka/README.md`
