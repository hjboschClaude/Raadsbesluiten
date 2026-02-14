#!/usr/bin/env python3
"""Download een motie van gemeenteraad.rotterdam.nl en extraheer de inhoud.

Gebruik:
    python3 download_motie.py <BB-nummer of zoekterm>
    python3 download_motie.py 26bb001043
    python3 download_motie.py "integriteitsmeldingen"
    python3 download_motie.py --lijst                   # Toon recente moties
    python3 download_motie.py --lijst --zoek "wijk"      # Zoek in moties

Opties:
    --pdf          Sla het PDF-bestand ook op (in map 'moties/')
    --lijst        Toon een lijst van moties (standaard: 20 meest recente)
    --aantal N     Aantal moties in lijst (standaard: 20)
    --zoek TERM    Filter de lijst op zoekterm
"""

import urllib.request
import json
import re
import sys
import os
import time
import io
import argparse

from pypdf import PdfReader

BASE_URL = "https://gemeenteraad.rotterdam.nl"
LIST_ID = "a61fab39-bc62-464f-968d-db31925a66e5"
API_URL = f"{BASE_URL}/Reports/GetReportData/{LIST_ID}"

COLUMNS_PARAM = "&".join([
    "columns[0][data]=externalid&columns[0][name]=externalid&columns[0][searchable]=true",
    "columns[1][data]=title&columns[1][name]=title&columns[1][searchable]=true",
    "columns[2][data]=partij&columns[2][name]=partij&columns[2][searchable]=true",
    "columns[3][data]=registrationdate&columns[3][name]=registrationdate&columns[3][searchable]=true",
    "columns[4][data]=uitslag&columns[4][name]=uitslag&columns[4][searchable]=true",
    "columns[5][data]=completed&columns[5][name]=completed&columns[5][searchable]=true",
    "columns[6][data]=datecompleted&columns[6][name]=datecompleted&columns[6][searchable]=true",
    "columns[7][data]=medeondertekenaars&columns[7][name]=medeondertekenaars&columns[7][searchable]=true",
    "columns[8][data]=medeindiendepartijen&columns[8][name]=medeindiendepartijen&columns[8][searchable]=true",
    "columns[9][data]=raadslid&columns[9][name]=raadslid&columns[9][searchable]=true",
])


# --- HTTP helpers ---

def http_request(url, max_retries=4, timeout=30, data=None, headers=None):
    """HTTP request met exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  Poging {attempt + 1} mislukt ({e}), wacht {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise


def http_text(url, **kwargs):
    """HTTP request die tekst retourneert."""
    return http_request(url, **kwargs).decode("utf-8")


# --- API functies ---

def fetch_page(draw, start, length, search=""):
    """Haal een pagina moties op via de API."""
    params = (
        f"draw={draw}&start={start}&length={length}"
        f"&order[0][column]=3&order[0][dir]=desc"
        f"&search[value]={urllib.request.quote(search)}&search[regex]=false"
        f"&{COLUMNS_PARAM}"
    )
    body = http_text(
        API_URL,
        data=params.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{BASE_URL}/Reports/Details/{LIST_ID}",
        },
    )
    return json.loads(body)


def zoek_motie(zoekterm):
    """Zoek een motie op BB-nummer of zoekterm. Retourneert lijst van matches."""
    result = fetch_page(1, 0, 100, search=zoekterm)
    return result["data"], result["recordsTotal"]


def haal_lijst_op(aantal=20, zoekterm=""):
    """Haal een lijst van recente moties op."""
    result = fetch_page(1, 0, aantal, search=zoekterm)
    return result["data"], result["recordsTotal"]


# --- Detail pagina parsing ---

def get_text_field(html, label):
    """Haal tekstveld op uit dt/dd structuur."""
    pattern = r'<dt[^>]*>\s*' + re.escape(label) + r'\s*</dt>\s*<dd[^>]*>(.*?)</dd>'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return ""
    content = match.group(1)
    pre = re.search(r'<span class="pre-line">(.*?)</span>', content, re.DOTALL)
    if pre:
        text = re.sub(r'<[^>]+>', ' ', pre.group(1)).strip()
    else:
        text = re.sub(r'<[^>]+>', ' ', content).strip()
    return re.sub(r'\s+', ' ', text).strip()


def get_list_field(html, label):
    """Haal lijstveld op (ul/li) uit dt/dd structuur."""
    pattern = r'<dt[^>]*>\s*' + re.escape(label) + r'\s*</dt>\s*<dd[^>]*>(.*?)</dd>'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return ""
    content = match.group(1)
    items = re.findall(r'<li[^>]*>(.*?)</li>', content, re.DOTALL)
    if items:
        return ", ".join(re.sub(r'<[^>]+>', '', item).strip() for item in items)
    return re.sub(r'<[^>]+>', ' ', content).strip().replace("  ", " ")


def get_checkbox_field(html, label):
    """Haal checkbox-veld op (Ja/Nee)."""
    pattern = r'<dt[^>]*>\s*' + re.escape(label) + r'\s*</dt>\s*<dd[^>]*>(.*?)</dd>'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return ""
    content = match.group(1)
    if 'fa-check-square' in content:
        return "Ja"
    if 'fa-square' in content:
        return "Nee"
    return ""


def get_document_ids(html):
    """Extraheer document-IDs en namen uit de detailpagina."""
    pattern = r'<dt[^>]*>\s*Hoofddocument\s*</dt>\s*<dd[^>]*>(.*?)</dd>'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return []
    docs = []
    for doc_match in re.finditer(
        r'data-document-id="([^"]+)"[^>]*>\s*'
        r'<span[^>]*>[^<]*</span>\s*'
        r'(.*?)\s*<span class="badge',
        match.group(1), re.DOTALL
    ):
        doc_id = doc_match.group(1)
        naam = doc_match.group(2).strip()
        docs.append({"id": doc_id, "naam": naam})
    return docs


def haal_details_op(row_id):
    """Haal de detailpagina op en extraheer alle velden."""
    url = f"{BASE_URL}/Reports/Item/{row_id}"
    html = http_text(url)

    details = {
        "portefeuillehouder": get_list_field(html, "Portefeuillehouder"),
        "beleidsveld": get_list_field(html, "Beleidsveld"),
        "commissie": get_text_field(html, "Commissie"),
        "omschrijving": get_text_field(html, "Omschrijving"),
        "verwachte_datum_afdoening": get_text_field(html, "Verwachte datum afdoening"),
        "stand_van_zaken": get_text_field(html, "Stand van zaken"),
        "afgedaan": get_checkbox_field(html, "Afgedaan"),
        "afdoeningsvoorstel_aanwezig": get_checkbox_field(html, "Afdoeningsvoorstel aanwezig"),
        "toelichting": get_text_field(html, "Toelichting"),
        "afdoening": get_text_field(html, "Afdoening"),
        "documenten": get_document_ids(html),
    }
    return details


# --- PDF download en extractie ---

def download_pdf(document_id):
    """Download een PDF via het Document/View endpoint."""
    url = f"{BASE_URL}/Document/View/{document_id}"
    return http_request(url, headers={
        "Referer": f"{BASE_URL}/",
    })


def extraheer_tekst(pdf_bytes):
    """Extraheer tekst uit PDF-bytes."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    paginas = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            paginas.append(text)
    return paginas


