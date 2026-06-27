# aPaczka

Integracja kurierska – **na razie tylko model danych i eksport CSV**. Nie wysyłamy nic do API.

## Zasady bezpieczeństwa

- Klucze API, App Secret, tokeny i hasła **tylko lokalnie**, poza Git.
- Dozwolone miejsca: `01-system/config.json` (w `.gitignore`) lub zmienne środowiskowe Windows.
- **Nigdy** nie commituj credentials do repozytorium.

## Obecny etap

System generuje plik przygotowawczy:

`02-output-private/APACZKA-IMPORT-001.csv`

Tylko wysyłki ze statusem `gotowe_do_nadania`. Brakujące dane trafiają do `WYSYLKI-DO-SPRAWDZENIA.csv`.

Dane wejściowe pochodzą z modułu: `05-sprzedaz/wysylki/README.md`

# Plan integracji aPaczka

## Etap 1 (obecny)

- Model danych w CSV (`WYSYLKI.csv`, `PACZKI.csv`, `APACZKA-IMPORT-001.csv`).
- Klucz wysyłkowy `KLUCZ-WYSYLKOWY.csv` uzupełniany ręcznie.

## Etap 2

- Ręczny import lub przepisanie danych z `APACZKA-IMPORT-001.csv` do panelu aPaczka.

## Etap 3

- Test read-only API – słowniki usług, walidacja pól.

## Etap 4

- Tworzenie przesyłki przez API w trybie testowym / kontrolowanym (bez produkcji masowej).

## Etap 5

- Pobieranie numeru listu przewozowego i etykiety.

## Etap 6

- Tracking i synchronizacja statusów (`nadane`, doręczone itd.) z powrotem do Footing System.

## Konfiguracja (przyszłość)

Przykład lokalny w `config.json` (nie w Git):

```json
{
  "apaczka_api_key": "",
  "apaczka_app_secret": "",
  "apaczka_sandbox": true
}
```

Alternatywnie zmienne środowiskowe Windows, np. `FOOTING_APACZKA_API_KEY`.
