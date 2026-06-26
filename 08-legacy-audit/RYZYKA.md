# Ryzyka – stary synchronizator

## 1. Przycinanie logiki przy refaktoryzacji

**Opis:** Moduły (szczególnie `inventory`, `parameters`) były skracane w trakcie podziału; tracono m.in. historię magazynu, pełny bilans, obsługę `initial_stock`.

**Skutek:** Wdrożenie „modułowej” wersji bez audytu = utrata danych magazynowych.

**Mitigacja:** Checklista funkcji z monolitu; zakaz merge bez testów inventory.

## 2. Sekrety w arkuszu „ustawienia”

**Opis:** Wczesna wersja trzymała `consumer_key`, `consumer_secret`, `sheet_id` w Google Sheets.

**Skutek:** Wyciek credentials przez udostępniony arkusz.

**Mitigacja:** Wyłącznie `.env` / `00-inbox/` / lokalny `config.json` (już w Footing `.gitignore`).

## 3. LockService i równoległe sync

**Opis:** `syncStockBalanced()` używa `LockService`; trigger co 2 min + `onEdit`.

**Skutek:** Wyścigi, duplikaty aktualizacji stanów bez locka.

**Mitigacja:** Zachować mutex w nowej implementacji; rozważyć dłuższy interwał.

## 4. Dwukierunkowy sync bez master source

**Opis:** Reguły G→W i W→G zależą od porównania z `initial_stock`.

**Skutek:** Błędna interpretacja → rozjazd stanów sklep vs arkusz.

**Mitigacja:** Udokumentować master data source; testy na scenariuszach brzegowych.

## 5. Mieszanie GAS i Node

**Opis:** Testy w Node, produkcja w GAS – rozjazd środowisk.

**Skutek:** Testy przechodzą, produkcja pada.

**Mitigacja:** Jedno środowisko docelowe lub wspólny bundle.

## 6. SEO w tym samym repo co magazyn

**Opis:** `seo.js` obok `inventory.js` w jednym deployu.

**Skutek:** Zmiana SEO psuje sync operacyjny.

**Mitigacja:** Rozdzielić piony (`05-sprzedaz` vs `06-marketing`) – już w architekturze Footing.

## 7. Import monolitu do Footing System

**Opis:** Pokusa wklejenia 5000+ linii z LEGACY-CONTEXT.

**Skutek:** Konflikt z `01-system`, duplikacja, brak utrzymania.

**Mitigacja:** **Zakaz importu** – tylko audyt + małe moduły.

## 8. Dane klientów w Git

**Opis:** CSV, logi, arkusze z PII.

**Mitigacja:** `.gitignore` dla `00-inbox/`, `02-output-private/`, `*.csv` – utrzymać.

---

# Ryzyka funkcjonalne starego synchronizatora

Poniższe ryzyka dotyczą **zachowania biznesowego** funkcji z monolitu (G1, D1–D3), nie samej struktury repo.

## Nadpisanie stanów magazynowych

- **`syncStockBalanced`** wykonuje PUT `stock_quantity` do WooCommerce bez osobnego potwierdzenia użytkownika.
- **`exportProductChanges`** celowo pomija `stock_quantity`, ale inne moduły mogą nadpisać stany przy błędnej orkiestracji.
- **Skutek:** rozjazd stanów sklep vs rzeczywistość magazynowa; sprzedaż produktu niedostępnego.
- **Mitigacja w Footing:** stany tylko przez `05-sprzedaz/magazyn/`; dry-run; log każdej zmiany stanu.

## Utrata danych przy synchronizacji dwukierunkowej

- Logika opiera się na **`initial_stock`** jako punkcie odniesienia; błędna aktualizacja `initial_stock` psuje kolejne cykle G→W i W→G.
- **`updateInventoryHistory`** zapisuje historię w osobnym arkuszu – przy refaktoryzacji łatwo pominąć i stracić audyt.
- **Skutek:** niemożność odtworzenia „kto zmienił stan i kiedy”.
- **Mitigacja:** historia stanów jako wymaganie akceptacji przed wdrożeniem; backup arkusza przed sync.

## Obcięcie funkcji podczas refaktoryzacji

- W LEGACY-CONTEXT widać wielokrotne „przywracanie pełnych funkcji” po skróceniu modułów (`parameters`, `inventory`).
- Wersje modułowe mogły zawierać tylko szkielet `syncProductData()` bez bilansu magazynu.
- **Skutek:** wdrożenie „działającego” modułu bez pełnej logiki monolitu.
- **Mitigacja:** checklista 20 funkcji z monolitu; brak merge bez testów inventory.

## Mieszanie logiki sprzedaży z marketingiem

- `seo.js` w tym samym deployu co `inventory.js` i `products.js`.
- **`scheduledProductExport`** łączy harmonogram promocji z operacjami CRUD produktu.
- **Skutek:** zmiana SEO lub promocji psuje sync operacyjny.
- **Mitigacja:** architektura Footing – `05-sprzedaz` vs `06-marketing` (już przyjęta).

## Przechowywanie sekretów w arkuszu lub repozytorium

- Wczesny monolit: `consumer_key`, `consumer_secret` w zakładce `ustawienia`.
- Ryzyko commita `.env`, `google_credentials.json`, logów z tokenami.
- **Skutek:** wyciek dostępu do WooCommerce / Google.
- **Mitigacja:** `.env` + `00-inbox/` poza Git; read-only API na pierwszym etapie integracji.

## Zbyt częste wywołania WooCommerce API

- **`scheduleSync`**: trigger co **2 minuty** dla całego arkusza produktów.
- **`onEdit`**: każda edycja w `produkty` → pełny `syncStockBalanced` (GET + ewentualnie PUT per wiersz).
- **Skutek:** limity API, throttling, niestabilność sklepu.
- **Mitigacja:** debounce, batch, dłuższy interwał, sync przyrostowy (tylko zmienione wiersze).

## Brak blokady procesów przy równoległej synchronizacji

- Monolit używa **`LockService.tryLock(30000)`** w `syncStockBalanced`.
- Równolegle: trigger czasowy + `onEdit` + ręczne uruchomienie.
- **Skutek:** wyścigi, podwójne PUT, niespójny `initial_stock`.
- **Mitigacja:** obowiązkowy mutex w nowej implementacji; jeden worker sync na raz.

## Powiązane funkcje wysokiego ryzyka

| Funkcja | Główne ryzyko |
|---------|----------------|
| `syncStockBalanced` | Nadpisanie stanów + wyścigi + częste API |
| `exportProductChanges` | Nadpisanie niezamierzonych pól Woo |
| `addNewProduct` | Duplikaty SKU, brak rollbacku |
| `updateAllWooCommerceParameters` | Zmiana schematu arkusza bez kontroli |
| `onEdit` | Lawina sync przy każdej edycji komórki |