def sla_pdf_op(pdf_bytes, bestandsnaam, map="moties"):
    """Sla PDF op in de opgegeven map."""
    os.makedirs(map, exist_ok=True)
    # Verwijder ongeldige karakters uit bestandsnaam
    veilig = re.sub(r'[<>:"/\\|?*]', '_', bestandsnaam)
    pad = os.path.join(map, veilig)
    with open(pad, "wb") as f:
        f.write(pdf_bytes)
    return pad


# --- Weergave ---

def toon_lijst(records, totaal):
    """Toon een lijst van moties."""
    print(f"\n{'='*80}")
    print(f"  Moties ({len(records)} van {totaal} resultaten)")
    print(f"{'='*80}\n")

    for r in records:
        uitslag = r.get("uitslag", "")
        bb = r.get("externalid", "")
        titel = r.get("title", "")
        partij = r.get("partij", "")
        datum = r.get("registrationdate", "")
        raadslid = r.get("raadslid", "")

        print(f"  {bb:<16} {datum:>12}  {uitslag:<14} {partij}")
        print(f"  {titel}")
        if raadslid:
            print(f"  Raadslid: {raadslid}")
        print()


def toon_motie(record, details, tekst_paginas):
    """Toon de volledige motie-informatie en geëxtraheerde tekst."""
    bb = record.get("externalid", "")
    titel = record.get("title", "")
    partij = record.get("partij", "")
    datum = record.get("registrationdate", "")
    uitslag = record.get("uitslag", "")
    raadslid = record.get("raadslid", "")
    medeondertekenaars = record.get("medeondertekenaars", "")
    medeindieners = record.get("medeindiendepartijen", "")
    row_id = record.get("DT_RowId", "")

    print(f"\n{'='*80}")
    print(f"  MOTIE: {titel}")
    print(f"{'='*80}\n")

    print(f"  BB-nummer:        {bb}")
    print(f"  Datum ingediend:  {datum}")
    print(f"  Partij:           {partij}")
    print(f"  Raadslid:         {raadslid}")
    print(f"  Uitslag:          {uitslag}")
    if medeondertekenaars:
        print(f"  Medeondertekenaars: {medeondertekenaars}")
    if medeindieners:
        print(f"  Mede indienende partijen: {medeindieners}")
    print(f"  URL:              {BASE_URL}/Reports/Item/{row_id}")

    if details:
        print()
        if details["portefeuillehouder"]:
            print(f"  Portefeuillehouder:   {details['portefeuillehouder']}")
        if details["beleidsveld"]:
            print(f"  Beleidsveld:          {details['beleidsveld']}")
        if details["commissie"]:
            print(f"  Commissie:            {details['commissie']}")
        if details["afgedaan"]:
            print(f"  Afgedaan:             {details['afgedaan']}")
        if details["verwachte_datum_afdoening"]:
            print(f"  Verwachte afdoening:  {details['verwachte_datum_afdoening']}")
        if details["stand_van_zaken"]:
            print(f"  Stand van zaken:      {details['stand_van_zaken']}")
        if details["toelichting"]:
            print(f"  Toelichting:          {details['toelichting']}")
        if details["afdoening"]:
            print(f"  Afdoening:            {details['afdoening']}")

    if tekst_paginas:
        print(f"\n{'─'*80}")
        print(f"  INHOUD DOCUMENT ({len(tekst_paginas)} pagina's)")
        print(f"{'─'*80}\n")
        for i, tekst in enumerate(tekst_paginas):
            if len(tekst_paginas) > 1:
                print(f"  --- Pagina {i + 1} ---\n")
            print(tekst)
            print()
    else:
        print("\n  (Geen document beschikbaar of tekst kon niet worden geëxtraheerd)")


