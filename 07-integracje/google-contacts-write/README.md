# Google Contacts – zapis (WYŁĄCZONY)

## Status: read-only

**Zapis do Google Contacts jest wyłączony.**

Obecny Footing System działa w trybie **read-only** wobec Google Contacts:

- sync pobiera kontakty (`01-system/sync_google_contacts.py`)
- cache: `00-inbox/contacts_cache.csv`
- pole `nazwa_kontaktu_google` w CRM to **odczyt**, nie cel zapisu

## Czego system nie robi

- updateContact (People API)
- zmiana nazw kontaktów Google
- automatyczny write-back zamówień do telefonu
- Android Contacts Provider – zapis z mikroaplikacji

## Tytuł sprawy ≠ nazwa Google

Format operacyjny:

`YYYY.MM.DD Klient ILOSCxPRODUKT [INWESTYCJA] [NAZWA]`

to **tytul_sprawy** w Footing System, nie proponowana nazwa kontaktu Google.

Nie tworzymy:

- `proponowana_nowa_nazwa_google`
- `GOOGLE-CONTACTS-ZMIANY-DO-AKCEPTACJI.csv`

## Ewentualny przyszły zapis

Wymaga **osobnej decyzji biznesowej** i osobnego modułu. Przed jakimkolwiek zapisem obowiązkowe:

1. **Backup** kontaktów Google
2. **Dry-run** – podgląd zmian bez zapisu
3. **Akceptacja użytkownika** – każda partia lub każda zmiana
4. **Obsługa konfliktów** – etag / wersjonowanie People API
5. **Audyt** – log kto, kiedy, co zmienił

## Footing Panel i Quick Order

- **Footing Panel** – nie edytuje Google Contacts na starcie
- **Quick Order** – tworzy zdarzenia w Footing System, nie w telefonie

## Powiązane

- Odczyt: `07-integracje/google/README.md`
- CRM: `03-raporty/KONTROLA-CRM-KONTAKTY.md`
