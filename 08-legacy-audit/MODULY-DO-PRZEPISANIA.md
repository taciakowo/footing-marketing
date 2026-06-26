# Moduły do przepisania

> Przepisać = nowa implementacja w Footing System z testem kompletności względem monolitu.

## Tabela funkcji monolitu – co wymaga przepisania

| Funkcja legacy | Problem | Co trzeba przepisać | Priorytet | Docelowy moduł |
|---|---|---|---|---|
| **`syncStockBalanced`** | Najczęściej obcinana przy refaktoryzacji; złożona logika `initial_stock`, delta, G→W / W→G | Pełny algorytm bilansu + LockService + aktualizacja `last_sync` + wywołanie historii | **Krytyczny** | `05-sprzedaz/magazyn/` |
| **`updateInventoryHistory`** | Format arkusza magazyn (SKU = kolumny); łatwo pominąć przy skróconym `inventory.js` | Zapis pary: stan + wiersz z datą i źródłem; auto-dodawanie kolumny SKU | **Krytyczny** | `05-sprzedaz/magazyn/` |
| **`exportProductChanges`** | PUT całego wiersza jako payload – ryzyko nadpisania pól Woo; w monolicie anonimowa funkcja IIFE | Whitelist pól, walidacja typów, wykluczenie `stock_quantity` i pól systemowych | **Wysoki** | `05-sprzedaz/woocommerce-sheets-sync/` |
| **`addNewProduct`** | Minimalna walidacja (sku, name, price); brak idempotencji przy ponownym wywołaniu | Walidacja wymaganych pól, mapowanie nagłówków, zapis ID z powrotem do arkusza, ochrona przed duplikatem SKU | **Wysoki** | `05-sprzedaz/woocommerce-sheets-sync/` |
| **`updateAllWooCommerceParameters`** | Zależność od `getProductById()` z jednym URL – nie skaluje na wiele produktów | Pętla po produktach / batch; pełny łańcuch D1 z testem regresji kolumn | **Wysoki** | `05-sprzedaz/woocommerce-sheets-sync/` |
| `getSettings` | Wcześniej czytał sekrety z arkusza | Odczyt wyłącznie z `.env` / lokalnego config; zero secretów w Sheets | Średni | `07-integracje/google/` |
| `sendToWooCommerce` | Brak rate limit / retry | Adapter cienki + retry, log statusów, timeout | Średni | `07-integracje/woocommerce/` |
| `fetchAllProductParameters` | Miesza kategorie globalne z polami jednego produktu | Rozdzielić: meta produktu vs słownik kategorii | Średni | `05-sprzedaz/woocommerce-sheets-sync/` |
| `addMissingColumnsToProducts` | Modyfikuje nagłówki arkusza bez migracji danych | Bezpieczne dodawanie kolumn + dokumentacja schematu | Średni | `05-sprzedaz/woocommerce-sheets-sync/` |
| `onEdit` | Każda edycja komórki → pełny sync magazynu | Debounce / sync tylko przy zmianie `stock_quantity` lub jawny przycisk | Średni | `05-sprzedaz/magazyn/` |
| `scheduleSync` | Trigger co 2 min – agresywny dla API | Konfigurowalny interwał; harmonogram poza GAS jeśli sync lokalny | Średni | `05-sprzedaz/magazyn/` |
| `scheduledProductExport` | Miesza logikę daty promocji z exportem produktu | Osobny scheduler + jawne reguły aktywacji oferty | Niski | `05-sprzedaz/woocommerce-sheets-sync/` |
| `exportProductImages` | PUT nadpisuje całą galerię | Tryb merge vs replace; walidacja URL | Niski | `05-sprzedaz/woocommerce-sheets-sync/` |
| `getProductById` | Jeden produkt na ustawienie URL | Parametr productId; uogólnienie API | Niski | `07-integracje/woocommerce/` |
| `fetchProductCategories` | `per_page=100` bez paginacji | Paginacja kategorii | Niski | `07-integracje/woocommerce/` |
| `parseDate` | Reguły locale / strefa czasowa | Jawna strefa `Europe/Warsaw`, testy brzegowe | Niski | `05-sprzedaz/woocommerce-sheets-sync/` |

## Moduły plikowe (poziom legacy repo)

| Moduł | Powód przepisania |
|-------|-------------------|
| `inventory.js` | Najczęściej przycinany; pełna logika D3 |
| `sync.js` | Orkiestracja – master source, idempotencja |
| `parameters/` | Złożony przepływ fetch → columns → update |
| `products.js` | Eksport wielu pól, zdjęcia, walidacja |
| `schedule.js` | GAS triggers vs lokalny cron |
| `category.js` | Zależność od api.js |
| `api.js` | → `07-integracje/woocommerce/` |
| `spreadsheet.js` | → `07-integracje/google/` |
| `seo.js` | → `06-marketing/seo/` (osobny pion) |

## Środowisko wykonania

Stary projekt: **GAS + Clasp + Node (testy)**.  
Footing System: decyzja otwarta – GAS vs Python lokalnie vs hybrid.

## Zasada przepisywania

1. Jeden moduł / funkcja na raz.
2. Checklista z [LEGACY-CONTEXT – funkcje źródłowe](./LEGACY-CONTEXT.md#kod-monolityczny--funkcje-źródłowe).
3. Test regresji przed usunięciem starego kodu.
4. **Zakaz** skracania `syncStockBalanced` i `updateInventoryHistory` bez checklisty akceptacji.
