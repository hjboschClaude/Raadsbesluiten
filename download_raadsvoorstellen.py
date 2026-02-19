#!/usr/bin/env python3
"""Download alle raadsvoorstel-documenten, extraheer inhoud en classificeer.

Downloadt de hoofddocumenten (PDFs) van alle raadsvoorstellen naar de map
'raadsvoorstellen/', extraheert de tekst, parseert het "Gevraagd besluit"
en classificeert op basis van de documentinhoud.

Gebruik:
    python3 download_raadsvoorstellen.py              # Volledige run
    python3 download_raadsvoorstellen.py --from-cache  # Gebruik cache
    python3 download_raadsvoorstellen.py --skip-download  # Alleen Excel
"""

import urllib.request
import json
import re
import os
import io
import time
import sys
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from pypdf import PdfReader
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from fetch_raadsvoorstellen import (
    BASE_URL, API_URL, PAGE_SIZE, COLUMNS_PARAM,
    http_get_with_retry, fetch_page, fetch_all_records,
    parse_documents,
    classificeer_besluittype, classificeer_beleidsdomein,
    make_styles, write_sheet, write_summary_sheet, write_cross_table,
)

PDF_DIR = "raadsvoorstellen"
CACHE_FILE = "raadsvoorstellen_cache.json"
CONCURRENT_DOWNLOADS = 3


# --- Detail pagina + document-ID ophalen ---

def fetch_item_detail(record):
    """Haal detailpagina op en extraheer document-ID en metadata."""
    row_id = record["DT_RowId"]
    url = f"{BASE_URL}/Reports/Item/{row_id}"
    try:
        html = http_get_with_retry(url)
        hoofddocs = parse_documents(html, "Hoofddocument")
        if hoofddocs:
            record["doc_id"] = hoofddocs[0]["document_id"]
            record["hoofddocument_naam"] = hoofddocs[0]["naam"]
            record["hoofddocument_url"] = hoofddocs[0]["url"]
        else:
            record["doc_id"] = ""
            record["hoofddocument_naam"] = ""
            record["hoofddocument_url"] = ""

        bijlagen = parse_documents(html, "Bijlage(n)")
        record["aantal_bijlagen"] = len(bijlagen)
        record["detail_ok"] = True
    except Exception as e:
        print(f"  FOUT detail {row_id}: {e}", file=sys.stderr)
        record["doc_id"] = ""
        record["hoofddocument_naam"] = ""
        record["hoofddocument_url"] = ""
        record["aantal_bijlagen"] = 0
        record["detail_ok"] = False
    return record


def fetch_all_details(records):
    """Haal detailpagina's op voor alle records."""
    total = len(records)
    completed = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_item_detail, r): r for r in records}
        for future in as_completed(futures):
            completed += 1
            if completed % 50 == 0 or completed == total:
                print(f"  Details opgehaald: {completed}/{total}")
    return records


# --- PDF download ---

def safe_filename(bb, title, max_len=150):
    """Maak een veilige bestandsnaam."""
    naam = f"[{bb}] {title}"
    naam = re.sub(r'[<>:"/\\|?*]', '_', naam)
    naam = re.sub(r'\s+', ' ', naam).strip()
    if len(naam) > max_len:
        naam = naam[:max_len].rstrip()
    return naam + ".pdf"


def download_pdf(record):
    """Download een PDF naar de raadsvoorstellen map."""
    doc_id = record.get("doc_id", "")
    if not doc_id:
        record["pdf_bestand"] = ""
        record["pdf_ok"] = False
        return record

    bb = record.get("externalid", "")
    title = record.get("title", "")
    bestandsnaam = safe_filename(bb, title)
    pad = os.path.join(PDF_DIR, bestandsnaam)

    # Sla over als bestand al bestaat
    if os.path.exists(pad) and os.path.getsize(pad) > 0:
        record["pdf_bestand"] = bestandsnaam
        record["pdf_ok"] = True
        return record

    url = f"{BASE_URL}/Document/View/{doc_id}"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"Referer": f"{BASE_URL}/"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                pdf_bytes = resp.read()
            with open(pad, "wb") as f:
                f.write(pdf_bytes)
            record["pdf_bestand"] = bestandsnaam
            record["pdf_ok"] = True
            return record
        except Exception as e:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1))
            else:
                print(f"  FOUT download {bb}: {e}", file=sys.stderr)
                record["pdf_bestand"] = ""
                record["pdf_ok"] = False
    return record


