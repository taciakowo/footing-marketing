# 04-produkty – wiedza o produktach Footing

Kody produktów, warianty, zastosowania, grupy produktowe.

## Źródło prawdy

**Google Sheet** użytkownika (zakładka `baza_produktow_footing`) – szczegóły: [GOOGLE-SHEET-PRODUCT-MASTER.md](./GOOGLE-SHEET-PRODUCT-MASTER.md).

- SKU = klucz główny produktu
- Formuły i listy rozwijane w arkuszu są **dozwolone i pożądane**
- Footing System na tym etapie **tylko czyta** arkusz (read-only)
- Lokalne eksporty → `02-output-private/produkty/` (prywatne, poza Git)

## Pliki

- [PRODUKTY.md](./PRODUKTY.md) – główny opis asortymentu
- [GOOGLE-SHEET-PRODUCT-MASTER.md](./GOOGLE-SHEET-PRODUCT-MASTER.md) – Product Master, sync, audyt

## Skrypt

`01-system/product_sheet_sync.py` – snapshot wartości, formuł, walidacji, audyt braków, roboczy eksport Woo.

## Powiązania

- Parser zamówień z nazw kontaktu: `01-system/update_footing_database.py`
- Raport produktowy: `03-raporty/PRODUKCJA.md`, ranking w `PODSUMOWANIE.md`
- Publikacja (przyszłość): `07-integracje/woocommerce/` – Woo to miejsce publikacji, nie źródło prawdy

## Zasada

Tu trzymamy **wiedzę produktową**, nie stany magazynowe (stany → `05-sprzedaz/magazyn/`).
