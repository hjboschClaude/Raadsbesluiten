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
        record["bijlagen_tekst"] = "\n".join(
            f"{b['naam']} ({b['grootte']})" for b in bijlagen
        )
        record["bijlagen_urls"] = "\n".join(b["url"] for b in bijlagen)
        record["detail_ok"] = True
    except Exception as e:
        print(f"  FOUT detail {row_id}: {e}", file=sys.stderr)
        record["doc_id"] = ""
        record["hoofddocument_naam"] = ""
        record["hoofddocument_url"] = ""
        record["aantal_bijlagen"] = 0
        record["bijlagen_tekst"] = ""
        record["bijlagen_urls"] = ""
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


def fetch_bijlagen_for_record(record):
    """Haal alleen bijlagedata op voor een bestaand record."""
    row_id = record["DT_RowId"]
    url = f"{BASE_URL}/Reports/Item/{row_id}"
    try:
        html = http_get_with_retry(url)
        bijlagen = parse_documents(html, "Bijlage(n)")
        record["aantal_bijlagen"] = len(bijlagen)
        record["bijlagen_tekst"] = "\n".join(
            f"{b['naam']} ({b['grootte']})" for b in bijlagen
        )
        record["bijlagen_urls"] = "\n".join(b["url"] for b in bijlagen)
    except Exception as e:
        print(f"  FOUT bijlagen {row_id}: {e}", file=sys.stderr)
        record.setdefault("bijlagen_tekst", "")
        record.setdefault("bijlagen_urls", "")
    return record


