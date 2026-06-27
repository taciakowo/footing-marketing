# Segmenty klientów

**Tryb aktywny: FOOTING MAILING SPRINT 001** – patrz `03-raporty/SPRINT-MAILING-001.md`.

## Aktywne – segmentacja CEIDG

CEIDG **nie miesza się** z kontaktami Google / SMS / e-mail.

| Element | Opis |
|---------|------|
| Skrypt | `01-system/prepare_ceidg_mailing.py` |
| Wejście | `00-inbox/input/` (`.csv`, `.ods`, `.xlsx`) |
| Segmenty CEIDG | pergole_altany_tarasy, ogrody_mala_architektura, budownictwo_drewno, ogrodzenia_konstrukcje, elektryka_lampy_ogrodowe, sklepy_ogrodnicze_budowlane, wykonawcy_lokalni, do_sprawdzenia, poza_grupa |
| Priorytet | A, B (eksport Brevo), C, X (wykluczone) |
| Eksport | `02-output-private/marketing/BREVO-CEIDG-001.csv` |
| Raport | `03-raporty/CEIDG-MAILING-001.md` |

`zrodlo = ceidg` – osobna kampania B2B, osobna kontrola zgodności.

## Jak wrzucić plik CEIDG

1. Wrzuć plik `.csv`, `.ods` albo `.xlsx` do `00-inbox/input/`.
2. Zamknij plik w Excelu / LibreOffice (usuń pliki `.~lock*` jeśli zostały).
3. Uruchom:

   `python 01-system\prepare_ceidg_mailing.py`

4. Sprawdź raport:

   `03-raporty\CEIDG-MAILING-001.md`

5. Sprawdź eksport:

   `02-output-private\marketing\BREVO-CEIDG-001.csv`

System sam rozpozna plik CEIDG po nazwie i nagłówkach kolumn. Stary folder `02-output-private/ceidg/input/` działa tylko jako awaryjny fallback.

## Zamrożone w tym sprincie

- `02-output-private/SEGMENTY-KLIENTOW.csv` (CRM własny)
- `BREVO-KONTAKTY-001.csv` (mailing klientów własnych)
