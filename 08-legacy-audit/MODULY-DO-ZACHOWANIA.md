# Moduły do zachowania (logika / koncepcja)

> Zachować **pomysł i reguły biznesowe**, niekoniecznie kod linia po linii.

## Tabela funkcji monolitu → Footing System

| Funkcja legacy | Obszar | Czy zachować | Dlaczego | Docelowy folder |
|---|---|---|---|---|
| `getSettings` | G1 globalne | Tak (koncepcja) | Centralna konfiguracja wymagana przez wszystkie moduły | `07-integracje/google/` + lokalny `.env` |
| `logEvent` | G1 globalne | Tak | Audyt operacji sync i błędów API | `07-integracje/google/` lub `05-sprzedaz/` (log operacyjny) |
| `sendToWooCommerce` | G1 globalne | Tak | Jedna warstwa HTTP + auth do Woo | `07-integracje/woocommerce/` |
| `getDynamicSheetId` | G1 globalne | Tak (koncepcja) | Identyfikacja docelowego arkusza | `07-integracje/google/` |
| `parseDate` | G1 globalne | Tak | Parsowanie dat z arkusza (`date_on_sale_from`) | `05-sprzedaz/woocommerce-sheets-sync/` |
| `getProductById` | D1 parametry | Tak | Punkt wejścia do mapowania pól Woo → kolumny | `07-integracje/woocommerce/` (read) |
| `fetchProductCategories` | D1 parametry | Tak | Synchronizacja słownika kategorii | `07-integracje/woocommerce/` + `05-sprzedaz/` |
| `fetchAllProductParameters` | D1 parametry | Tak | Rdzeń dynamicznych kolumn produktu | `05-sprzedaz/woocommerce-sheets-sync/` |
| `updateWooParametersSheet` | D1 parametry | Tak | Rejestr znanych parametrów Woo | `05-sprzedaz/woocommerce-sheets-sync/` |
| `addMissingColumnsToProducts` | D1 parametry | Tak | Rozszerzanie schematu arkusza `produkty` | `05-sprzedaz/woocommerce-sheets-sync/` |
| `updateAllWooCommerceParameters` | D1 parametry | Tak | Orkiestracja pełnego cyklu parametryzacji | `05-sprzedaz/woocommerce-sheets-sync/` |
| `getProductIdBySku` | D2 produkty | Tak | Most SKU (arkusz) ↔ ID (Woo) | `07-integracje/woocommerce/` |
| `addNewProduct` | D2 produkty | Tak (z walidacją) | Tworzenie produktów ze sklepu z arkusza | `05-sprzedaz/woocommerce-sheets-sync/` |
| `exportProductChanges` | D2 produkty | Tak (ostrożnie) | Eksport edycji wiersza do Woo | `05-sprzedaz/woocommerce-sheets-sync/` |
| `exportProductImages` | D2 produkty | Tak | Osobna ścieżka dla mediów | `05-sprzedaz/woocommerce-sheets-sync/` |
| `scheduledProductExport` | D2 produkty | Tak | Harmonogram ofert / aktywacji | `05-sprzedaz/woocommerce-sheets-sync/` |
| `updateInventoryHistory` | D3 magazyn | **Tak – priorytet** | Wymaganie biznesowe: historia stanów początkowych | `05-sprzedaz/magazyn/` |
| `syncStockBalanced` | D3 magazyn | **Tak – priorytet** | Rdzeń bilansu G↔W z `initial_stock` | `05-sprzedaz/magazyn/` |
| `onEdit` | D3 magazyn | Tak (koncepcja) | Reakcja na zmianę w arkuszu | `05-sprzedaz/magazyn/` |
| `scheduleSync` | D3 magazyn | Tak (koncepcja) | Okresowa synchronizacja | `05-sprzedaz/magazyn/` |

## Moduły plikowe (poziom legacy repo)

| Moduł legacy | Co zachować |
|--------------|-------------|
| `inventory.js` | Bilans stanów Sheet ↔ Woo z `initial_stock`; historia; G→W / W→G; LockService |
| `products.js` | CRUD produktów; eksport wiersza → Woo; SKU → ID |
| `parameters/` | Fetch → columns → update → produkty |
| `category.js` | Synchronizacja kategorii WooCommerce |
| `schedule.js` | Zaplanowany eksport (`date_on_sale_from`) |
| `sync.js` | Orkiestracja kierunku synchronizacji |
| `api.js` | Warstwa HTTP WooCommerce |
| `spreadsheet.js` | Operacje na arkuszach |
| `logger.js` | Logi do `logi` + konsola |
| `settings.js` / `config.js` | Konfiguracja lokalna (`.env`) |
| `seo.js` | Słowa kluczowe – **osobny pion** → `06-marketing/seo/` |

## Testy / jakość (koncepcja)

- Jest dla modułów krytycznych (inventory, sync, parameters)
- ESLint + Prettier + CI przed wdrożeniem
- Checklista funkcji z monolitu przed każdym merge modułu

## Status audytu

Inwentaryzacja funkcji monolitu: **wykonana** → [LEGACY-CONTEXT.md](./LEGACY-CONTEXT.md#kod-monolityczny--funkcje-źródłowe).  
Następny krok: porównanie z wersjami modułowymi w LEGACY-CONTEXT (historia refaktoryzacji) – tabela braków w MODULY-DO-PRZEPISANIA.