def fetch_missing_bijlagen(records):
    """Haal bijlagedata op voor records waar die ontbreekt."""
    missing = [r for r in records if "bijlagen_tekst" not in r]
    if not missing:
        print("  Bijlagedata al compleet voor alle records.")
        return records
    print(f"  Bijlagedata ophalen voor {len(missing)} records...")
    completed = 0
    total = len(missing)
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_bijlagen_for_record, r): r for r in missing}
        for future in as_completed(futures):
            completed += 1
            if completed % 50 == 0 or completed == total:
                print(f"  Bijlagen opgehaald: {completed}/{total}")
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
    Probeert eerst inhoud-classificatie, daarna titel-gebaseerde fallbacks.
    """
    # Normaliseer: lowercase, collapse whitespace (PDF extractie geeft soms
    # merged/split woorden: "vast testellen", "co ördinatieregeling", etc.)
    gb = re.sub(r'\s+', ' ', (gevraagd_besluit or "").lower().strip())
    tl = re.sub(r'\s+', ' ', titel.lower().strip())

    # Helper: check of "vaststellen" in enige vorm voorkomt in gb
    heeft_vaststellen = bool(
        gb and re.search(r'vast\s*(?:te\s*)?stellen', gb))

    # --- Inhoud-gebaseerde classificatie (alleen als gb niet leeg) ---
    if gb:
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

        # Coördinatieregeling (art. 3.30 Wro)
        # PDF geeft soms "co ördinatieregeling" met extra spatie
        if re.search(r'co\s*[öo]rdinatieregeling', gb):
            return ("1. Ruimtelijk", "1.8 Coördinatieregeling")

        # Verordening
        if "verordening" in gb:
            if "wijzig" in gb:
                return ("2. Regelgeving", "2.1 Verordening (wijziging)")
            return ("2. Regelgeving", "2.1 Verordening (vaststelling)")

        # Financieel
        if any(w in gb for w in [
                "krediet", "budget beschikbaar", "middelen beschikbaar"]):
            return ("3. Financieel", "3.4 Krediet")
        if "begroting" in gb:
            return ("3. Financieel", "3.1 Begroting")
        if "jaarrekening" in gb or "jaarstukken" in gb:
            return ("3. Financieel", "3.2 Jaarrekening / Jaarstukken")
        if "subsidie" in gb:
            return ("3. Financieel", "3.5 Subsidie")
        if any(w in gb for w in ["belasting", "tarieven", "leges"]):
            return ("3. Financieel", "3.3 Belasting / Tarieven")

        # Bestuurlijk - benoeming
        if any(w in gb for w in ["te benoemen", "benoemen", "herbenoemen"]):
            return ("4. Bestuurlijk", "4.1 Benoeming / Aanwijzing")

        # Gemeenschappelijke regeling
        if "zienswijze" in gb and re.search(
                r'gemeenschappelijke\s+regeling', gb):
            return ("4. Bestuurlijk", "4.2 Gem. regeling (zienswijze)")
        if re.search(r'gemeenschappelijke\s+regeling', gb):
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

        # Wegonttrekking
        if "openbaar verkeer" in gb and "onttrekk" in gb:
            return ("1. Ruimtelijk", "1.7 Wegonttrekking")

        # Voorkeursrecht (Wet voorkeursrecht gemeenten)
        if "voorkeursrecht" in gb:
            return ("1. Ruimtelijk", "1.9 Voorkeursrecht (WVG)")

        # VVGB / Adviesrecht / BOPA
        if ("adviesrecht" in gb or "verklaring van geen bedenkingen" in gb
                or "vvgb" in gb
                or ("omgevingsvergunning" in gb and "buitenplanse" in gb)
                or ("bindend advies" in gb and "omgevingsvergunning" in gb)):
            return ("1. Ruimtelijk", "1.5 VVGB / Adviesrecht")

        # Erfpacht
        if "erfpacht" in gb:
            return ("1. Ruimtelijk", "1.6 Erfpacht")

        # Bijdrageregeling Ontplofbare Oorlogsresten / kostenverhaal
        if "oorlogsresten" in gb or "ontplofbare" in gb:
            return ("3. Financieel", "3.7 Declaratie / Kostenverhaal")

        # Bestemmingsreserve / reserve omzetten
        if "bestemmingsreserve" in gb:
            return ("3. Financieel", "3.4 Krediet")

        # Grondprijzen
        if "grondprijs" in gb or "grondprijzen" in gb:
            return ("3. Financieel", "3.4 Krediet")

        # Huren kostendekkendheid
        if "kostendekkend" in gb and "huren" in gb:
            return ("3. Financieel", "3.4 Krediet")

        # Investering / Eneco-middelen / fonds instellen
        if any(w in gb for w in [
                "investering", "eneco-middelen", "investeringsvoorstel"]):
            return ("3. Financieel", "3.6 Investering")
        if "fonds" in gb and "instellen" in gb:
            return ("3. Financieel", "3.6 Investering")

        # Accountantscontrole
        if "accountant" in gb or "accountantscontrole" in gb:
            return ("5. Controle", "5.4 Rechtmatigheid / Accountant")

        # Rekenkamerrapport
        if "rekenkamer" in gb:
            return ("5. Controle", "5.1 Rekenkamerrapport")

        # Instelling commissie / adviesorgaan (art. 84 Gemeentewet)
        if ("instellen" in gb or "instelling" in gb
                or "inrichting" in gb) and (
                "commissie" in gb or "adviescommissie" in gb
                or "adviesorgaan" in gb or "raadscommissie" in gb):
            return ("4. Bestuurlijk", "4.3 Organisatie / Werkwijze raad")

        # Aantal wethouders
        if "wethouder" in gb and (
                "aantal" in gb or "tijdsbestedingsnorm" in gb):
            return ("4. Bestuurlijk", "4.3 Organisatie / Werkwijze raad")

        # Wijk aan Zet / gebiedscommissie / wijkraad
        if (re.search(r'wijk\s*aan\s*zet', gb)
                or "wijkraad" in gb or "gebiedscommissie" in gb):
            return ("4. Bestuurlijk", "4.3 Organisatie / Werkwijze raad")

        # Opdracht aan college (participatietraject, reactie sturen)
        if "opdracht" in gb and "college" in gb:
            return ("4. Bestuurlijk", "4.3 Organisatie / Werkwijze raad")

        # Aanwijzen terrein (begraafplaats, etc.)
        if ("aanwijzen" in gb or "aan te wijzen" in gb) and "terrein" in gb:
            return ("1. Ruimtelijk", "1.6 Erfpacht")

        # Breed: Nota / beleidskader / plan vaststellen
        if heeft_vaststellen:
            nota_keywords = [
                "nota", "kader", "visie", "strategie", "programma",
                "handboek", "grondprijzen", "woonakkoord",
                "huisvestingsplan", "vuistregels", "wateratlas",
                "kiesreglement", "wijkplan", "beleidsregel", "leidraad",
                "richtlijn", "beleidskader", "beleidsnota",
                "gebiedsuitwerking", "uitvoeringsvoorstel", "horecanota",
                "grondstoffennota", "transitie", "huisvestingsplannen",
                "stijl", "plan", "beleidsplan",
            ]
            if any(w in tl or w in gb for w in nota_keywords):
                return ("2. Regelgeving", "2.2 Beleidsnota / Beleidsregel")

        # Nog breder: vaststellen met specifieke signalen
        if heeft_vaststellen:
            if "aandelen" in gb or "deelneming" in gb:
                return ("3. Financieel", "3.6 Investering")
            if "gunning" in gb or "1-op-1" in gb:
                return ("3. Financieel", "3.4 Krediet")
            if "algemeen belang" in gb or "mededingingswet" in gb:
                return ("2. Regelgeving", "2.2 Beleidsnota / Beleidsregel")

    # --- Titel-gebaseerde fallbacks (ook voor lege gevraagd_besluit) ---
    if "instelling" in tl and (
            "commissie" in tl or "raadscommissie" in tl):
        return ("4. Bestuurlijk", "4.3 Organisatie / Werkwijze raad")
    if "accountant" in tl:
        return ("5. Controle", "5.4 Rechtmatigheid / Accountant")
    if "vaststelling" in tl and "wijkplan" in tl:
        return ("2. Regelgeving", "2.2 Beleidsnota / Beleidsregel")
    if "eindrapportage" in tl or "eindevaluatie" in tl:
        return ("5. Controle", "5.3 Decharge / Verantwoording")
    if "bestuursmodel" in tl or "herziening" in tl and "stichting" in tl:
        return ("4. Bestuurlijk", "4.3 Organisatie / Werkwijze raad")

    return None


def classificeer_beleidsdomein_inhoud(tekst, cluster, titel, beleidsveld):
    """Classificeer beleidsdomein: beleidsveld is leidend, inhoud verfijnt detail.

    Het beleidsveld uit de API bepaalt altijd de hoofdcategorie.
    PDF-inhoud (cluster + trefwoorden) wordt gebruikt om het subdomein
    te verfijnen binnen die hoofdcategorie.

    Returns (hoofddomein, subdomein).
    """
    bv = (beleidsveld or "").lower().strip()

    # --- Stap 1: beleidsveld -> hoofddomein + default subdomein ---
    beleidsveld_mapping = {
        "bouwen en wonen":     ("A. Ruimte & Wonen", "A.1 Stedelijke ontwikkeling"),
        "buitenruimte":        ("A. Ruimte & Wonen", "A.3 Buitenruimte / Groen"),
        "projecten":           ("A. Ruimte & Wonen", "A.1 Stedelijke ontwikkeling"),
        "economie":            ("B. Economie & Haven", "B.2 Economisch beleid"),
        "haven":               ("B. Economie & Haven", "B.1 Haven"),
        "werk en inkomen":     ("B. Economie & Haven", "B.3 Werk & Inkomen"),
        "mobiliteit":          ("C. Mobiliteit", "C.1 Verkeer"),
        "duurzaam":            ("D. Duurzaamheid", "D.1 Energie / Klimaat"),
        "onderwijs":           ("E. Sociaal", "E.1 Onderwijs"),
        "zorg":                ("E. Sociaal", "E.2 Zorg / Jeugd"),
        "jeugd":               ("E. Sociaal", "E.2 Zorg / Jeugd"),
        "cultuur":             ("E. Sociaal", "E.3 Cultuur"),
        "sport":               ("E. Sociaal", "E.4 Sport"),
        "armoedebestrijding":  ("E. Sociaal", "E.5 Welzijn / Armoede"),
        "welzijn":             ("E. Sociaal", "E.5 Welzijn / Armoede"),
        "samenleven":          ("E. Sociaal", "E.6 Samenleven / Wijken"),
        "wijken":              ("E. Sociaal", "E.6 Samenleven / Wijken"),
        "gebieden":            ("E. Sociaal", "E.6 Samenleven / Wijken"),
        "veiligheid":          ("F. Veiligheid", "F.1 Openbare orde / Handhaving"),
        "bestuur":             ("G. Bestuur & Financiën", "G.3 Raadsorganisatie"),
        "organisatie":         ("G. Bestuur & Financiën", "G.2 Gemeentelijke organisatie"),
        "presidium":           ("G. Bestuur & Financiën", "G.3 Raadsorganisatie"),
        "cor":                 ("G. Bestuur & Financiën", "G.4 Interbestuurlijk"),
    }
    # Normaliseer financiën varianten
    if bv in ("financien-inactief", "financïen", "financien", "financiën"):
        hoofddomein = "G. Bestuur & Financiën"
        default_detail = "G.1 Gemeentefinanciën"
    elif bv in beleidsveld_mapping:
        hoofddomein, default_detail = beleidsveld_mapping[bv]
    else:
        hoofddomein = "G. Bestuur & Financiën"
        default_detail = "G.1 Gemeentefinanciën"

    # --- Stap 2: verfijn subdomein op basis van inhoud ---
    # Subdomein-patronen gegroepeerd per hoofddomein
    subdomein_patterns = {
        "A. Ruimte & Wonen": [
            (["bestemmingsplan", "omgevingsplan", "grondexploitatie", "welstand",
              "stedenbouwkundig", "gebiedsontwikkeling", "bouwplan", "plangebied"],
             "A.1 Stedelijke ontwikkeling"),
            (["woning", "huurwoning", "woonvisie", "huisvesting", "woningbouw",
              "flexwonen", "sociale huur", "koopwoning"],
             "A.2 Woonbeleid"),
            (["groen", "bomen", "buitenruimte", "openbare ruimte", "begraafplaats",
              "speeltuin", "stadspark"],
             "A.3 Buitenruimte / Groen"),
            (["monument", "erfgoed", "beschermd stadsgezicht", "restauratie",
              "rijksmonument"],
             "A.4 Monumenten / Erfgoed"),
        ],
        "B. Economie & Haven": [
            (["haven", "havengebied", "havenbedrijf", "havenmeester", "scheepvaart",
              "havenverordening"],
             "B.1 Haven"),
            (["economie", "ondernemers", "bedrijventerrein", "horeca", "winkelgebied",
              "economisch", "investering", "vestigingsklimaat", "mkb"],
             "B.2 Economisch beleid"),
            (["werk", "inkomen", "uitkering", "participatiewet", "bijstand",
              "arbeidsmarkt"],
             "B.3 Werk & Inkomen"),
        ],
        "C. Mobiliteit": [
            (["mobiliteit", "verkeer", "fiets", "voetganger", "weginfrastructuur",
              "bereikbaarheid", "verkeersplan"],
             "C.1 Verkeer"),
            (["openbaar vervoer", "metro", "tram", "bus", "ret"],
             "C.2 Openbaar vervoer"),
            (["parkeer", "parkeergarage", "parkeernorm", "autoparkeren"],
             "C.3 Parkeren"),
        ],
        "D. Duurzaamheid": [
            (["klimaat", "energie", "warmte", "duurzaam", "co2", "circulair",
              "energietransitie", "windenergie", "zonnepanelen"],
             "D.1 Energie / Klimaat"),
            (["water", "riool", "riolering", "wateroverlast", "waterkwaliteit",
              "klimaatadaptatie"],
             "D.2 Water / Klimaatadaptatie"),
        ],
        "E. Sociaal": [
            (["onderwijs", "school", "boor", "leerling", "leraar", "kinderopvang",
              "onderwijshuisvesting"],
             "E.1 Onderwijs"),
            (["zorg", "jeugdhulp", "wmo", "ggz", "beschermd wonen",
              "maatschappelijke ondersteuning", "jeugdzorg"],
             "E.2 Zorg / Jeugd"),
            (["cultuur", "museum", "theater", "bibliotheek", "kunst", "festival",
              "cultureel", "kunstenaar"],
             "E.3 Cultuur"),
            (["sport", "stadion", "zwembad", "sporthal", "voetbal", "sportclub",
              "sportaccommodatie"],
             "E.4 Sport"),
            (["armoede", "schuld", "minima", "rotterdampas", "armoedebeleid",
              "schuldhulp"],
             "E.5 Welzijn / Armoede"),
            (["wijk", "wijkraad", "samenleven", "integratie", "buurt",
              "gebiedscommissie", "bewonersparticipatie"],
             "E.6 Samenleven / Wijken"),
        ],
        "F. Veiligheid": [
            (["veiligheid", "camera", "politie", "handhaving", "toezicht",
              "ondermijning", "criminaliteit"],
             "F.1 Openbare orde / Handhaving"),
        ],
        "G. Bestuur & Financiën": [
            (["begroting", "jaarrekening", "jaarstukken", "belasting", "tarieven",
              "krediet", "subsidie", "investering", "financ"],
             "G.1 Gemeentefinanciën"),
            (["organisatie", "ambtelijk", "dienstverlening", "bedrijfsvoering",
              "personeelsbeleid"],
             "G.2 Gemeentelijke organisatie"),
            (["raadscommissie", "griffie", "presidium", "raadslid", "raadsvergadering",
              "commissie", "benoeming"],
             "G.3 Raadsorganisatie"),
            (["gemeenschappelijke regeling", "regio", "metropoolregio",
              "interbestuurlijk", "samenwerkingsverband"],
             "G.4 Interbestuurlijk"),
        ],
    }

    # Zoek trefwoorden in PDF-tekst voor detail-verfijning
    if tekst:
        t = tekst[:5000].lower()
        patterns = subdomein_patterns.get(hoofddomein, [])
        best_score = 0
        best_detail = None
        for keywords, detail in patterns:
            score = sum(1 for kw in keywords if kw in t)
            if score > best_score:
                best_score = score
                best_detail = detail
        if best_score >= 2:
            return (hoofddomein, best_detail)

    return (hoofddomein, default_detail)


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

        # Beleidsdomein: beleidsveld is leidend, inhoud verfijnt detail
        bd_hoofd, bd_detail = classificeer_beleidsdomein_inhoud(
            pdf_tekst, pdf_cluster, title, beleidsveld)
        r["beleidsdomein"] = bd_hoofd
        r["beleidsdomein_detail"] = bd_detail
        r["bd_bron"] = "beleidsveld"

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
    ("Pagina's", "pdf_paginas", 10),
    ("PDF bestand", "pdf_bestand", 50),
    ("Hoofddocument URL", "hoofddocument_url", 50),
    ("Aantal bijlagen", "aantal_bijlagen", 15),
    ("Bijlagen", "bijlagen_tekst", 100),
    ("Bijlage URLs", "bijlagen_urls", 100),
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

    metrieken = [
        ("Totaal raadsvoorstellen", totaal),
        ("PDFs succesvol gedownload", f"{pdf_ok} ({round(pdf_ok/totaal*100)}%)"),
        ("'Gevraagd besluit' gevonden", f"{gb_ok} ({round(gb_ok/totaal*100)}%)"),
        ("", ""),
        ("Besluittype - op basis van inhoud", f"{bt_inhoud} ({round(bt_inhoud/totaal*100)}%)"),
        ("Besluittype - op basis van titel", f"{bt_titel} ({round(bt_titel/totaal*100)}%)"),
        ("Besluittype - niet geclassificeerd", f"{bt_geen} ({round(bt_geen/totaal*100)}%)"),
        ("", ""),
        ("Beleidsdomein - bron", "Beleidsveld (origineel) is leidend"),
        ("Beleidsdomein - detail verfijnd met inhoud",
         f"{sum(1 for r in records if r.get('pdf_tekst') or r.get('pdf_cluster'))}/{totaal}"),
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
    print(f"  Beleidsdomein: beleidsveld leidend, detail verfijnd met inhoud")


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
            # Haal bijlagedata op als die ontbreekt in de cache
            print("\nStap 1: Bijlagedata controleren en aanvullen...")
            fetch_missing_bijlagen(records)
            # Herextraheer tekst uit bestaande PDFs
            print("\nStap 2: Tekst extraheren uit bestaande PDFs...")
            extraheer_alle_teksten(records)
            print("\nStap 3: Classificeren op basis van inhoud...")
            classificeer_alle_records(records)
            print("\nStap 4: Excel genereren...")
            create_excel(records, "raadsvoorstellen.xlsx")
            # Cache bijwerken met bijlagedata
            save_cache(records)
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
