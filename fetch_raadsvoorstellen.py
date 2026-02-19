#!/usr/bin/env python3
"""Haal alle raadsvoorstellen op van gemeenteraad.rotterdam.nl en sla ze op als Excel.

Inclusief automatische categorisering op twee dimensies:
- Besluittype (procedureel): wat voor soort besluit is het?
- Beleidsdomein (inhoudelijk): over welk thema gaat het?
"""

import urllib.request
import json
import re
import time
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

BASE_URL = "https://gemeenteraad.rotterdam.nl"
API_URL = f"{BASE_URL}/Reports/GetReportData/4a6cb9e4-2668-4729-852a-ddb3b3ea90d3"
PAGE_SIZE = 100
CONCURRENT_REQUESTS = 5

COLUMNS_PARAM = (
    "columns[0][data]=beleidsveld&columns[0][name]=beleidsveld&columns[0][searchable]=true&"
    "columns[1][data]=externalid&columns[1][name]=externalid&columns[1][searchable]=true&"
    "columns[2][data]=title&columns[2][name]=title&columns[2][searchable]=false&"
    "columns[3][data]=registrationdate&columns[3][name]=registrationdate&columns[3][searchable]=true&"
    "columns[4][data]=portefeuillehouder&columns[4][name]=portefeuillehouder&columns[4][searchable]=true&"
    "columns[5][data]=aanwie&columns[5][name]=aanwie&columns[5][searchable]=false&"
    "columns[6][data]=behandeladvies&columns[6][name]=behandeladvies&columns[6][searchable]=true"
)

EXCEL_COLUMNS = [
    ("BB-nummer", "externalid", 18),
    ("Titel", "title", 80),
    ("Besluittype", "besluittype", 22),
    ("Besluittype detail", "besluittype_detail", 30),
    ("Beleidsdomein", "beleidsdomein", 22),
    ("Beleidsdomein detail", "beleidsdomein_detail", 28),
    ("Beleidsveld (origineel)", "beleidsveld", 22),
    ("Datum ontvangen", "registrationdate", 18),
    ("Portefeuillehouder", "portefeuillehouder", 35),
    ("Aan wie gericht", "aanwie", 20),
    ("Behandeladvies", "behandeladvies", 45),
    ("Hoofddocument", "hoofddocument_naam", 80),
    ("Hoofddocument URL", "hoofddocument_url", 50),
    ("Aantal bijlagen", "aantal_bijlagen", 15),
    ("Bijlagen", "bijlagen_tekst", 100),
    ("Bijlage URLs", "bijlagen_urls", 100),
]


# --- Classificatie ---