# --- Hoofdprogramma ---

def main():
    parser = argparse.ArgumentParser(
        description="Download een motie van gemeenteraad.rotterdam.nl en extraheer de inhoud.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Voorbeelden:\n"
            "  python3 download_motie.py 26bb001043\n"
            '  python3 download_motie.py "integriteitsmeldingen"\n'
            "  python3 download_motie.py --lijst\n"
            '  python3 download_motie.py --lijst --zoek "wijk"\n'
        ),
    )
    parser.add_argument("zoekterm", nargs="?", help="BB-nummer of zoekterm")
    parser.add_argument("--pdf", action="store_true", help="Sla het PDF-bestand ook op (in map 'moties/')")
    parser.add_argument("--lijst", action="store_true", help="Toon een lijst van moties")
    parser.add_argument("--aantal", type=int, default=20, help="Aantal moties in lijst (standaard: 20)")
    parser.add_argument("--zoek", default="", help="Filter de lijst op zoekterm")

    args = parser.parse_args()

    if not args.lijst and not args.zoekterm:
        parser.print_help()
        sys.exit(1)

    # --- Lijstmodus ---
    if args.lijst:
        zoek = args.zoek or args.zoekterm or ""
        print(f"Moties ophalen..." + (f' (zoekterm: "{zoek}")' if zoek else ""))
        records, totaal = haal_lijst_op(args.aantal, zoek)
        toon_lijst(records, totaal)
        return

    # --- Enkele motie ophalen ---
    zoekterm = args.zoekterm
    print(f'Zoeken naar motie: "{zoekterm}"...')

    records, totaal = zoek_motie(zoekterm)
    if not records:
        print(f"Geen moties gevonden voor: {zoekterm}", file=sys.stderr)
        sys.exit(1)

    # Als meerdere resultaten, zoek exact BB-nummer match
    exact = [r for r in records if r.get("externalid", "").lower() == zoekterm.lower()]
    if exact:
        record = exact[0]
    elif len(records) == 1:
        record = records[0]
    else:
        # Toon lijst zodat gebruiker kan kiezen
        print(f"\n{totaal} resultaten gevonden. Toon de eerste {len(records)}:\n")
        for i, r in enumerate(records):
            bb = r.get("externalid", "")
            titel = r.get("title", "")
            datum = r.get("registrationdate", "")
            uitslag = r.get("uitslag", "")
            print(f"  [{i + 1:>2}] {bb:<16} {datum:>12}  {uitslag:<14}")
            print(f"       {titel}")
        print()
        try:
            keuze = input("Kies een nummer (of Enter voor #1): ").strip()
            if not keuze:
                keuze = "1"
            idx = int(keuze) - 1
            if idx < 0 or idx >= len(records):
                print("Ongeldig nummer.", file=sys.stderr)
                sys.exit(1)
            record = records[idx]
        except (ValueError, EOFError):
            print("Ongeldige invoer.", file=sys.stderr)
            sys.exit(1)

    bb = record.get("externalid", "")
    titel = record.get("title", "")
    row_id = record.get("DT_RowId", "")

    # Haal details op
    print(f"Details ophalen voor {bb}: {titel}...")
    details = haal_details_op(row_id)

    # Download en extraheer PDF
    tekst_paginas = []
    pdf_bytes = None

    if details["documenten"]:
        doc = details["documenten"][0]  # Eerste (hoofd)document
        print(f"Document downloaden: {doc['naam']}...")
        try:
            pdf_bytes = download_pdf(doc["id"])
            print(f"  {len(pdf_bytes)} bytes gedownload")
            print("Tekst extraheren uit PDF...")
            tekst_paginas = extraheer_tekst(pdf_bytes)
            print(f"  {len(tekst_paginas)} pagina's geëxtraheerd")
        except Exception as e:
            print(f"  Fout bij downloaden/extraheren: {e}", file=sys.stderr)
    else:
        print("Geen document gevonden op de detailpagina.")

    # Toon resultaat
    toon_motie(record, details, tekst_paginas)

    # Optioneel: sla PDF op
    if args.pdf and pdf_bytes:
        bestandsnaam = f"[{bb}] {titel}.pdf"
        pad = sla_pdf_op(pdf_bytes, bestandsnaam)
        print(f"\nPDF opgeslagen: {pad}")


if __name__ == "__main__":
    main()