def download_all_pdfs(records):
    """Download alle PDFs parallel."""
    met_doc = [r for r in records if r.get("doc_id")]
    total = len(met_doc)
    print(f"  {total} documenten te downloaden...")

    # Check hoeveel al bestaan
    al_aanwezig = sum(1 for r in met_doc
                      if os.path.exists(os.path.join(PDF_DIR, safe_filename(
                          r.get("externalid", ""), r.get("title", "")))))
    if al_aanwezig:
        print(f"  {al_aanwezig} al gedownload, {total - al_aanwezig} nieuw")

    completed = 0
    with ThreadPoolExecutor(max_workers=CONCURRENT_DOWNLOADS) as executor:
        futures = {executor.submit(download_pdf, r): r for r in met_doc}
        for future in as_completed(futures):
            completed += 1
            if completed % 50 == 0 or completed == total:
                print(f"  Downloads: {completed}/{total}")

    # Markeer records zonder doc_id
    for r in records:
        if not r.get("doc_id"):
            r["pdf_bestand"] = ""
            r["pdf_ok"] = False

    return records


# --- Tekst extractie en sectie-parsing ---

def extraheer_pdf_tekst(pdf_pad):
    """Extraheer volledige tekst uit een PDF bestand."""
    try:
        reader = PdfReader(pdf_pad)
        paginas = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                paginas.append(text)
        return "\n\n".join(paginas), len(reader.pages)
    except Exception:
        return "", 0


def parse_gevraagd_besluit(tekst):
    """Extraheer 'Gevraagd besluit' sectie uit de PDF-tekst."""
    # Zoek varianten van "Gevraagd besluit"
    pattern = r'(?:Gevraagd[e]?\s+besluit[:\s]*)(.*?)(?:Waarom\s+dit\s+voorstel|Toelichting\b|Aan\s+de\s+gemeenteraad|Relatie\s+met\s+het\s+coalitie|$)'
    match = re.search(pattern, tekst, re.DOTALL | re.IGNORECASE)
    if match:
        besluit = match.group(1).strip()
        # Beperk tot max 2000 tekens (sommige zijn zeer lang)
        if len(besluit) > 2000:
            besluit = besluit[:2000] + "..."
        return besluit
    return ""


def parse_waarom(tekst):
    """Extraheer 'Waarom dit voorstel' sectie."""
    pattern = r'(?:Waarom\s+dit\s+voorstel[?/\s]*(?:Waarom\s+nu\s+voorgelegd[?]?\s*)?)(.*?)(?:Relatie\s+met\s+het\s+coalitie|Toelichting\b|Aan\s+de\s+gemeenteraad|$)'
    match = re.search(pattern, tekst, re.DOTALL | re.IGNORECASE)
    if match:
        waarom = match.group(1).strip()
        if len(waarom) > 1500:
            waarom = waarom[:1500] + "..."
        return waarom
    return ""


def parse_cluster(tekst):
    """Extraheer Cluster en Portefeuille uit de PDF-tekst."""
    cluster = ""
    portefeuille = ""

    m = re.search(r'Cluster:\s*(.+?)(?:\n|$)', tekst)
    if m:
        cluster = m.group(1).strip()

    m = re.search(r'Portefeuille:\s*(.+?)(?:\n|$)', tekst)
    if m:
        portefeuille = m.group(1).strip()

    return cluster, portefeuille


def extraheer_alle_teksten(records):
    """Extraheer tekst uit alle gedownloade PDFs."""
    total = sum(1 for r in records if r.get("pdf_ok"))
    completed = 0

    for r in records:
        if not r.get("pdf_ok") or not r.get("pdf_bestand"):
            r["pdf_tekst"] = ""
            r["gevraagd_besluit"] = ""
            r["waarom_voorstel"] = ""
            r["pdf_cluster"] = ""
            r["pdf_portefeuille"] = ""
            r["pdf_paginas"] = 0
            continue

        pad = os.path.join(PDF_DIR, r["pdf_bestand"])
        tekst, paginas = extraheer_pdf_tekst(pad)

        r["pdf_tekst"] = tekst
        r["gevraagd_besluit"] = parse_gevraagd_besluit(tekst)
        r["waarom_voorstel"] = parse_waarom(tekst)
        cluster, portefeuille = parse_cluster(tekst)
        r["pdf_cluster"] = cluster
        r["pdf_portefeuille"] = portefeuille
        r["pdf_paginas"] = paginas

        completed += 1
        if completed % 100 == 0 or completed == total:
            print(f"  Tekst geëxtraheerd: {completed}/{total}")

    return records