def classificeer_besluittype(title):
    """Classificeer het besluittype op basis van de titel.

    Returns (hoofdcategorie, subcategorie).
    """
    t = title.lower()

    # 6. Vervallen
    if t.startswith("vervallen") or t.startswith("(vervallen"):
        return ("6. Overig", "6.1 Vervallen")

    # 1. Ruimtelijk
    if "bestemmingsplan" in t or "omgevingsplan" in t:
        label = "Bestemmingsplan" if "bestemmingsplan" in t else "Omgevingsplan"
        if "zienswijze" in t:
            return ("1. Ruimtelijk", f"1.1 {label} (zienswijze)")
        if "wijziging" in t and "bestemmingsplan" in t:
            return ("1. Ruimtelijk", f"1.1 {label} (wijziging)")
        return ("1. Ruimtelijk", f"1.1 {label} (vaststelling)")
    if "ambitiedocument" in t:
        if "gebiedsambitie" in t:
            return ("1. Ruimtelijk", "1.2 Gebiedsambitiedocument")
        if "projectambitie" in t:
            return ("1. Ruimtelijk", "1.2 Projectambitiedocument")
        return ("1. Ruimtelijk", "1.2 Ambitiedocument")
    if "grondexploitatie" in t:
        if "openen" in t or "open" in t:
            return ("1. Ruimtelijk", "1.3 Grondexploitatie (openen)")
        if "herzie" in t:
            return ("1. Ruimtelijk", "1.3 Grondexploitatie (herzien)")
        if "afsluit" in t:
            return ("1. Ruimtelijk", "1.3 Grondexploitatie (afsluiten)")
        return ("1. Ruimtelijk", "1.3 Grondexploitatie")
    if "welstand" in t:
        return ("1. Ruimtelijk", "1.4 Welstandsnota")
    if "verklaring van geen bedenkingen" in t or "vvgb" in t:
        return ("1. Ruimtelijk", "1.5 Verkl. geen bedenkingen")
    if "erfpacht" in t:
        return ("1. Ruimtelijk", "1.6 Erfpacht")

    # 2. Regelgeving
    if "verordening" in t:
        if "haven" in t:
            return ("2. Regelgeving", "2.1 Havenverordening")
        if "wijziging" in t:
            return ("2. Regelgeving", "2.1 Verordening (wijziging)")
        return ("2. Regelgeving", "2.1 Verordening (vaststelling)")
    if re.search(r'\bnota\b', t):
        return ("2. Regelgeving", "2.2 Nota / Beleidsstuk")
    if "kadernota" in t or "visie" in t or "beleidskader" in t:
        return ("2. Regelgeving", "2.3 Kadernota / Visie")
    if "beleidsregel" in t:
        return ("2. Regelgeving", "2.2 Nota / Beleidsstuk")

    # 3. Financieel
    if "begroting" in t or "begrotingswijziging" in t:
        return ("3. Financieel", "3.1 Begroting")
    if "jaarrekening" in t or "jaarstukken" in t:
        return ("3. Financieel", "3.2 Jaarrekening / Jaarstukken")
    if "jaarverslag" in t:
        return ("3. Financieel", "3.2 Jaarrekening / Jaarstukken")
    if "krediet" in t:
        return ("3. Financieel", "3.4 Krediet")
    if "subsidie" in t:
        return ("3. Financieel", "3.5 Subsidie")
    if any(w in t for w in ["lening", "borgstelling", "garantie"]):
        return ("3. Financieel", "3.6 Lening / Garantie")
    if any(w in t for w in ["belasting", "tarieven", "leges", "retributie"]):
        return ("3. Financieel", "3.3 Belasting / Tarieven")

    # 4. Bestuurlijk
    if "benoeming" in t or "herbenoeming" in t:
        if "rekenkamer" in t:
            return ("4. Bestuurlijk", "4.1 Benoeming (Rekenkamer)")
        if "lid" in t or "voorzitter" in t:
            return ("4. Bestuurlijk", "4.1 Benoeming (lid/voorzitter)")
        return ("4. Bestuurlijk", "4.1 Benoeming / Aanwijzing")
    if "aanwijzing" in t:
        return ("4. Bestuurlijk", "4.1 Benoeming / Aanwijzing")
    if "gemeenschappelijke regeling" in t:
        if "zienswijze" in t:
            return ("4. Bestuurlijk", "4.2 Gem. regeling (zienswijze)")
        if "wijziging" in t:
            return ("4. Bestuurlijk", "4.2 Gem. regeling (wijziging)")
        return ("4. Bestuurlijk", "4.2 Gemeenschappelijke regeling")
    if "zienswijze" in t:
        return ("4. Bestuurlijk", "4.3 Zienswijze")

    # 5. Controle
    if "rekenkamer" in t:
        return ("5. Controle", "5.1 Rekenkamerrapport")
    if "geheimhouding" in t:
        return ("5. Controle", "5.2 Geheimhouding")
    if "decharge" in t:
        return ("5. Controle", "5.3 Decharge / Verantwoording")

    # 3. Financieel — bredere patronen
    if any(w in t for w in ["voorjaarsnota", "najaarsrapportage", "eindejaarsbrief",
                            "financiën", "financien", "financieel"]):
        return ("3. Financieel", "3.1 Begroting")

    # 4. Bestuurlijk — bredere patronen
    if any(w in t for w in ["ontheffing", "ontslag", "woonplaatsvereiste"]):
        return ("4. Bestuurlijk", "4.1 Benoeming / Aanwijzing")
    if "presidium" in t:
        return ("4. Bestuurlijk", "4.3 Organisatie raad")
    if any(w in t for w in ["burgerinitiatief", "initiatiefnotitie",
                            "initiatief notitie", "initiatiefvoorstel"]):
        return ("4. Bestuurlijk", "4.4 Burgerinitiatief")
    if any(w in t for w in ["mandaat", "delegatie", "volmacht"]):
        return ("4. Bestuurlijk", "4.3 Organisatie raad")
    if "bezwaar" in t or "ongegrond" in t:
        return ("4. Bestuurlijk", "4.5 Bezwaarschrift")
    if "afdoening motie" in t or "afdoening toezegging" in t:
        return ("5. Controle", "5.3 Decharge / Verantwoording")
    if "intrekk" in t and "raadsbesluit" in t:
        return ("4. Bestuurlijk", "4.3 Organisatie raad")

    # 1. Ruimtelijk — bredere patronen
    if any(w in t for w in ["voorbereidingsbesluit", "voorkeursrecht",
                            "exploitatieplan", "structuurvisie"]):
        return ("1. Ruimtelijk", "1.1 Bestemmingsplan (vaststelling)")
    if any(w in t for w in ["vastgoed", "verkoop", "aankoop", "aan- en verkoop",
                            "onderhandse verkoop", "pand"]):
        return ("1. Ruimtelijk", "1.7 Vastgoed")
    if "masterplan" in t or "gebiedsplan" in t:
        return ("1. Ruimtelijk", "1.2 Ambitiedocument")

    # 2. Regelgeving — bredere patronen
    if any(w in t for w in ["koers", "agenda", "programma", "strategie", "plan ",
                            "actieplan", "uitvoeringsagenda", "kader ", "beleid"]):
        return ("2. Regelgeving", "2.3 Kadernota / Visie")

    return ("6. Overig", "6.2 Niet geclassificeerd")


