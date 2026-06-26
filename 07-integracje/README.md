# 07-integracje – adaptery zewnętrzne

**Tylko pobieranie i wysyłanie danych.** Bez logiki biznesowej.

| Integracja | Folder | Pion korzystający |
|------------|--------|-------------------|
| Google (People, Sheets, OAuth) | `google/` | 01-system, 05-sprzedaz |
| WooCommerce | `woocommerce/` | 05-sprzedaz |
| Brevo | `brevo/` | 06-marketing |
| Allegro | `allegro/` | 05-sprzedaz / 06-marketing |
| OLX | `olx/` | 06-marketing |
| YouTube | `youtube/` | 06-marketing |
| Facebook / Instagram | `facebook-instagram/` | 06-marketing |
| TikTok | `tiktok/` | 06-marketing |
| Pinterest | `pinterest/` | 06-marketing |
| X (Twitter) | `x/` | 06-marketing |
| LinkedIn | `linkedin/` | 06-marketing |
| Etsy | `etsy/` | 06-marketing |
| Slack | `slack/` | 01-system (powiadomienia) |
| Google Merchant Center | `merchant-center/` | 06-marketing |
| Google Search Console | `search-console/` | 06-marketing |
| Google Analytics | `analytics/` | 06-marketing |

## Zasady

1. Credentials w `00-inbox/`, `.env` lub `config.json` – **nigdy w Git**.
2. Jeden adapter = jeden kanał, cienka warstwa HTTP/API.
3. Decyzje (co synchronizować, kiedy) → `05-sprzedaz` lub `06-marketing`.

## Status

Foldery dokumentacyjne – brak implementacji w tym etapie.