# --- Inhoud-gebaseerde classificatie ---

def classificeer_besluittype_inhoud(gevraagd_besluit, titel):
    """Classificeer besluittype op basis van 'Gevraagd besluit' tekst.

    Returns (hoofdcategorie, subcategorie) of None als niet bepaald.
    """
    if not gevraagd_besluit:
        return None

    gb = gevraagd_besluit.lower()

    # Bestemmingsplan / omgevingsplan
    if "bestemmingsplan" in gb or "omgevingsplan" in gb:
        if "zienswijze" in gb:
            return ("1. Ruimtelijk", "1.1 Bestemmingsplan (zienswijze)")
        return ("1. Ruimtelijk", "1.1 Bestemmingsplan (vaststelling)")

    # Grondexploitatie
    if "grondexploitatie" in gb:
        if "openen" in gb or "open te stellen" in gb:
            return ("1. Ruimtelijk", "1.3 Grondexploitatie (openen)")
        if "herzie" in gb:
            return ("1. Ruimtelijk", "1.3 Grondexploitatie (herzien)")
        return ("1. Ruimtelijk", "1.3 Grondexploitatie")

    # Verordening
    if "verordening" in gb:
        if "wijzig" in gb:
            return ("2. Regelgeving", "2.1 Verordening (wijziging)")
        return ("2. Regelgeving", "2.1 Verordening (vaststelling)")

    # Financieel
    if any(w in gb for w in ["krediet", "budget beschikbaar", "middelen beschikbaar"]):
        return ("3. Financieel", "3.4 Krediet")
    if "begroting" in gb:
        return ("3. Financieel", "3.1 Begroting")
    if "jaarrekening" in gb or "jaarstukken" in gb:
        return ("3. Financieel", "3.2 Jaarrekening / Jaarstukken")
    if "subsidie" in gb:
        return ("3. Financieel", "3.5 Subsidie")
    if any(w in gb for w in ["belasting", "tarieven", "leges"]):
        return ("3. Financieel", "3.3 Belasting / Tarieven")

    # Bestuurlijk
    if any(w in gb for w in ["te benoemen", "benoemen", "herbenoemen"]):
        return ("4. Bestuurlijk", "4.1 Benoeming / Aanwijzing")
    if "zienswijze" in gb and "gemeenschappelijke regeling" in gb:
        return ("4. Bestuurlijk", "4.2 Gem. regeling (zienswijze)")
    if "gemeenschappelijke regeling" in gb:
        return ("4. Bestuurlijk", "4.2 Gemeenschappelijke regeling")
    if "zienswijze" in gb:
        return ("4. Bestuurlijk", "4.3 Zienswijze")

    # Controle
    if "geheimhouding" in gb:
        return ("5. Controle", "5.2 Geheimhouding")

    # Welstand
    if "welstand" in gb:
        return ("1. Ruimtelijk", "1.4 Welstandsnota")

    # Ambitiedocument
    if "ambitiedocument" in gb:
        return ("1. Ruimtelijk", "1.2 Ambitiedocument")

    return None


