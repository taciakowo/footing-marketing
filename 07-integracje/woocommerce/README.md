# WooCommerce

REST API WooCommerce (produkty, kategorie, stany, zamówienia).

**WooCommerce jest miejscem publikacji**, nie źródłem prawdy o produktach. Źródło prawdy: Google Sheet `baza_produktow_footing` → `01-system/product_sheet_sync.py`.

## Moduł read-only (etap 1)

Skrypt: `01-system/woo_product_sync.py`

```powershell
python 01-system\woo_product_sync.py --fetch-woo
python 01-system\woo_product_sync.py --compare
python 01-system\woo_product_sync.py --dry-run --limit 5
python 01-system\woo_product_sync.py --dry-run --sku Z17-R130-U/M8
```

| Tryb | Opis | Zapis do sklepu |
|------|------|-----------------|
| `--fetch-woo` | `GET /products` z paginacją | **Nie** |
| `--compare` | Diff po SKU (arkusz vs snapshot Woo) | **Nie** |
| `--dry-run` | Payload aktualizacji JSON (bez PUT/POST) | **Nie** |
| `--write` | Zablokowany | `Write mode not implemented in this sprint.` |

Domyślne ścieżki:

- `--input-sheet-csv` → `02-output-private/produkty/PRODUKTY-GOOGLE-SHEET-VALUES.csv`
- `--output-dir` → `02-output-private/produkty/`

Pliki prywatne (poza Git):

| Plik | Zawartość |
|------|-----------|
| `PRODUKTY-WOO-REMOTE-SNAPSHOT.csv` | Snapshot produktów ze sklepu |
| `PRODUKTY-WOO-DIFF.csv` | Raport różnic po SKU |
| `PRODUKTY-WOO-DIFF.md` | Podsumowanie diff dla użytkownika |
| `PRODUKTY-WOO-UPDATE-DRY-RUN.json` | Payload aktualizacji (bez wysyłki) |

Porównywane pola (whitelist): `name`, `regular_price`, `sale_price`, `stock_quantity`, `stock_status`, `description`, `short_description`, `categories`, `tags`, `weight`, `dimensions`, `status`.

**Pominięte na tym etapie:** images, image_main, drawing, gallery, yoast, meta_data, variations (tylko informacyjnie w przyszłości).

Aktualizacja sklepu nastąpi **dopiero po akceptacji** raportu diff i dry-run. Zdjęcia/rysunki na razie przez standardowy mechanizm WooCommerce (URL/nazwa pliku w arkuszu); automatyczny upload mediów jest odłożony.

## Credentials

Prywatny plik (poza Git): `00-inbox/woo_credentials.json`

Wzór publiczny: [woo_credentials.example.json](./woo_credentials.example.json)

```json
{
  "store_url": "https://footing.pl",
  "consumer_key": "ck_...",
  "consumer_secret": "cs_..."
}
```

Nigdy nie commituj credentials ani snapshotów z `02-output-private/`.

## Operacje adaptera – status

| Operacja | Metoda API (Woo REST v3) | Kierunek | Status |
|----------|--------------------------|----------|--------|
| Pobieranie produktów | `GET /products` | Woo → lokalnie | **Działa** (`--fetch-woo`) |
| Porównanie po SKU | lokalnie | Sheet ↔ Woo | **Działa** (`--compare`) |
| Dry-run aktualizacji | lokalnie | Sheet → payload | **Działa** (`--dry-run`) |
| Aktualizacja produktów | `PUT /products/{id}` | lokalnie → Woo | **Zablokowane** |
| Tworzenie produktu | `POST /products` | lokalnie → Woo | **Zablokowane** |

## Zasady bezpieczeństwa

- Sekrety wyłącznie w `00-inbox/` – nigdy w arkuszu Google ani w repozytorium.
- Moduł domyślnie read-only; PUT/POST wymagają osobnego zatwierdzenia i osobnego sprintu.
- Rate limiting: paginacja `per_page=100`, bez równoległych zapisów.

## Powiązania

- Product Master (Sheet): [04-produkty/GOOGLE-SHEET-PRODUCT-MASTER.md](../../04-produkty/GOOGLE-SHEET-PRODUCT-MASTER.md)
- Odczyt arkusza: `01-system/product_sheet_sync.py`
- Audyt legacy: `08-legacy-audit/LEGACY-CONTEXT.md`
