# Plan audytu starego synchronizatora WooCommerce ↔ Google Sheets

Materiał źródłowy: [LEGACY-CONTEXT.md](./LEGACY-CONTEXT.md)

---

# 1. Cel starego synchronizatora

- Utrzymywać **spójność produktów i stanów magazynowych** między **WooCommerce** a **Google Sheets**.
- Umożliwić **edycję operacyjną** w arkuszu (ceny, parametry, stany) z eksportem do sklepu.
- **Automatyzować** eksport zaplanowanych ofert i synchronizację okresową (triggery).
- Pobocznie: **parametryzacja kolumn** produktu z WooCommerce; fragment **SEO** (słowa kluczowe).

---

# 2. Technologie użyte w starym projekcie

| Technologia | Zastosowanie |
|-------------|--------------|
| Google Apps Script | Produkcja: Sheets, UrlFetchApp, LockService, triggery |
| WooCommerce REST API v3 | Produkty, kategorie, stany, atrybuty |
| Google Sheets API | Zakładki: produkty, ustawienia, logi, woo_parametry, magazyn |
| Node.js + NPM | Testy, lint, build |
| Jest | Testy jednostkowe modułów |
| ESLint + Prettier | Jakość kodu |
| Babel | Transpilacja |
| Dotenv | Sekrety poza arkuszem |
| Clasp | Deploy do GAS |
| GitHub Actions | CI |
| LockService | Mutex synchronizacji magazynu |

---

# 3. Moduły starego projektu

## `src/modules/`

| Moduł | Pliki | Rola |
|-------|-------|------|
| `parameters/` | columns, fetch, index, update | Parametry produktu, dynamiczne kolumny |
| `category.js` | | Kategorie WooCommerce |
| `inventory.js` | | Stany, historia, bilans G↔W |
| `products.js` | | CRUD produktów, eksport, zdjęcia |
| `schedule.js` | | Harmonogram eksportu |
| `seo.js` | | SEO / słowa kluczowe |
| `sync.js` | | Główna synchronizacja |

## `src/utils/`

api, config, dotenv.config, helpers, initial, logger, settings, spreadsheet

## `tests/`

Moduły: inventory, parameters, products, schedule, sync; utils: api, logger, settings, spreadsheet

---

# 4. Funkcje sprzedażowo-operacyjne

- Pobieranie/aktualizacja produktów WooCommerce z arkusza `produkty`
- Mapowanie SKU → product ID
- Dodawanie nowych produktów (POST)
- Aktualizacja pól (PUT), w tym zdjęć
- **Synchronizacja stanów** z `initial_stock` jako punktem odniesienia
- **Historia magazynu** per SKU (kolumny w arkuszu magazyn)
- Trigger `onEdit` na arkuszu produktów → sync
- Harmonogram co N minut (`scheduleSync`, `syncStockBalanced`)
- Parametry: `fetchAllProductParameters`, `updateWooParametersSheet`, `addMissingColumnsToProducts`
- Kategorie: `fetchProductCategories`, `syncCategories`
- Logi operacji do zakładki `logi`

**Docelowy pion Footing:** `05-sprzedaz/`

---

# 5. Funkcje marketingowe i SEO

- `seo.js` – generowanie / powiązanie słów kluczowych z produktami (zakres do doprecyzowania w LEGACY-CONTEXT)
- Zaplanowany eksport ofert (`date_on_sale_from`) ma wymiar promocyjny, ale jest zaimplementowany w module produktów/harmonogramu

**Docelowy pion Footing:** `06-marketing/seo/`

---

# 6. Funkcje integracyjne

- `sendToWooCommerce` / `api.js` – HTTP + auth
- `spreadsheet.js` – odczyt/zapis arkuszy
- `getSettings`, `getDynamicSheetId` – konfiguracja
- `logEvent` / `logger.js` – audyt zdarzeń
- Clasp deploy, GitHub Actions – pipeline (nie logika biznesowa)