def classificeer_beleidsdomein_inhoud(tekst, cluster, titel, beleidsveld):
    """Classificeer beleidsdomein op basis van volledige PDF-tekst en cluster.

    Returns (hoofddomein, subdomein) of None.
    """
    # Gebruik cluster-veld als sterk signaal
    cl = (cluster or "").lower()
    cluster_mapping = {
        "stadsontwikkeling": ("A. Ruimte & Wonen", "A.1 Stedelijke ontwikkeling"),
        "stadsbeheer": ("A. Ruimte & Wonen", "A.3 Buitenruimte / Groen"),
        "maatschappelijke ontwikkeling": ("E. Sociaal", "E.2 Zorg / Jeugd"),
        "werk en inkomen": ("B. Economie & Haven", "B.3 Werk & Inkomen"),
        "dienstverlening": ("G. Bestuur & Financiën", "G.2 Gemeentelijke organisatie"),
        "bestuurs- en concernondersteuning": ("G. Bestuur & Financiën", "G.2 Gemeentelijke organisatie"),
    }
    for key, val in cluster_mapping.items():
        if key in cl:
            return val

    if not tekst:
        return None

    t = tekst[:5000].lower()  # Analyseer eerste 5000 tekens

    # Zoek domein-specifieke trefwoorden in de inhoud
    domein_patterns = [
        (["bestemmingsplan", "omgevingsplan", "grondexploitatie", "welstand",
          "stedenbouwkundig", "gebiedsontwikkeling", "bouwplan", "plangebied"],
         ("A. Ruimte & Wonen", "A.1 Stedelijke ontwikkeling")),
        (["woning", "huurwoning", "woonvisie", "huisvesting", "woningbouw",
          "flexwonen", "sociale huur", "koopwoning"],
         ("A. Ruimte & Wonen", "A.2 Woonbeleid")),
        (["groen", "bomen", "buitenruimte", "openbare ruimte", "begraafplaats",
          "speeltuin", "stadspark"],
         ("A. Ruimte & Wonen", "A.3 Buitenruimte / Groen")),
        (["monument", "erfgoed", "beschermd stadsgezicht", "restauratie",
          "rijksmonument"],
         ("A. Ruimte & Wonen", "A.4 Monumenten / Erfgoed")),
        (["haven", "havengebied", "havenbedrijf", "havenmeester", "scheepvaart"],
         ("B. Economie & Haven", "B.1 Haven")),
        (["economie", "ondernemers", "bedrijventerrein", "horeca", "winkelgebied",
          "economisch", "investering", "vestigingsklimaat", "mkb"],
         ("B. Economie & Haven", "B.2 Economisch beleid")),
        (["mobiliteit", "verkeer", "fiets", "voetganger", "weginfrastructuur",
          "bereikbaarheid", "verkeersplan"],
         ("C. Mobiliteit", "C.1 Verkeer")),
        (["parkeer", "parkeergarage", "parkeernorm", "autoparkeren"],
         ("C. Mobiliteit", "C.3 Parkeren")),
        (["klimaat", "energie", "warmte", "duurzaam", "co2", "circulair",
          "energietransitie", "windenergie", "zonnepanelen"],
         ("D. Duurzaamheid", "D.1 Energie / Klimaat")),
        (["water", "riool", "riolering", "wateroverlast", "waterkwaliteit",
          "klimaatadaptatie"],
         ("D. Duurzaamheid", "D.2 Water / Klimaatadaptatie")),
        (["onderwijs", "school", "boor", "leerling", "leraar", "kinderopvang",
          "onderwijshuisvesting"],
         ("E. Sociaal", "E.1 Onderwijs")),
        (["zorg", "jeugdhulp", "wmo", "ggz", "beschermd wonen",
          "maatschappelijke ondersteuning", "jeugdzorg"],
         ("E. Sociaal", "E.2 Zorg / Jeugd")),
        (["cultuur", "museum", "theater", "bibliotheek", "kunst", "festival",
          "cultureel", "kunstenaar"],
         ("E. Sociaal", "E.3 Cultuur")),
        (["sport", "stadion", "zwembad", "sporthal", "voetbal", "sportclub",
          "sportaccommodatie"],
         ("E. Sociaal", "E.4 Sport")),
        (["armoede", "schuld", "minima", "rotterdampas", "armoedebeleid",
          "schuldhulp"],
         ("E. Sociaal", "E.5 Welzijn / Armoede")),
        (["wijk", "wijkraad", "samenleven", "integratie", "buurt",
          "gebiedscommissie", "bewonersparticipatie"],
         ("E. Sociaal", "E.6 Samenleven / Wijken")),
        (["veiligheid", "camera", "politie", "handhaving", "toezicht",
          "ondermijning", "criminaliteit"],
         ("F. Veiligheid", "F.1 Openbare orde / Handhaving")),
    ]

    # Tel hits per domein
    best_score = 0
    best_domein = None
    for keywords, domein in domein_patterns:
        score = sum(1 for kw in keywords if kw in t)
        if score > best_score:
            best_score = score
            best_domein = domein

    if best_score >= 2:  # Minimaal 2 trefwoorden
        return best_domein

    return None


