# WooCommerce

REST API WooCommerce (produkty, kategorie, stany, zamówienia).

Legacy: `src/utils/api.js` (`sendToWooCommerce`), moduły `products.js`, `inventory.js`, `sync.js`.

Credentials: `.env` (`consumer_key`, `consumer_secret`, `base_url`) – **nie w Git**.

Logika synchronizacji → `05-sprzedaz/`, nie tutaj.

---

# WooCommerce – zakres integracji

Na tym etapie **tylko dokumentacja** – bez kodu produkcyjnego w repozytorium.

## Planowane operacje adaptera (`07-integracje/woocommerce/`)

| Operacja | Metoda API (Woo REST v3) | Kierunek | Status |
|----------|--------------------------|----------|--------|
| Pobieranie produktów | `GET /products` | Woo → lokalnie | Do zaimplementowania (read-only first) |
| Pobieranie produktu po ID | `GET /products/{id}` | Woo → lokalnie | Do zaimplementowania |
| Pobieranie po SKU | `GET /products?sku=` | Woo → lokalnie | Legacy: `getProductIdBySku` |
| Pobieranie kategorii | `GET /products/categories` | Woo → lokalnie | Legacy: `fetchProductCategories` |
| Aktualizacja produktów | `PUT /products/{id}` | lokalnie → Woo | **Zablokowane** do osobnego zatwierdzenia |
| Aktualizacja stanów magazynowych | `PUT /products/{id}` (`stock_quantity`) | lokalnie → Woo | **Zablokowane** – wysokie ryzyko |
| Tworzenie produktu | `POST /products` | lokalnie → Woo | **Zablokowane** – legacy: `addNewProduct` |

## Pierwszy krok techniczny (po audycie)

**Test read-only API:**

1. Jedno zapytanie `GET /products?per_page=1` z credentials w `.env`.
2. Log wyniku lokalnie (nie w Git).
3. Brak zapisu do WooCommerce bez osobnego zatwierdzenia.

## Zasady bezpieczeństwa

- Sekrety wyłącznie w `.env` / `00-inbox/` – nigdy w arkuszu Google ani w repozytorium.
- Rate limiting i retry – unikać wzorca trigger co 2 min + `onEdit` z monolitu.
- PUT/POST wymagają walidacji w `05-sprzedaz/` przed wywołaniem adaptera.

## Powiązania

- Logika biznesowa: `05-sprzedaz/magazyn/`, `05-sprzedaz/woocommerce-sheets-sync/`
- Audyt funkcji: `08-legacy-audit/LEGACY-CONTEXT.md#kod-monolityczny--funkcje-źródłowe`
