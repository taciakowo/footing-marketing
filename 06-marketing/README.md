# 06-marketing – pion marketingowy

Odpowiada za **popyt, promocję i komunikację** – bez operacji magazynowych.

## Zakres (docelowo)

- SEO i frazy
- Kampanie Brevo
- Segmenty klientów
- Analiza pytań i popytu
- Social media
- Landing page i materiały promocyjne
- Treści (maile, posty)

## Co tu **nie** należy

- Synchronizacja stanów WooCommerce → `05-sprzedaz/`
- Parser kontaktów/SMS → `01-system/`

## Podfoldery (przygotowane)

| Folder | Przeznaczenie |
|--------|---------------|
| `seo/` | SEO, Search Console, Merchant Center (logika) |
| `brevo/` | Kampanie e-mail, konfiguracja |
| `kampanie/` | Plany kampanii (treść) |
| `segmenty/` | Segmentacja klientów |
| `landingi/` | Landing page, PDF, materiały |
| `social/` | Kanały social media |

## Foldery przejściowe (stary układ)

Treść do migracji:

- `05-kampanie/` → tutaj `kampanie/` i `brevo/`
- `06-landingi/` → tutaj `landingi/`

Migracja treści **nie wykonana** w tym etapie.

## Powiązania

- Raporty: `03-raporty/SEO.md`, `KAMPANIE.md`
- Integracje: `07-integracje/brevo/`, kanały social
- Segmenty CSV: `02-output-private/SEGMENTY-KLIENTOW.csv` (generowane przez 01-system)

## Status

**Etap architektury** – struktura folderów, bez nowych integracji.