def classificeer_alle_records(records):
    """Classificeer alle records met inhoud-gebaseerde classificatie + fallback."""
    for r in records:
        title = r.get("title") or ""
        beleidsveld = r.get("beleidsveld") or ""
        gevraagd_besluit = r.get("gevraagd_besluit") or ""
        pdf_tekst = r.get("pdf_tekst") or ""
        pdf_cluster = r.get("pdf_cluster") or ""

        # Besluittype: probeer eerst inhoud, dan titel
        bt_inhoud = classificeer_besluittype_inhoud(gevraagd_besluit, title)
        bt_titel = classificeer_besluittype(title)

        if bt_inhoud:
            r["besluittype"], r["besluittype_detail"] = bt_inhoud
            r["bt_bron"] = "inhoud"
        else:
            r["besluittype"], r["besluittype_detail"] = bt_titel
            if bt_titel[1].endswith("Niet geclassificeerd"):
                r["bt_bron"] = "geen"
            else:
                r["bt_bron"] = "titel"

        # Beleidsdomein: probeer inhoud, dan titel, dan beleidsveld
        bd_inhoud = classificeer_beleidsdomein_inhoud(
            pdf_tekst, pdf_cluster, title, beleidsveld)
        bd_titel_hoofd, bd_titel_detail = classificeer_beleidsdomein(title, beleidsveld)

        if bd_inhoud:
            r["beleidsdomein"], r["beleidsdomein_detail"] = bd_inhoud
            r["bd_bron"] = "inhoud"
        else:
            r["beleidsdomein"] = bd_titel_hoofd
            r["beleidsdomein_detail"] = bd_titel_detail
            r["bd_bron"] = "titel/beleidsveld"

    return records


# --- Excel generatie ---

EXCEL_COLUMNS = [
    ("BB-nummer", "externalid", 16),
    ("Titel", "title", 55),
    ("Besluittype", "besluittype", 18),
    ("Besluittype detail", "besluittype_detail", 28),
    ("Beleidsdomein", "beleidsdomein", 20),
    ("Beleidsdomein detail", "beleidsdomein_detail", 26),
    ("Gevraagd besluit", "gevraagd_besluit", 80),
    ("Waarom dit voorstel", "waarom_voorstel", 60),
    ("Cluster (PDF)", "pdf_cluster", 22),
    ("Beleidsveld (origineel)", "beleidsveld", 20),
    ("Datum ontvangen", "registrationdate", 16),
    ("Portefeuillehouder", "portefeuillehouder", 30),
    ("Classificatiebron BT", "bt_bron", 14),
    ("Classificatiebron BD", "bd_bron", 16),
    ("Pagina's", "pdf_paginas", 10),
    ("PDF bestand", "pdf_bestand", 50),
    ("Hoofddocument URL", "hoofddocument_url", 50),
]


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

    # --- Blad 8: Classificatiekwaliteit ---
    ws8 = wb.create_sheet("Classificatiekwaliteit")
    headers = [("Metriek", 40), ("Waarde", 15)]
    for col_idx, (header, width) in enumerate(headers, 1):
        cell = ws8.cell(row=1, column=col_idx, value=header)
        cell.font = styles["header_font"]
        cell.fill = styles["header_fill"]
        cell.alignment = styles["header_alignment"]
        cell.border = styles["thin_border"]
        ws8.column_dimensions[get_column_letter(col_idx)].width = width

    totaal = len(records)
    pdf_ok = sum(1 for r in records if r.get("pdf_ok"))
    gb_ok = sum(1 for r in records if r.get("gevraagd_besluit"))
    bt_inhoud = sum(1 for r in records if r.get("bt_bron") == "inhoud")
    bt_titel = sum(1 for r in records if r.get("bt_bron") == "titel")
    bt_geen = sum(1 for r in records if r.get("bt_bron") == "geen")
    bd_inhoud = sum(1 for r in records if r.get("bd_bron") == "inhoud")
    bd_fallback = sum(1 for r in records if r.get("bd_bron") == "titel/beleidsveld")

    metrieken = [
        ("Totaal raadsvoorstellen", totaal),
        ("PDFs succesvol gedownload", f"{pdf_ok} ({round(pdf_ok/totaal*100)}%)"),
        ("'Gevraagd besluit' gevonden", f"{gb_ok} ({round(gb_ok/totaal*100)}%)"),
        ("", ""),
        ("Besluittype - op basis van inhoud", f"{bt_inhoud} ({round(bt_inhoud/totaal*100)}%)"),
        ("Besluittype - op basis van titel", f"{bt_titel} ({round(bt_titel/totaal*100)}%)"),
        ("Besluittype - niet geclassificeerd", f"{bt_geen} ({round(bt_geen/totaal*100)}%)"),
        ("", ""),
        ("Beleidsdomein - op basis van inhoud", f"{bd_inhoud} ({round(bd_inhoud/totaal*100)}%)"),
        ("Beleidsdomein - op basis van titel/beleidsveld", f"{bd_fallback} ({round(bd_fallback/totaal*100)}%)"),
    ]
    for row_idx, (label, val) in enumerate(metrieken, 2):
        ws8.cell(row=row_idx, column=1, value=label).border = styles["thin_border"]
        cell = ws8.cell(row=row_idx, column=2, value=val)
        cell.border = styles["thin_border"]
        cell.alignment = styles["cell_alignment"]

    ws8.freeze_panes = "A2"

    wb.save(filename)
    print(f"\nExcel opgeslagen: {filename}")
    print(f"  Blad 'Raadsvoorstellen': {totaal} rijen")
    print(f"  PDF download: {pdf_ok}/{totaal}")
    print(f"  Gevraagd besluit gevonden: {gb_ok}/{totaal}")
    print(f"  Classificatie besluittype: inhoud={bt_inhoud}, titel={bt_titel}, geen={bt_geen}")
    print(f"  Classificatie beleidsdomein: inhoud={bd_inhoud}, fallback={bd_fallback}")


