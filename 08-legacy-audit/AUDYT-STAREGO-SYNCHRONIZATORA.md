# Audyt starego synchronizatora – skrót

## Czym był stary projekt

Aplikacja **Google Apps Script + Node.js** synchronizująca **WooCommerce** z **Google Sheets**: produkty, parametry, kategorie, stany magazynowe, harmonogram eksportu, fragment SEO.

## Stan projektu (wg LEGACY-CONTEXT)

- Rozpoczęty od **monolitu** w jednym pliku (GAS)
- Podzielony na moduły: `products`, `inventory`, `parameters`, `category`, `schedule`, `seo`, `sync`
- Narzędzia: `api`, `config`, `logger`, `spreadsheet`, `settings`, `helpers`
- CI: GitHub Actions, Jest, ESLint, Prettier, Babel, Clasp
- **Problem:** w trakcie refaktoryzacji moduły były **skracane**; szczególnie magazyn i parametry traciły pełną logikę (stany początkowe, bilans G↔W, historia)

## Technologie

Google Apps Script, WooCommerce REST API v3, Google Sheets API, LockService, Node.js/NPM, Jest, Clasp, Dotenv, GitHub Actions.

## Arkusze (legacy)

| Zakładka | Rola |
|----------|------|
| `produkty` | Główna tabela produktów |
| `ustawienia` | Konfiguracja (później częściowo `.env`) |
| `logi` | Zdarzenia |
| `woo_parametry` | Mapowanie parametrów WooCommerce |
| magazyn | Historia stanów (SKU w kolumnach) |

## Decyzja architektoniczna Footing System

Stary kod → **audyt w `08-legacy-audit/`** → ewentualne przepisanie do `05-sprzedaz/` + `07-integracje/woocommerce/` + `07-integracje/google/`.

Szczegóły: [AUDYT-PLAN.md](./AUDYT-PLAN.md).