**Docelowy pion Footing:** `07-integracje/`

---

# 7. Funkcje niebezpieczne lub wymagające ostrożności

| Obszar | Ryzyko |
|--------|--------|
| `syncStockBalanced` | Błędny bilans → zły stan w sklepie |
| `onEdit` → pełny sync | Każda edycja komórki uruchamia sync |
| Trigger co 2 min | Obciążenie API, kolizje bez LockService |
| Eksport całego wiersza jako payload PUT | Nadpisanie pól Woo niezamierzone |
| Credentials w arkuszu (wczesna wersja) | Wyciek kluczy API |
| Skrócone moduły po refaktoryzacji | Brakująca logika vs monolit |

Szczegóły: [RYZYKA.md](./RYZYKA.md)

---

# 8. Elementy do zachowania

Koncepcja i reguły – patrz [MODULY-DO-ZACHOWANIA.md](./MODULY-DO-ZACHOWANIA.md).

Skrót:

- Bilans magazynu z `initial_stock` i historią
- Warstwa API WooCommerce z logowaniem błędów
- Dynamiczne kolumny parametrów
- Lock / mutex przy synchronizacji
- Centralne logi zdarzeń
- Testy modułów krytycznych

---

# 9. Elementy do przepisania

Patrz [MODULY-DO-PRZEPISANIA.md](./MODULY-DO-PRZEPISANIA.md).

Priorytet: **inventory → sync → parameters → products**.

---

# 10. Elementy do odrzucenia

| Element | Powód |
|---------|--------|
| Monolit 5000+ linii jako jeden plik | Nieużywalny w Footing; tylko referencja |
| Credentials w zakładce `ustawienia` | Zastąpione `.env` |
| Mieszanie deploy GAS + ad-hoc skrypty Node w produkcji | Jedno środowisko docelowe |
| Duplikaty funkcji po nieudanych refaktoryzacjach | Wymagać jednej wersji canonical |
| Wklejenie całego starego repo do `01-system/` | Konflikt z parserem klientów |

---

# 11. Pytania wymagające wyjaśnienia

1. **Master source:** W konflikcie Sheet vs Woo – który system jest nadrzędny dla stanów? Dla cen?
2. **Czy GAS pozostaje?** Czy sync ma być lokalny (Python) jak `01-system`?
3. **Pełna kopia repo** `footing-sync` – gdzie jest ostatni commit z kompletnym kodem (poza LEGACY-CONTEXT)?
4. **Zakres seo.js** – jakie dokładnie wyjścia (arkusz, Woo meta, oba)?
5. **Arkusz magazyn** – czy format kolumn=SKU jest nadal aktualny biznesowo?
6. **Częstotliwość sync** – 2 minuty to wymaganie czy eksperyment?
7. **Relacja do Footing `04-produkty/`** – czy kody Z25/K98 mapują się na SKU Woo?
8. **Zamówienia Woo** – czy wchodzą w scope sync, czy tylko produkty/stany?

---

# 12. Proponowany pierwszy mały krok po audycie

**Inwentaryzacja funkcji monolitu vs modułów** (1 sesja, bez kodu):

1. W LEGACY-CONTEXT (sekcja „Kod monolityczny”) wypisać listę funkcji D1–D3 (parametry, export, magazyn).
2. Porównać z listą eksportów w `inventory.js`, `products.js`, `parameters/` z opisu w LEGACY-CONTEXT.
3. Uzupełnić tabelę „brakujące funkcje” w `MODULY-DO-PRZEPISANIA.md`.
4. Wybrać **jeden** read-only krok implementacyjny: np. adapter `07-integracje/woocommerce/` – `GET /products?per_page=1` + log do pliku lokalnego (bez zapisu do Sheets).

Dopiero potem: pierwszy moduł w `05-sprzedaz/woocommerce-sheets-sync/`.