# --- Cache ---

def save_cache(records):
    """Sla op als JSON (zonder pdf_tekst om grootte te beperken)."""
    cache_records = []
    for r in records:
        cr = {k: v for k, v in r.items() if k != "pdf_tekst"}
        cache_records.append(cr)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_records, f, ensure_ascii=False)
    print(f"  Cache opgeslagen: {CACHE_FILE}")


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
        print(f"  Cache geladen: {len(records)} records")
        return records
    return None


# --- Main ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download raadsvoorstellen PDFs, extraheer inhoud en classificeer")
    parser.add_argument("--from-cache", action="store_true",
                        help="Gebruik cache (sla API + download over)")
    parser.add_argument("--skip-download", action="store_true",
                        help="Sla PDF download over, gebruik bestaande bestanden")
    args = parser.parse_args()

    os.makedirs(PDF_DIR, exist_ok=True)

    if args.from_cache:
        records = load_cache()
        if records:
            # Herextraheer tekst uit bestaande PDFs
            print("\nStap 1: Tekst extraheren uit bestaande PDFs...")
            extraheer_alle_teksten(records)
            print("\nStap 2: Classificeren op basis van inhoud...")
            classificeer_alle_records(records)
            print("\nStap 3: Excel genereren...")
            create_excel(records, "raadsvoorstellen.xlsx")
            sys.exit(0)
        else:
            print("Geen cache gevonden, volledige run wordt gestart.")

    print("Stap 1: Raadsvoorstellen ophalen via API...")
    records = fetch_all_records()

    print(f"\nStap 2: Detailpagina's ophalen ({len(records)} records)...")
    fetch_all_details(records)
    met_doc = sum(1 for r in records if r.get("doc_id"))
    print(f"  {met_doc} records met hoofddocument")

    if not args.skip_download:
        print(f"\nStap 3: PDFs downloaden naar '{PDF_DIR}/'...")
        download_all_pdfs(records)
        pdf_ok = sum(1 for r in records if r.get("pdf_ok"))
        print(f"  {pdf_ok} PDFs succesvol gedownload")
    else:
        print("\nStap 3: PDF download overgeslagen, bestaande bestanden gebruiken...")
        for r in records:
            if r.get("doc_id"):
                bestandsnaam = safe_filename(
                    r.get("externalid", ""), r.get("title", ""))
                pad = os.path.join(PDF_DIR, bestandsnaam)
                if os.path.exists(pad) and os.path.getsize(pad) > 0:
                    r["pdf_bestand"] = bestandsnaam
                    r["pdf_ok"] = True
                else:
                    r["pdf_bestand"] = ""
                    r["pdf_ok"] = False
            else:
                r["pdf_bestand"] = ""
                r["pdf_ok"] = False

    # Cache opslaan na download (voor herstart)
    save_cache(records)

    print(f"\nStap 4: Tekst extraheren uit PDFs...")
    extraheer_alle_teksten(records)
    gb_ok = sum(1 for r in records if r.get("gevraagd_besluit"))
    print(f"  'Gevraagd besluit' gevonden in {gb_ok} documenten")

    print(f"\nStap 5: Classificeren op basis van inhoud...")
    classificeer_alle_records(records)

    # Update cache met classificatie
    save_cache(records)

    print("\nStap 6: Excel genereren...")
    create_excel(records, "raadsvoorstellen.xlsx")
