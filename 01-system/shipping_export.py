"""Generowanie danych wysyłkowych Footing System (bez API aPaczka)."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

OUT_PRIVATE = Path(__file__).resolve().parent.parent / "02-output-private"
REPORTS = Path(__file__).resolve().parent.parent / "03-raporty"

POSTAL_RE = re.compile(r"\b(\d{2}-\d{3})\b")
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

SHIPPING_CATEGORIES = (
    "paczka_do_30kg",
    "cwiartka_palety",
    "pol_palety",
    "paleta_euro",
    "paleta_niestandardowa",
    "odbior_osobisty",
    "transport_indywidualny",
    "do_sprawdzenia",
)

WYSYLKI_COLS = [
    "data_zamowienia", "shipment_id", "order_id", "klient_id", "telefon_kontaktowy",
    "email_powiadomien", "nazwa_odbiorcy", "osoba_kontaktowa", "firma", "ulica", "nr_domu",
    "nr_lokalu", "kod_pocztowy", "miejscowosc", "kraj", "adres_surowy", "zrodlo_adresu",
    "pozycje_tekst", "produkt_glowny", "ilosc_laczna", "kategoria_wysylki", "liczba_paczek",
    "status_wysylki", "status_sprawdzenia", "uwagi",
]
PACZKI_COLS = [
    "data_zamowienia", "shipment_id", "package_id", "order_id", "klient_id", "produkt_glowny",
    "pozycje_tekst", "kategoria_paczki", "dlugosc_cm", "szerokosc_cm", "wysokosc_cm",
    "waga_kg", "liczba_sztuk_w_paczce", "czy_paczka_standardowa", "czy_paleta", "uwagi_pakowania",
]
WYSYLKI_REVIEW_COLS = [
    "powod", "data_zamowienia", "shipment_id", "order_id", "telefon", "email", "nazwa_kontaktu",
    "adres_surowy", "pozycje_tekst", "kategoria_wysylki", "brakujace_pola", "sugestia", "uwagi",
]
APACZKA_IMPORT_COLS = [
    "shipment_id", "order_id", "nazwa_odbiorcy", "osoba_kontaktowa", "firma", "telefon_kontaktowy",
    "email_powiadomien", "ulica", "nr_domu", "nr_lokalu", "kod_pocztowy", "miejscowosc", "kraj",
    "kategoria_paczki", "dlugosc_cm", "szerokosc_cm", "wysokosc_cm", "waga_kg", "uwagi",
    "status_gotowosci",
]
KLUCZ_COLS = [
    "produkt_lub_rodzina", "wariant", "kategoria_paczki", "dlugosc_cm", "szerokosc_cm",
    "wysokosc_cm", "waga_kg", "sztuk_na_paczke", "sztuk_na_cwiartke_palety",
    "sztuk_na_pol_palety", "sztuk_na_palete", "uwagi",
]

KLUCZ_SAMPLE_ROWS = [
    ("Z17", "", "do_sprawdzenia", "", "", "", "", "", "", "", "", "szkic – uzupełnij gabaryty"),
    ("Z25", "", "do_sprawdzenia", "", "", "", "", "", "", "", "", "szkic – uzupełnij gabaryty"),
    ("Z26", "", "do_sprawdzenia", "", "", "", "", "", "", "", "", "szkic – uzupełnij gabaryty"),
    ("K1", "", "do_sprawdzenia", "", "", "", "", "", "", "", "", "szkic – uzupełnij gabaryty"),
    ("K2", "", "do_sprawdzenia", "", "", "", "", "", "", "", "", "szkic – uzupełnij gabaryty"),
    ("H1", "", "do_sprawdzenia", "", "", "", "", "", "", "", "", "szkic – uzupełnij gabaryty"),
    ("H2", "", "do_sprawdzenia", "", "", "", "", "", "", "", "", "szkic – uzupełnij gabaryty"),
    ("W400", "", "do_sprawdzenia", "", "", "", "", "", "", "", "", "szkic – uzupełnij gabaryty"),
    ("W2001", "", "do_sprawdzenia", "", "", "", "", "", "", "", "", "szkic – uzupełnij gabaryty"),
    ("W2002", "", "do_sprawdzenia", "", "", "", "", "", "", "", "", "szkic – uzupełnij gabaryty"),
]

PICKUP_RE = re.compile(
    r"odbiór\s+osobist|odbior\s+osobist|sam\s+odbier|odbierze\s+osobi|"
    r"odbiór\s+w\s+siedzib|odbior\s+w\s+siedzib|po\s+odbiorze\s+osobist",
    re.I,
)
COMM_CATEGORY_RULES = [
    ("odbior_osobisty", r"odbiór\s+osobist|odbior\s+osobist|sam\s+odbior"),
    ("pol_palety", r"półpalet|polpalet|pol\s+palet"),
    ("cwiartka_palety", r"ćwierćpalet|cwiartka\s+palet|cwiercpalet"),
    ("paleta_euro", r"paleta\s+euro|europalet"),
    ("paleta_niestandardowa", r"paleta\s+niestandard|paleta\s+(?!euro)"),
    ("paczka_do_30kg", r"\bpaczk\w|\bkurier\b|\bwysyłk\w|\bwysylk\w"),
    ("transport_indywidualny", r"transport\s+indywidual|dostawa\s+własn|dostawa\s+wlasn"),
]


def ensure_klucz_wysylkowy(path: Path) -> list[dict]:
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [dict(zip(KLUCZ_COLS, row)) for row in KLUCZ_SAMPLE_ROWS]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=KLUCZ_COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return rows


def product_family(code: str) -> str:
    code = (code or "").upper().strip()
    m = re.match(r"^(Z\d+|K\d+|H\d+|W\d+|F25|F2)", code)
    if m:
        fam = m.group(1)
        return "Z25" if fam == "F2" else fam
    return code.split("-")[0] if code else ""


def lookup_klucz(klucz_rows: list[dict], produkt_glowny: str) -> dict | None:
    fam = product_family(produkt_glowny)
    for row in klucz_rows:
        if (row.get("produkt_lub_rodzina") or "").upper() == fam:
            return row
    return None


def extract_delivery_address(body: str) -> str:
    for line in body.splitlines():
        m = re.search(r"(?:Dostawa do:|Wysyłka:|Adres dostawy:|Adres:)\s*(.+)", line, re.I)
        if m:
            return m.group(1).strip()[:300]
    m = POSTAL_RE.search(body or "")
    if m:
        start = max(0, m.start() - 80)
        end = min(len(body), m.end() + 80)
        return body[start:end].strip()[:300]
    return ""


def parse_polish_address(raw: str) -> dict[str, str]:
    out = {
        "ulica": "", "nr_domu": "", "nr_lokalu": "", "kod_pocztowy": "",
        "miejscowosc": "", "kraj": "PL", "firma": "",
    }
    if not raw:
        return out
    postal = POSTAL_RE.search(raw)
    if postal:
        out["kod_pocztowy"] = postal.group(1)
        after = raw[postal.end():].strip(" ,;-")
        city = re.split(r"[,\n;]", after)[0].strip()
        if city and len(city) >= 2:
            out["miejscowosc"] = city[:80]
    street = re.search(
        r"(?:ul\.?|ulica|al\.?|aleja|os\.?|osiedle|pl\.?|plac)\s+"
        r"([^,\n]+?)\s+(\d+[A-Za-z]?)(?:[/\\](\d+))?(?:\s|$|,)",
        raw, re.I,
    )
    if street:
        out["ulica"] = street.group(1).strip()[:120]
        out["nr_domu"] = street.group(2)
        if street.group(3):
            out["nr_lokalu"] = street.group(3)
    elif not out["ulica"]:
        simple = re.search(r"([A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż .-]{3,40})\s+(\d+[A-Za-z]?)(?:[/\\](\d+))?", raw)
        if simple and not POSTAL_RE.match(simple.group(0)[:6]):
            out["ulica"] = simple.group(1).strip()
            out["nr_domu"] = simple.group(2)
            if simple.group(3):
                out["nr_lokalu"] = simple.group(3)
    return out


def classify_from_comm(comm_text: str) -> tuple[str, bool]:
    text = comm_text or ""
    for cat, pat in COMM_CATEGORY_RULES:
        if re.search(pat, text, re.I):
            return cat, True
    return "do_sprawdzenia", False


def classify_shipment_category(
    produkt_glowny: str, ilosc: int, comm_text: str, klucz_row: dict | None,
) -> tuple[str, bool]:
    comm_cat, comm_sure = classify_from_comm(comm_text)
    if comm_sure and comm_cat != "do_sprawdzenia":
        return comm_cat, True
    if PICKUP_RE.search(comm_text or ""):
        return "odbior_osobisty", True
    if klucz_row:
        kat = (klucz_row.get("kategoria_paczki") or "").strip()
        if kat and kat != "do_sprawdzenia":
            if ilosc > 0 and klucz_row.get("sztuk_na_palete"):
                try:
                    if ilosc >= int(klucz_row["sztuk_na_palete"]):
                        return "paleta_euro", True
                except ValueError:
                    pass
            if ilosc > 0 and klucz_row.get("sztuk_na_pol_palety"):
                try:
                    if ilosc >= int(klucz_row["sztuk_na_pol_palety"]):
                        return "pol_palety", True
                except ValueError:
                    pass
            return kat, kat != "do_sprawdzenia"
    return "do_sprawdzenia", False


def has_weight_or_key(klucz_row: dict | None, packages: list[dict]) -> bool:
    if klucz_row and (klucz_row.get("waga_kg") or "").strip():
        return True
    return any((p.get("waga_kg") or "").strip() for p in packages)


def has_dims_or_key(klucz_row: dict | None, packages: list[dict]) -> bool:
    if klucz_row and all(
        (klucz_row.get(k) or "").strip()
        for k in ("dlugosc_cm", "szerokosc_cm", "wysokosc_cm")
    ):
        return True
    return any(
        all((p.get(k) or "").strip() for k in ("dlugosc_cm", "szerokosc_cm", "wysokosc_cm"))
        for p in packages
    )


def build_packages_for_shipment(
    shipment_id: str,
    order: dict,
    items: list[dict],
    kategoria: str,
    klucz_row: dict | None,
) -> list[dict]:
    packages: list[dict] = []
    ilosc = int(order.get("ilosc_laczna") or 0)
    seq = 0

    def pkg_row(qty_in_pkg: int, kat: str, uwagi: str) -> dict:
        nonlocal seq
        seq += 1
        dims = klucz_row or {}
        is_paleta = kat in (
            "cwiartka_palety", "pol_palety", "paleta_euro", "paleta_niestandardowa",
        )
        return {
            "data_zamowienia": order.get("data_zamowienia", ""),
            "shipment_id": shipment_id,
            "package_id": f"{shipment_id}-P{seq:02d}",
            "order_id": order.get("order_id", ""),
            "klient_id": order.get("klient_id", ""),
            "produkt_glowny": order.get("produkt_glowny", ""),
            "pozycje_tekst": order.get("pozycje_tekst", ""),
            "kategoria_paczki": kat,
            "dlugosc_cm": dims.get("dlugosc_cm", ""),
            "szerokosc_cm": dims.get("szerokosc_cm", ""),
            "wysokosc_cm": dims.get("wysokosc_cm", ""),
            "waga_kg": dims.get("waga_kg", ""),
            "liczba_sztuk_w_paczce": qty_in_pkg or "",
            "czy_paczka_standardowa": "tak" if kat == "paczka_do_30kg" else "nie",
            "czy_paleta": "tak" if is_paleta else "nie",
            "uwagi_pakowania": uwagi,
        }

    if kategoria == "odbior_osobisty":
        packages.append(pkg_row(ilosc, "odbior_osobisty", "odbiór osobisty – bez paczki kurierskiej"))
        return packages

    per_paczka = 0
    if klucz_row and klucz_row.get("sztuk_na_paczke"):
        try:
            per_paczka = int(klucz_row["sztuk_na_paczke"])
        except ValueError:
            pass

    if per_paczka > 0 and ilosc > 0:
        remaining = ilosc
        while remaining > 0:
            take = min(remaining, per_paczka)
            packages.append(pkg_row(take, kategoria if kategoria != "do_sprawdzenia" else "do_sprawdzenia", ""))
            remaining -= take
    else:
        packages.append(pkg_row(ilosc, kategoria, "brak klucza sztuk_na_paczke – wymaga weryfikacji"))

    return packages


def validate_shipment(
    ship: dict, packages: list[dict], klucz_row: dict | None, pickup_hint: bool,
) -> tuple[list[str], str, str]:
    missing: list[str] = []
    if not (ship.get("nazwa_odbiorcy") or ship.get("firma")):
        missing.append("nazwa_odbiorcy_lub_firma")
    if not ship.get("telefon_kontaktowy"):
        missing.append("telefon_kontaktowy")
    if not (ship.get("ulica") or ship.get("miejscowosc")):
        missing.append("ulica_lub_miejscowosc")
    if not ship.get("nr_domu") and ship.get("kategoria_wysylki") != "odbior_osobisty":
        if not pickup_hint:
            missing.append("nr_domu")
    if not ship.get("kod_pocztowy") and ship.get("kategoria_wysylki") != "odbior_osobisty":
        if not pickup_hint:
            missing.append("kod_pocztowy")
    if not ship.get("miejscowosc") and ship.get("kategoria_wysylki") != "odbior_osobisty":
        if not pickup_hint:
            missing.append("miejscowosc")
    kat = ship.get("kategoria_wysylki", "")
    if not kat or kat == "do_sprawdzenia":
        missing.append("kategoria_wysylki")
    if kat != "odbior_osobisty" and not has_weight_or_key(klucz_row, packages):
        missing.append("waga_kg")
    if kat != "odbior_osobisty" and not has_dims_or_key(klucz_row, packages):
        missing.append("gabaryty")

    if pickup_hint and not ship.get("adres_surowy"):
        return missing, "odbior_osobisty_do_potwierdzenia", "odbior_osobisty_do_potwierdzenia"

    if missing:
        if not ship.get("adres_surowy") and not ship.get("telefon_kontaktowy"):
            return missing, "brak_danych", "do_sprawdzenia"
        return missing, "do_sprawdzenia", "do_sprawdzenia"

    return [], "gotowe_do_nadania", "ok"


def collect_order_logistics(
    orders: list[dict], komunikacja: list[dict],
) -> dict[str, dict]:
    by_order: dict[str, dict] = defaultdict(lambda: {"adres_surowy": "", "zrodlo_adresu": "", "comm_text": ""})
    for row in komunikacja:
        oid = row.get("powiazane_order_id", "")
        if not oid:
            continue
        text = " ".join([row.get("temat", ""), row.get("tresc", "")])
        by_order[oid]["comm_text"] += " " + text
        addr = extract_delivery_address(text)
        if addr and not by_order[oid]["adres_surowy"]:
            by_order[oid]["adres_surowy"] = addr
            by_order[oid]["zrodlo_adresu"] = row.get("kanal", "komunikacja").lower()
    return by_order


def build_shipping_exports(
    orders: list[dict],
    items: list[dict],
    clients: list[dict],
    komunikacja: list[dict],
    contacts: dict,
    write_csv_fn,
) -> dict:
    klucz_path = OUT_PRIVATE / "KLUCZ-WYSYLKOWY.csv"
    klucz_rows = ensure_klucz_wysylkowy(klucz_path)

    client_by_kid = {c["klient_id"]: c for c in clients}
    items_by_order: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        items_by_order[it["order_id"]].append(it)

    logistics = collect_order_logistics(orders, komunikacja)

    wysylki: list[dict] = []
    paczki: list[dict] = []
    review: list[dict] = []
    apaczka: list[dict] = []

    missing_field_counter: Counter = Counter()
    category_counter: Counter = Counter()
    status_counter: Counter = Counter()

    for order in orders:
        oid = order["order_id"]
        kid = order["klient_id"]
        client = client_by_kid.get(kid, {})
        pc = contacts.get(client.get("telefon", ""))
        log = logistics.get(oid, {})
        comm_text = log.get("comm_text", "")
        adres_surowy = log.get("adres_surowy", "")
        parsed = parse_polish_address(adres_surowy)

        shipment_id = f"S-{oid.replace('O-', '')}"
        ilosc = int(order.get("ilosc_laczna") or 0)
        klucz_row = lookup_klucz(klucz_rows, order.get("produkt_glowny", ""))
        pickup_hint = bool(PICKUP_RE.search(comm_text) or PICKUP_RE.search(adres_surowy))

        kategoria, _kat_sure = classify_shipment_category(
            order.get("produkt_glowny", ""), ilosc, comm_text, klucz_row,
        )
        if pickup_hint:
            kategoria = "odbior_osobisty"

        nazwa = ""
        if pc and getattr(pc, "imie_firma", ""):
            nazwa = pc.imie_firma
        elif client.get("nazwa_kontaktu"):
            nazwa = re.sub(
                r"^\d{4}[.\-]\d{2}[.\-]\d{2}\s+Klient\s+", "", client["nazwa_kontaktu"], flags=re.I,
            ).strip()[:120]

        ship = {
            "data_zamowienia": order.get("data_zamowienia", ""),
            "shipment_id": shipment_id,
            "order_id": oid,
            "klient_id": kid,
            "telefon_kontaktowy": client.get("telefon", ""),
            "email_powiadomien": client.get("email", ""),
            "nazwa_odbiorcy": nazwa,
            "osoba_kontaktowa": nazwa,
            "firma": parsed.get("firma", ""),
            "ulica": parsed.get("ulica", ""),
            "nr_domu": parsed.get("nr_domu", ""),
            "nr_lokalu": parsed.get("nr_lokalu", ""),
            "kod_pocztowy": parsed.get("kod_pocztowy", ""),
            "miejscowosc": parsed.get("miejscowosc", "") or (pc.miasto if pc else ""),
            "kraj": parsed.get("kraj", "PL"),
            "adres_surowy": adres_surowy,
            "zrodlo_adresu": log.get("zrodlo_adresu", ""),
            "pozycje_tekst": order.get("pozycje_tekst", ""),
            "produkt_glowny": order.get("produkt_glowny", ""),
            "ilosc_laczna": ilosc,
            "kategoria_wysylki": kategoria,
            "liczba_paczek": 0,
            "status_wysylki": "",
            "status_sprawdzenia": "",
            "uwagi": order.get("uwagi", ""),
        }

        order_packages = build_packages_for_shipment(shipment_id, order, items_by_order[oid], kategoria, klucz_row)
        ship["liczba_paczek"] = len(order_packages)

        missing, status_wys, status_spr = validate_shipment(ship, order_packages, klucz_row, pickup_hint)
        ship["status_wysylki"] = status_wys
        ship["status_sprawdzenia"] = status_spr

        wysylki.append(ship)
        paczki.extend(order_packages)
        category_counter[kategoria] += 1
        status_counter[status_wys] += 1

        if status_wys in ("do_sprawdzenia", "brak_danych", "odbior_osobisty_do_potwierdzenia"):
            for f in missing:
                missing_field_counter[f] += 1
            powod = status_wys
            sugestia = "Uzupełnij adres dostawy w SMS/e-mail lub Google Contacts"
            if status_wys == "odbior_osobisty_do_potwierdzenia":
                sugestia = "Potwierdź odbiór osobisty z klientem"
            elif "kategoria_wysylki" in missing:
                sugestia = "Uzupełnij KLUCZ-WYSYLKOWY.csv lub dopisz kategorię w komunikacji"
            elif "waga_kg" in missing or "gabaryty" in missing:
                sugestia = "Uzupełnij gabaryty i wagę w KLUCZ-WYSYLKOWY.csv"
            review.append({
                "powod": powod,
                "data_zamowienia": ship["data_zamowienia"],
                "shipment_id": shipment_id,
                "order_id": oid,
                "telefon": ship["telefon_kontaktowy"],
                "email": ship["email_powiadomien"],
                "nazwa_kontaktu": client.get("nazwa_kontaktu", ""),
                "adres_surowy": adres_surowy,
                "pozycje_tekst": ship["pozycje_tekst"],
                "kategoria_wysylki": kategoria,
                "brakujace_pola": "; ".join(missing),
                "sugestia": sugestia,
                "uwagi": ship["uwagi"],
            })

        if status_wys == "gotowe_do_nadania" and order_packages:
            p0 = order_packages[0]
            apaczka.append({
                "shipment_id": shipment_id,
                "order_id": oid,
                "nazwa_odbiorcy": ship["nazwa_odbiorcy"],
                "osoba_kontaktowa": ship["osoba_kontaktowa"],
                "firma": ship["firma"],
                "telefon_kontaktowy": ship["telefon_kontaktowy"],
                "email_powiadomien": ship["email_powiadomien"],
                "ulica": ship["ulica"],
                "nr_domu": ship["nr_domu"],
                "nr_lokalu": ship["nr_lokalu"],
                "kod_pocztowy": ship["kod_pocztowy"],
                "miejscowosc": ship["miejscowosc"],
                "kraj": ship["kraj"],
                "kategoria_paczki": p0.get("kategoria_paczki", ""),
                "dlugosc_cm": p0.get("dlugosc_cm", ""),
                "szerokosc_cm": p0.get("szerokosc_cm", ""),
                "wysokosc_cm": p0.get("wysokosc_cm", ""),
                "waga_kg": p0.get("waga_kg", ""),
                "uwagi": ship["uwagi"],
                "status_gotowosci": "gotowe_do_nadania",
            })

    wysylki.sort(key=lambda r: (r.get("data_zamowienia", ""), r.get("shipment_id", "")), reverse=True)
    paczki.sort(key=lambda r: (r.get("data_zamowienia", ""), r.get("shipment_id", ""), r.get("package_id", "")), reverse=True)
    review.sort(key=lambda r: (r.get("powod", ""), r.get("data_zamowienia", "")), reverse=True)

    write_csv_fn(OUT_PRIVATE / "WYSYLKI.csv", WYSYLKI_COLS, wysylki)
    write_csv_fn(OUT_PRIVATE / "PACZKI.csv", PACZKI_COLS, paczki)
    write_csv_fn(OUT_PRIVATE / "WYSYLKI-DO-SPRAWDZENIA.csv", WYSYLKI_REVIEW_COLS, review)
    write_csv_fn(OUT_PRIVATE / "APACZKA-IMPORT-001.csv", APACZKA_IMPORT_COLS, apaczka)

    brak_adres = sum(1 for s in wysylki if not s.get("adres_surowy") and s.get("kategoria_wysylki") != "odbior_osobisty")
    brak_tel = sum(1 for s in wysylki if not s.get("telefon_kontaktowy"))
    brak_email = sum(1 for s in wysylki if not s.get("email_powiadomien"))
    brak_kat = sum(1 for s in wysylki if s.get("kategoria_wysylki") in ("", "do_sprawdzenia"))

    stats = {
        "wysylki_total": len(wysylki),
        "paczki_total": len(paczki),
        "gotowe_do_nadania": status_counter.get("gotowe_do_nadania", 0),
        "do_sprawdzenia": status_counter.get("do_sprawdzenia", 0),
        "odbior_osobisty": status_counter.get("odbior_osobisty_do_potwierdzenia", 0),
        "brak_danych": status_counter.get("brak_danych", 0),
        "apaczka_import": len(apaczka),
        "brak_adresow": brak_adres,
        "brak_telefonow": brak_tel,
        "brak_emaili": brak_email,
        "brak_kategorii": brak_kat,
        "categories": category_counter,
        "missing_fields": missing_field_counter,
    }
    write_wysylki_report(stats)
    return stats


def write_wysylki_report(stats: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    now = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
    cats = stats.get("categories", Counter())
    cat_lines = "\n".join(
        f"| {c} | {cats.get(c, 0)} |" for c in SHIPPING_CATEGORIES if c != "odbior_osobisty"
    )
    missing = stats.get("missing_fields", Counter())
    miss_lines = "\n".join(f"- **{f}**: {n} wysyłek" for f, n in missing.most_common(8)) or "- _brak danych_"

    recs = []
    if stats.get("brak_adresow", 0) > 0:
        recs.append("Uzupełniaj adres dostawy w SMS/e-mail (linia „Dostawa do: …”).")
    if stats.get("brak_kategorii", 0) > 0:
        recs.append("Uzupełnij `02-output-private/KLUCZ-WYSYLKOWY.csv` – gabaryty, waga i sztuki na paczkę/paletę.")
    if missing.get("waga_kg") or missing.get("gabaryty"):
        recs.append("Bez wagi i gabarytów w kluczu wysyłkowym paczki nie przejdą do APACZKA-IMPORT-001.csv.")
    if not recs:
        recs.append("Kontynuuj uzupełnianie klucza wysyłkowego przed integracją API aPaczka.")

    (REPORTS / "WYSYLKI.md").write_text(
        f"# Wysyłki – podsumowanie zbiorcze\n\n"
        f"Wygenerowano: {now}\n\n"
        f"## Statystyki (bez danych osobowych)\n\n"
        f"| Metryka | Liczba |\n|---|---:|\n"
        f"| Wysyłki ogółem | {stats.get('wysylki_total', 0)} |\n"
        f"| Gotowe do nadania | {stats.get('gotowe_do_nadania', 0)} |\n"
        f"| Do sprawdzenia | {stats.get('do_sprawdzenia', 0)} |\n"
        f"| Odbiór osobisty do potwierdzenia | {stats.get('odbior_osobisty', 0)} |\n"
        f"| Brak danych | {stats.get('brak_danych', 0)} |\n"
        f"| W APACZKA-IMPORT-001.csv | {stats.get('apaczka_import', 0)} |\n\n"
        f"## Podział według kategorii\n\n"
        f"| Kategoria | Liczba |\n|---|---:|\n{cat_lines}\n\n"
        f"## Najczęstsze brakujące pola\n\n{miss_lines}\n\n"
        f"## Rekomendowane uzupełnienia\n\n"
        + "\n".join(f"- {r}" for r in recs) + "\n",
        encoding="utf-8",
    )
