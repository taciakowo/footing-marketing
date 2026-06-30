# CEIDG Mailing 001 – podsumowanie

Wygenerowano: 2026-06-29 20:06

Rekordy bez adresu e-mail **nie są eksportowane** i **nie są kierowane do ręcznej weryfikacji**, ponieważ sprint dotyczy mailingu.

## Statystyki zbiorcze (bez danych osobowych)

| Metryka | Liczba |
|---|---:|
| Pliki w 00-inbox/input | 1 |
| Przetworzone pliki | baza_ceidg_footing.csv |
| Rekordy wejściowe | 509259 |
| Rekordy bez e-maila | 382824 |
| Rekordy z poprawnym e-mailem | 125043 |
| Rekordy z błędnym e-mailem | 37 |
| Duplikaty e-mail usunięte | 1357 |
| Rekordy po czyszczeniu (z e-mailem) | 125043 |
| Priorytet A | 1258 |
| Priorytet B | 2475 |
| Priorytet C | 119477 |
| Priorytet X | 1833 |
| Do sprawdzenia | 525 |
| Eksport BREVO-CEIDG-001.csv | 123033 |
| TEST-050-v2 | 50 |
| TEST-100-v2 | 100 |
| Podejrzenia false positive | 342 |
| A-001 | 1258 |
| B-001 | 2475 |
| C-001 | 119300 |
| Czas przetwarzania (s) | 141.6 |

## Podział według segmentów (rekordy z poprawnym e-mailem)

| Segment | Liczba |
|---|---:|
| pergole_altany_tarasy | 23 |
| ogrody_mala_architektura | 865 |
| budownictwo_drewno | 141 |
| stolarnia_ciesielstwo | 16 |
| domki_wiaty_konstrukcje | 3 |
| ogrodzenia_konstrukcje | 37 |
| konstrukcje_stalowe | 62 |
| brukarstwo_nawierzchnie | 490 |
| elektryka_lampy_ogrodowe | 231 |
| sklepy_ogrodnicze_budowlane | 324 |
| wykonawcy_lokalni | 11179 |
| uslugi_remontowo_budowlane | 1315 |
| architektura_krajobrazu | 226 |
| montaz_instalacje | 185 |
| producenci_i_rzemioslo | 234 |
| szeroki_potencjal | 107702 |
| do_sprawdzenia | 177 |
| poza_grupa | 1833 |

## Rekomendowany pierwszy import do Brevo

**BREVO-CEIDG-TEST-050-v2.csv (partia testowa priorytet A/B)**

## Uwagi jakościowe

- Rozpocznij od BREVO-CEIDG-TEST-050-v2.csv, potem rozszerzaj partiami.

## Ostrożność przy kampanii CEIDG

- CEIDG jest **osobnym źródłem** – nie mieszać z klientami Google/SMS/e-mail.
- Wysyłka masowa B2B wymaga ostrożności prawnej (identyfikacja nadawcy, podstawa kontaktu).
- Kampanię testuj na **małej partii** (TEST-050-v2, potem TEST-100-v2).
- Wiadomość musi mieć **jasną identyfikację nadawcy** Footing.
- Musi być **prosty sposób wypisania / sprzeciwu** (link lub odpowiedź).
- **Nie wysyłać całej bazy naraz** – stopniowe rozszerzanie po analizie bounce/unsubscribe.
