# CEIDG Mailing 001 – podsumowanie

Wygenerowano: 2026-06-27 00:46

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
| Priorytet A | 1836 |
| Priorytet B | 15227 |
| Priorytet C | 106116 |
| Priorytet X | 1864 |
| Do sprawdzenia | 1188 |
| Eksport BREVO-CEIDG-001.csv | 122338 |
| TEST-050 | 50 |
| TEST-100 | 100 |
| A-001 | 1836 |
| B-001 | 15227 |
| C-001 | 105275 |
| Czas przetwarzania (s) | 218.3 |

## Podział według segmentów (rekordy z poprawnym e-mailem)

| Segment | Liczba |
|---|---:|
| pergole_altany_tarasy | 96 |
| ogrody_mala_architektura | 1116 |
| budownictwo_drewno | 313 |
| stolarnia_ciesielstwo | 1434 |
| domki_wiaty_konstrukcje | 32 |
| ogrodzenia_konstrukcje | 46 |
| konstrukcje_stalowe | 526 |
| brukarstwo_nawierzchnie | 842 |
| elektryka_lampy_ogrodowe | 977 |
| sklepy_ogrodnicze_budowlane | 366 |
| wykonawcy_lokalni | 13996 |
| uslugi_remontowo_budowlane | 11036 |
| architektura_krajobrazu | 279 |
| montaz_instalacje | 1322 |
| producenci_i_rzemioslo | 207 |
| szeroki_potencjal | 89750 |
| do_sprawdzenia | 841 |
| poza_grupa | 1864 |

## Rekomendowany pierwszy import do Brevo

**BREVO-CEIDG-TEST-050.csv (partia testowa priorytet A/B)**

## Uwagi jakościowe

- Rozpocznij od BREVO-CEIDG-TEST-050.csv, potem rozszerzaj partiami.

## Ostrożność przy kampanii CEIDG

- CEIDG jest **osobnym źródłem** – nie mieszać z klientami Google/SMS/e-mail.
- Wysyłka masowa B2B wymaga ostrożności prawnej (identyfikacja nadawcy, podstawa kontaktu).
- Kampanię testuj na **małej partii** (TEST-050, potem TEST-100).
- Wiadomość musi mieć **jasną identyfikację nadawcy** Footing.
- Musi być **prosty sposób wypisania / sprzeciwu** (link lub odpowiedź).
- **Nie wysyłać całej bazy naraz** – stopniowe rozszerzanie po analizie bounce/unsubscribe.