def classificeer_beleidsdomein(title, beleidsveld):
    """Classificeer het beleidsdomein op basis van titel en origineel beleidsveld.

    Returns (hoofddomein, subdomein).
    """
    t = title.lower()
    bv = (beleidsveld or "").lower().strip()

    # Probeer eerst op trefwoorden in de titel
    if any(w in t for w in ["bestemmingsplan", "omgevingsplan", "ambitiedocument",
                            "grondexploitatie", "welstand", "stedenbouw",
                            "gebiedsontwikkeling", "bouwplan"]):
        return ("A. Ruimte & Wonen", "A.1 Stedelijke ontwikkeling")
    if any(w in t for w in ["woning", "huur", "woonvisie", "huisvesting",
                            "woningbouw", "flexwonen", "woonbeleid"]):
        return ("A. Ruimte & Wonen", "A.2 Woonbeleid")
    if any(w in t for w in ["groen", "bomen", "park", "tuin", "buitenruimte",
                            "begraafplaats"]):
        return ("A. Ruimte & Wonen", "A.3 Buitenruimte / Groen")
    if any(w in t for w in ["monument", "erfgoed", "beschermd stadsgezicht"]):
        return ("A. Ruimte & Wonen", "A.4 Monumenten / Erfgoed")
    if any(w in t for w in ["water", "riool", "riolering", "waterschap"]):
        return ("D. Duurzaamheid", "D.2 Water / Klimaatadaptatie")

    if any(w in t for w in ["haven", "havengebied", "havenverordening",
                            "havenbedrijf", "havenvisie"]):
        return ("B. Economie & Haven", "B.1 Haven")
    if any(w in t for w in ["economie", "bedrijven", "vestigingsklimaat",
                            "horeca", "markt", "nachtleven", "winkel"]):
        return ("B. Economie & Haven", "B.2 Economisch beleid")
    if any(w in t for w in ["werk", "inkomen", "uitkering", "participatiewet",
                            "bijstand", "arbeidsmarkt"]):
        return ("B. Economie & Haven", "B.3 Werk & Inkomen")

    if any(w in t for w in ["mobiliteit", "verkeer", "weg", "fiets",
                            "verkeers"]):
        return ("C. Mobiliteit", "C.1 Verkeer")
    if any(w in t for w in ["openbaar vervoer", "metro", "tram", "bus", "ret"]):
        return ("C. Mobiliteit", "C.2 Openbaar vervoer")
    if any(w in t for w in ["parkeer", "parkeren", "parkeergarage"]):
        return ("C. Mobiliteit", "C.3 Parkeren")

    if any(w in t for w in ["klimaat", "energie", "warmte", "wind", "zon",
                            "duurzaam", "co2", "circulair", "milieu", "lucht"]):
        return ("D. Duurzaamheid", "D.1 Energie / Klimaat")

    if any(w in t for w in ["onderwijs", "school", "boor", "leerling",
                            "leraar", "kinderopvang"]):
        return ("E. Sociaal", "E.1 Onderwijs")
    if any(w in t for w in ["zorg", "jeugd", "wmo", "ggz", "beschermd wonen",
                            "maatschappelijke ondersteuning"]):
        return ("E. Sociaal", "E.2 Zorg / Jeugd")
    if any(w in t for w in ["cultuur", "museum", "theater", "bibliotheek",
                            "kunst", "festival", "cultuurhaven"]):
        return ("E. Sociaal", "E.3 Cultuur")
    if any(w in t for w in ["sport", "stadion", "zwembad", "sporthal",
                            "voetbal", "feyenoord", "excelsior"]):
        return ("E. Sociaal", "E.4 Sport")
    if any(w in t for w in ["armoede", "schuld", "minima", "rotterdam pas"]):
        return ("E. Sociaal", "E.5 Welzijn / Armoede")
    if any(w in t for w in ["wijk", "gebiedscommissie", "wijkraad",
                            "samenleven", "integratie", "discriminatie"]):
        return ("E. Sociaal", "E.6 Samenleven / Wijken")

    if any(w in t for w in ["veiligheid", "camera", "politie", "handhaving",
                            "toezicht", "boa", "ondermijning"]):
        return ("F. Veiligheid", "F.1 Openbare orde / Handhaving")

    # Fallback: gebruik origineel beleidsveld
    bv_mapping = {
        "bouwen en wonen": ("A. Ruimte & Wonen", "A.1 Stedelijke ontwikkeling"),
        "buitenruimte": ("A. Ruimte & Wonen", "A.3 Buitenruimte / Groen"),
        "economie": ("B. Economie & Haven", "B.2 Economisch beleid"),
        "haven": ("B. Economie & Haven", "B.1 Haven"),
        "mobiliteit": ("C. Mobiliteit", "C.1 Verkeer"),
        "duurzaam": ("D. Duurzaamheid", "D.1 Energie / Klimaat"),
        "onderwijs": ("E. Sociaal", "E.1 Onderwijs"),
        "zorg": ("E. Sociaal", "E.2 Zorg / Jeugd"),
        "cultuur": ("E. Sociaal", "E.3 Cultuur"),
        "sport": ("E. Sociaal", "E.4 Sport"),
        "armoedebestrijding": ("E. Sociaal", "E.5 Welzijn / Armoede"),
        "welzijn": ("E. Sociaal", "E.5 Welzijn / Armoede"),
        "samenleven": ("E. Sociaal", "E.6 Samenleven / Wijken"),
        "wijken": ("E. Sociaal", "E.6 Samenleven / Wijken"),
        "jeugd": ("E. Sociaal", "E.2 Zorg / Jeugd"),
        "werk en inkomen": ("B. Economie & Haven", "B.3 Werk & Inkomen"),
        "veiligheid": ("F. Veiligheid", "F.1 Openbare orde / Handhaving"),
        "bestuur": ("G. Bestuur & Financiën", "G.3 Raadsorganisatie"),
        "organisatie": ("G. Bestuur & Financiën", "G.2 Gemeentelijke organisatie"),
        "projecten": ("A. Ruimte & Wonen", "A.1 Stedelijke ontwikkeling"),
        "presidium": ("G. Bestuur & Financiën", "G.3 Raadsorganisatie"),
        "cor": ("G. Bestuur & Financiën", "G.4 Interbestuurlijk"),
        "gebieden": ("E. Sociaal", "E.6 Samenleven / Wijken"),
    }
    # Normaliseer financiën varianten
    if bv in ("financien-inactief", "financïen", "financien", "financiën"):
        return ("G. Bestuur & Financiën", "G.1 Gemeentefinanciën")

    if bv in bv_mapping:
        return bv_mapping[bv]

    return ("G. Bestuur & Financiën", "G.1 Gemeentefinanciën")


