# 08-legacy-audit – audyt starego synchronizatora

Folder na **analizę** niedokończonego projektu WooCommerce ↔ Google Sheets (Google Apps Script + Node.js).

## Zasada

> **Nie importować kodu 1:1** do Footing System. Najpierw audyt, potem małe kroki przepisywania.

## Pliki

| Plik | Opis |
|------|------|
| [LEGACY-CONTEXT.md](./LEGACY-CONTEXT.md) | Pełny materiał referencyjny (rozmowy, kod, historia refaktoryzacji) |
| [AUDYT-PLAN.md](./AUDYT-PLAN.md) | Plan audytu – sekcje 1–12 |
| [AUDYT-STAREGO-SYNCHRONIZATORA.md](./AUDYT-STAREGO-SYNCHRONIZATORA.md) | Skrót stanu projektu legacy |
| [MODULY-DO-ZACHOWANIA.md](./MODULY-DO-ZACHOWANIA.md) | Moduły z wartością do przeniesienia |
| [MODULY-DO-PRZEPISANIA.md](./MODULY-DO-PRZEPISANIA.md) | Moduły wymagające przepisania |
| [RYZYKA.md](./RYZYKA.md) | Ryzyka (przycinanie logiki, sekrety, LockService) |

## Docelowe piony po audycie

| Legacy moduł | Pion Footing System |
|--------------|---------------------|
| products, inventory, sync, parameters, category, schedule | `05-sprzedaz/` |
| seo | `06-marketing/seo/` |
| api, spreadsheet, logger, config | `07-integracje/` |

## Status

Etap **architektury i dokumentacji** – kod synchronizatora pozostaje poza tym repozytorium.
