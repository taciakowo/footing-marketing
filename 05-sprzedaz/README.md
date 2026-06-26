# 05-sprzedaz – pion sprzedażowo-operacyjny

Odpowiada za **operacyjną** stronę firmy: sklep, magazyn, zamówienia, synchronizacja danych produktowych.

## Zakres (docelowo)

- WooCommerce (produkty, stany, zamówienia)
- Google Sheets (operacyjne arkusze)
- Historia stanów magazynowych
- Synchronizacja WooCommerce ↔ Google Sheets
- Obsługa zamówień i dostępności

## Co tu **nie** należy

- Kampanie e-mail, SEO, social media → `06-marketing/`
- Surowe adaptery API → `07-integracje/`
- Parser kontaktów/SMS → `01-system/`

## Podfoldery (przygotowane, puste)

| Folder | Przeznaczenie |
|--------|---------------|
| `woocommerce-sheets-sync/` | Przyszła synchronizacja Woo ↔ Sheets (po audycie legacy) |
| `magazyn/` | Stany, historia, bilans G↔W |
| `zamowienia/` | Operacyjna obsługa zamówień |

## Powiązania

- Wiedza o produktach: `04-produkty/`
- Integracja WooCommerce: `07-integracje/woocommerce/`
- Integracja Google Sheets: `07-integracje/google/`
- Audyt starego kodu: `08-legacy-audit/`

## Status

**Etap architektury i audytu** – brak kodu synchronizacji. Stary synchronizator jest w audycie, nie w tym folderze.

Inwentaryzacja funkcji monolitu: `08-legacy-audit/LEGACY-CONTEXT.md#kod-monolityczny--funkcje-źródłowe`.

# Docelowe moduły pionu sprzedażowego

| Moduł | Folder / integracja | Funkcje legacy (referencja) |
|-------|----------------------|----------------------------|
| **Produkty** | `05-sprzedaz/woocommerce-sheets-sync/` | D2: `getProductIdBySku`, `addNewProduct`, `exportProductChanges`, `exportProductImages` |
| **Magazyn** | `05-sprzedaz/magazyn/` | D3: `updateInventoryHistory`, `syncStockBalanced`, `onEdit`, `scheduleSync` |
| **Zamówienia** | `05-sprzedaz/zamowienia/` | (poza monolitem – przyszły Woo orders) |
| **Synchronizacja Woo ↔ Sheets** | `05-sprzedaz/woocommerce-sheets-sync/` | Orkiestracja D1–D3, `sync.js` |
| **Historia stanów** | `05-sprzedaz/magazyn/` | `updateInventoryHistory`, arkusz magazyn |
| **Import/eksport produktów** | `05-sprzedaz/woocommerce-sheets-sync/` | D1 + D2 |
| **Walidacja przed Woo** | `05-sprzedaz/woocommerce-sheets-sync/` | Wymagane przed każdym POST/PUT (nowe w Footing) |

Lista szczegółowa:

- produkty
- magazyn
- zamówienia
- synchronizacja WooCommerce ↔ Google Sheets
- historia stanów
- import/eksport produktów
- walidacja danych przed wysłaniem do WooCommerce