def classificeer_record(record):
    """Voeg classificatievelden toe aan een record."""
    title = record.get("title") or ""
    beleidsveld = record.get("beleidsveld") or ""

    bt_hoofd, bt_detail = classificeer_besluittype(title)
    bd_hoofd, bd_detail = classificeer_beleidsdomein(title, beleidsveld)

    record["besluittype"] = bt_hoofd
    record["besluittype_detail"] = bt_detail
    record["beleidsdomein"] = bd_hoofd
    record["beleidsdomein_detail"] = bd_detail

    return record


def http_get_with_retry(url, max_retries=4, timeout=30, data=None, headers=None):
    """HTTP request met exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
            else:
                raise


def fetch_page(draw, start, length):
    params = f"draw={draw}&start={start}&length={length}&order[0][column]=3&order[0][dir]=desc&search[value]=&search[regex]=false&{COLUMNS_PARAM}"
    body = http_get_with_retry(
        API_URL,
        data=params.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{BASE_URL}/Reports/Details/4a6cb9e4-2668-4729-852a-ddb3b3ea90d3",
        },
    )
    return json.loads(body)


def fetch_all_records():
    all_records = []
    start = 0
    draw = 1
    total = None

    while True:
        result = fetch_page(draw, start, PAGE_SIZE)
        if total is None:
            total = result["recordsTotal"]
            print(f"Totaal aantal raadsvoorstellen: {total}")

        records = result["data"]
        all_records.extend(records)
        print(f"  Lijst opgehaald: {len(all_records)}/{total}")

        if len(all_records) >= total or len(records) == 0:
            break

        start += PAGE_SIZE
        draw += 1

    return all_records


def parse_documents(html, section_label):
    """Parse documenten uit een dt/dd sectie van de HTML."""
    documents = []
    pattern = (
        r'<dt[^>]*>\s*' + re.escape(section_label) + r'\s*</dt>\s*<dd[^>]*>(.*?)</dd>'
    )
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return documents

    content = match.group(1)
    for doc_match in re.finditer(
        r'href="([^"]+)"[^>]*data-document-id="([^"]+)"[^>]*>\s*'
        r'<span class="icon\s+(\w+)"[^>]*>[^<]*</span>\s*'
        r'(.*?)\s*<span class="badge[^"]*">(.*?)</span>',
        content,
        re.DOTALL,
    ):
        url, doc_id, file_type, name, size = doc_match.groups()
        name = re.sub(r"<[^>]+>", "", name).strip()
        name = re.sub(r"\s+", " ", name)
        documents.append({
            "naam": name,
            "url": BASE_URL + url,
            "document_id": doc_id,
            "type": file_type,
            "grootte": size.strip(),
        })

    return documents


def fetch_item_documents(record):
    """Haal de detailpagina op en parse de documenten."""
    row_id = record["DT_RowId"]
    url = f"{BASE_URL}/Reports/Item/{row_id}"

    for attempt in range(4):
        try:
            html = http_get_with_retry(url)

            hoofddocumenten = parse_documents(html, "Hoofddocument")
            bijlagen = parse_documents(html, "Bijlage(n)")

            if hoofddocumenten:
                record["hoofddocument_naam"] = hoofddocumenten[0]["naam"]
                record["hoofddocument_url"] = hoofddocumenten[0]["url"]
            else:
                record["hoofddocument_naam"] = ""
                record["hoofddocument_url"] = ""

            record["aantal_bijlagen"] = len(bijlagen)
            record["bijlagen_tekst"] = "\n".join(
                f"{b['naam']} ({b['grootte']})" for b in bijlagen
            )
            record["bijlagen_urls"] = "\n".join(
                b["url"] for b in bijlagen
            )
            record["bijlagen"] = bijlagen

            return record

        except Exception as e:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
            else:
                print(f"  FOUT bij {row_id}: {e}", file=sys.stderr)
                record["hoofddocument_naam"] = f"FOUT: {e}"
                record["hoofddocument_url"] = ""
                record["aantal_bijlagen"] = ""
                record["bijlagen_tekst"] = ""
                record["bijlagen"] = []
                return record


def fetch_all_documents(records):
    """Haal documenten op voor alle records met parallelle requests."""
    total = len(records)
    completed = 0

    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        futures = {
            executor.submit(fetch_item_documents, record): record
            for record in records
        }

        for future in as_completed(futures):
            completed += 1
            if completed % 50 == 0 or completed == total:
                print(f"  Documenten opgehaald: {completed}/{total}")

    return records


def make_styles():
    return {
        "header_font": Font(name="Calibri", bold=True, color="FFFFFF", size=11),
        "header_fill": PatternFill(start_color="00674A", end_color="00674A", fill_type="solid"),
        "header_fill_2": PatternFill(start_color="1B5E20", end_color="1B5E20", fill_type="solid"),
        "header_alignment": Alignment(horizontal="center", vertical="center", wrap_text=True),
        "cell_alignment": Alignment(vertical="top", wrap_text=True),
        "url_font": Font(name="Calibri", color="0563C1", underline="single", size=10),
        "bold_font": Font(name="Calibri", bold=True),
        "number_alignment": Alignment(horizontal="right", vertical="top"),
        "thin_border": Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        ),
    }


def write_sheet(ws, columns, records, styles):
    """Schrijf data naar een werkblad met headers, data, freeze en filter."""
    for col_idx, (header, _, width) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = styles["header_font"]
        cell.fill = styles["header_fill"]
        cell.alignment = styles["header_alignment"]
        cell.border = styles["thin_border"]
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    for row_idx, record in enumerate(records, 2):
        for col_idx, (_, key, _) in enumerate(columns, 1):
            value = record.get(key, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = styles["cell_alignment"]
            cell.border = styles["thin_border"]

            if key == "hoofddocument_url" and value:
                cell.hyperlink = value
                cell.font = styles["url_font"]
            elif key == "bijlagen_urls" and value:
                cell.font = styles["url_font"]

    ws.freeze_panes = "A2"
    last_col = get_column_letter(len(columns))
    ws.auto_filter.ref = f"A1:{last_col}{len(records) + 1}"


def write_summary_sheet(ws, title_label, key, records, styles):
    """Schrijf een samenvattingsblad met tellingen per categorie."""
    # Tel per waarde
    counts = Counter()
    for r in records:
        val = r.get(key) or "(onbekend)"
        counts[val] += 1

    headers = [
        (title_label, 40),
        ("Aantal", 12),
        ("% van totaal", 12),
    ]
    for col_idx, (header, width) in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = styles["header_font"]
        cell.fill = styles["header_fill"]
        cell.alignment = styles["header_alignment"]
        cell.border = styles["thin_border"]
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    total = len(records)
    for row_idx, (val, count) in enumerate(sorted(counts.items()), 2):
        pct = round(count / total * 100, 1) if total else 0
        for col_idx, cell_val in enumerate([val, count, f"{pct}%"], 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=cell_val)
            cell.alignment = styles["cell_alignment"]
            cell.border = styles["thin_border"]

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:C{len(counts) + 1}"


def write_cross_table(ws, records, styles):
    """Schrijf kruistabel Besluittype x Beleidsdomein."""
    # Verzamel unieke waarden
    besluittypes = sorted(set(r.get("besluittype", "") for r in records))
    beleidsdomeinen = sorted(set(r.get("beleidsdomein", "") for r in records))

    # Tel combinaties
    cross = Counter()
    bt_totals = Counter()
    bd_totals = Counter()
    for r in records:
        bt = r.get("besluittype", "")
        bd = r.get("beleidsdomein", "")
        cross[(bt, bd)] += 1
        bt_totals[bt] += 1
        bd_totals[bd] += 1

    # Header rij: lege cel + beleidsdomeinen + Totaal
    ws.cell(row=1, column=1, value="Besluittype \\ Beleidsdomein")
    ws.cell(row=1, column=1).font = styles["header_font"]
    ws.cell(row=1, column=1).fill = styles["header_fill"]
    ws.cell(row=1, column=1).border = styles["thin_border"]
    ws.column_dimensions["A"].width = 22

    for col_idx, bd in enumerate(beleidsdomeinen, 2):
        cell = ws.cell(row=1, column=col_idx, value=bd)
        cell.font = styles["header_font"]
        cell.fill = styles["header_fill"]
        cell.alignment = styles["header_alignment"]
        cell.border = styles["thin_border"]
        ws.column_dimensions[get_column_letter(col_idx)].width = 18

    totaal_col = len(beleidsdomeinen) + 2
    cell = ws.cell(row=1, column=totaal_col, value="Totaal")
    cell.font = styles["header_font"]
    cell.fill = styles["header_fill_2"]
    cell.alignment = styles["header_alignment"]
    cell.border = styles["thin_border"]
    ws.column_dimensions[get_column_letter(totaal_col)].width = 10

    # Data rijen
    for row_idx, bt in enumerate(besluittypes, 2):
        cell = ws.cell(row=row_idx, column=1, value=bt)
        cell.font = styles["bold_font"]
        cell.border = styles["thin_border"]

        for col_idx, bd in enumerate(beleidsdomeinen, 2):
            count = cross.get((bt, bd), 0)
            cell = ws.cell(row=row_idx, column=col_idx, value=count if count else "")
            cell.alignment = styles["number_alignment"]
            cell.border = styles["thin_border"]

        # Rij-totaal
        cell = ws.cell(row=row_idx, column=totaal_col, value=bt_totals[bt])
        cell.font = styles["bold_font"]
        cell.alignment = styles["number_alignment"]
        cell.border = styles["thin_border"]

    # Totaal rij
    totaal_row = len(besluittypes) + 2
    cell = ws.cell(row=totaal_row, column=1, value="Totaal")
    cell.font = styles["header_font"]
    cell.fill = styles["header_fill_2"]
    cell.border = styles["thin_border"]

    for col_idx, bd in enumerate(beleidsdomeinen, 2):
        cell = ws.cell(row=totaal_row, column=col_idx, value=bd_totals[bd])
        cell.font = Font(name="Calibri", bold=True, color="FFFFFF")
        cell.fill = styles["header_fill_2"]
        cell.alignment = styles["number_alignment"]
        cell.border = styles["thin_border"]

    cell = ws.cell(row=totaal_row, column=totaal_col, value=len(records))
    cell.font = Font(name="Calibri", bold=True, color="FFFFFF")
    cell.fill = styles["header_fill_2"]
    cell.alignment = styles["number_alignment"]
    cell.border = styles["thin_border"]

    ws.freeze_panes = "B2"


def create_excel(records, filename):
    wb = Workbook()
    styles = make_styles()

    # --- Blad 1: Alle raadsvoorstellen ---
    ws1 = wb.active
    ws1.title = "Raadsvoorstellen"
    write_sheet(ws1, EXCEL_COLUMNS, records, styles)

    # --- Blad 2: Per besluittype ---
    ws2 = wb.create_sheet("Per besluittype")
    write_summary_sheet(ws2, "Besluittype", "besluittype", records, styles)

    # --- Blad 3: Per besluittype (detail) ---
    ws3 = wb.create_sheet("Per besluittype (detail)")
    write_summary_sheet(ws3, "Besluittype detail", "besluittype_detail", records, styles)

    # --- Blad 4: Per beleidsdomein ---
    ws4 = wb.create_sheet("Per beleidsdomein")
    write_summary_sheet(ws4, "Beleidsdomein", "beleidsdomein", records, styles)

    # --- Blad 5: Per beleidsdomein (detail) ---
    ws5 = wb.create_sheet("Per beleidsdomein (detail)")
    write_summary_sheet(ws5, "Beleidsdomein detail", "beleidsdomein_detail", records, styles)

    # --- Blad 6: Kruistabel ---
    ws6 = wb.create_sheet("Kruistabel")
    write_cross_table(ws6, records, styles)

    # --- Blad 7: Per portefeuillehouder ---
    ws7 = wb.create_sheet("Per portefeuillehouder")
    write_summary_sheet(ws7, "Portefeuillehouder", "portefeuillehouder", records, styles)

    wb.save(filename)

    # Statistieken
    bt_counts = Counter(r.get("besluittype", "") for r in records)
    bd_counts = Counter(r.get("beleidsdomein", "") for r in records)
    niet_gecl = sum(1 for r in records if r.get("besluittype_detail", "").endswith("Niet geclassificeerd"))

    print(f"\nExcel bestand opgeslagen: {filename}")
    print(f"  Blad 'Raadsvoorstellen': {len(records)} rijen")
    print(f"  Blad 'Kruistabel': {len(bt_counts)} besluittypes x {len(bd_counts)} beleidsdomeinen")
    print(f"  Automatisch geclassificeerd: {len(records) - niet_gecl}/{len(records)}"
          f" ({round((len(records) - niet_gecl) / len(records) * 100)}%)")
    print(f"  Niet geclassificeerd (besluittype): {niet_gecl}")


if __name__ == "__main__":
    print("Stap 1: Raadsvoorstellen ophalen via API...")
    records = fetch_all_records()

    print(f"\nStap 2: Documenten ophalen van {len(records)} detailpagina's...")
    fetch_all_documents(records)

    # Statistieken
    fouten = sum(1 for r in records if not isinstance(r.get("aantal_bijlagen"), int))
    met_bijlagen = sum(1 for r in records if isinstance(r.get("aantal_bijlagen"), int) and r["aantal_bijlagen"] > 0)
    totaal_bijlagen = sum(r.get("aantal_bijlagen", 0) for r in records if isinstance(r.get("aantal_bijlagen"), int))
    if fouten:
        print(f"  {fouten} raadsvoorstellen konden niet opgehaald worden (403/fout)")
    print(f"\n  {met_bijlagen} raadsvoorstellen hebben bijlagen")
    print(f"  {totaal_bijlagen} bijlagen in totaal")

    print("\nStap 3: Classificeren...")
    for r in records:
        classificeer_record(r)

    print("\nStap 4: Excel genereren...")
    create_excel(records, "raadsvoorstellen.xlsx")
