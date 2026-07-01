# Google Sheet – Product Master Footing

## Źródło prawdy

Aktualnym **źródłem prawdy o produktach** jest Google Sheet użytkownika, a nie plik CSV w repozytorium ani WooCommerce.

| Parametr | Wartość |
|---|---|
| Spreadsheet ID | `1YtWrOgyJgNXFYaSg5-TeApJOOP3R25b9b62TT7lZqXE` |
| Zakładka produktów | `baza_produktow_footing` |
| Klucz główny | **SKU** |

Footing System **nie tworzy** nowego `PRODUKTY-MASTER.csv` jako zamiennika arkusza. Lokalne pliki w `02-output-private/produkty/` to wyłącznie **snapshoty i raporty audytu**.

## Zasady współpracy z arkuszem

### Dozwolone i pożądane

- **Formuły** w komórkach (np. automatyczne uzupełnianie opisów, cen, parametrów).
- **Listy rozwijane** (data validation) – ręczne listy i listy oparte o zakres komórek.
- Ręczna edycja arkusza przez użytkownika jako główny sposób pracy.

### Czego Footing System nie robi (etap 1)

- **Nie zapisuje** niczego do Google Sheets.
- **Nie nadpisuje** formuł.
- **Nie nadpisuje** list rozwijanych ani walidacji.
- **Nie publikuje** automatycznie do WooCommerce.

## Moduł synchronizacji (read-only)

Skrypt: `01-system/product_sheet_sync.py`

```powershell
python 01-system\product_sheet_sync.py --snapshot-only
python 01-system\product_sheet_sync.py --inspect-formulas
python 01-system\product_sheet_sync.py --inspect-validations
python 01-system\product_sheet_sync.py --audit
python 01-system\product_sheet_sync.py --export-woo
```

Bez flag uruchamia pełny pipeline odczytu (wartości + formuły + walidacje + audyt + eksport Woo roboczy).

### Tryb A – Google Sheets API

1. Wartości obliczone / widoczne (`valueRenderOption=FORMATTED_VALUE`).
2. Formuły (`valueRenderOption=FORMULA`).
3. Walidacje / listy rozwijane (`spreadsheets.get` + `includeGridData`).
4. Dla list opartych o zakres – zapis `source_range` i pobranie wartości źródłowych.

Credentials (prywatne, poza Git): `00-inbox/google_credentials.json`, token: `00-inbox/google_token_sheets.json`.

Scope: `spreadsheets.readonly`.

### Stan integracji (2026-07)

Google Sheets API jest **włączone i działa częściowo**:

| Komenda | Wynik |
|---------|--------|
| `--snapshot-only` | OK — 142 produkty, 112 kolumn → `PRODUKTY-GOOGLE-SHEET-VALUES.csv` |
| `--inspect-validations` | OK — 852 walidacji / list rozwijanych |
| `--export-woo` | OK — `PRODUKTY-WOO-EXPORT.csv` (roboczy) |
| `--inspect-formulas` | **Problem otwarty** — 0 wykrytych formuł; wymaga poprawki odczytu |

Warstwa wartości i walidacji jest operacyjna. Warstwa formuł wymaga dopracowania w module — bez niej audyt nie rozróżnia poprawnie pustych komórek od komórek z formułą o pustym wyniku.

### Tryb B – lokalny CSV (`--input-csv`)

Praca na snapshocie wartości bez API. Raport zawiera:

- `formulas_available = 0`
- `validations_available = 0`
- `source_mode = csv`

Snapshoty prywatne używają separatora **`;`** w CSV (`Import-Csv ... -Delimiter ';'`).

## Pliki prywatne (`02-output-private/produkty/`)

| Plik | Zawartość |
|---|---|
| `PRODUKTY-GOOGLE-SHEET-VALUES.csv` | Snapshot wartości |
| `PRODUKTY-GOOGLE-SHEET-FORMULAS.csv` | Formuły per komórka |
| `PRODUKTY-GOOGLE-SHEET-VALIDATIONS.csv` | Walidacje / listy rozwijane |
| `PRODUKTY-BRAKI.csv` | Audyt braków |
| `PRODUKTY-RAPORT.md` | Raport dla użytkownika |
| `PRODUKTY-WOO-EXPORT.csv` | Roboczy eksport Woo – **bez publikacji** |

## WooCommerce

WooCommerce jest **miejscem publikacji**, nie źródłem prawdy. Eksport `PRODUKTY-WOO-EXPORT.csv` służy do weryfikacji przed ręczną lub przyszłą synchronizacją. Adapter REST: `07-integracje/woocommerce/`.

## Audyt braków

System rozróżnia:

| Sytuacja | Traktowanie |
|---|---|
| Pusta komórka bez formuły | Brak **krytyczny** (dla wymaganych pól) |
| Komórka z formułą, pusty wynik | **Ostrzeżenie** (`formula_present=1`, `calculated_value_empty=1`) |
| Brak SKU / duplikat SKU | **Krytyczne** |
| Brak pól publish (permalink, zdjęcia, kategorie…) | **Krytyczne** tylko gdy `status=publish` |

Sprawdzane m.in.: SKU, nazwa, cena, status, stock_status, permalink, image_main, drawing, categories, short_description, weight, dimensions oraz parametry techniczne (jeśli kolumny istnieją w arkuszu).

## Powiązania

- Asortyment (opis marketingowy): [PRODUKTY.md](./PRODUKTY.md)
- Integracja Woo (plan): [07-integracje/woocommerce/README.md](../07-integracje/woocommerce/README.md)
- Google OAuth: [07-integracje/google/README.md](../07-integracje/google/README.md)
