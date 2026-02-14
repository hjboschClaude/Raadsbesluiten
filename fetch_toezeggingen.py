#!/usr/bin/env python3
"""Haal alle toezeggingen op van gemeenteraad.rotterdam.nl en sla ze op als Excel.

Voor openstaande toezeggingen worden ook de detailpagina's opgehaald om
beleidsveld, stand van zaken en afdoeningsstatus te extraheren.
"""

import urllib.request
import json
import re
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

BASE_URL = "https://gemeenteraad.rotterdam.nl"
LIST_ID = "32881df4-b70b-4ede-942c-d4135415883f"
API_URL = f"{BASE_URL}/Reports/GetReportData/{LIST_ID}"
PAGE_SIZE = 100
CONCURRENT_REQUESTS = 3  # Voorzichtig met rate limiting

COLUMNS_PARAM = "&".join([
    "columns[0][data]=externalid&columns[0][name]=externalid&columns[0][searchable]=true",
    "columns[1][data]=title&columns[1][name]=title&columns[1][searchable]=true",
    "columns[2][data]=registrationdate&columns[2][name]=registrationdate&columns[2][searchable]=true",
    "columns[3][data]=portefeuillehouder&columns[3][name]=portefeuillehouder&columns[3][searchable]=true",
    "columns[4][data]=commissie&columns[4][name]=commissie&columns[4][searchable]=true",
])


# --- HTTP helpers ---

def http_request(url, max_retries=4, timeout=30, data=None, headers=None):
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


# --- API data ophalen ---

def fetch_page(draw, start, length):
    params = (
        f"draw={draw}&start={start}&length={length}"
        f"&order[0][column]=2&order[0][dir]=desc"
        f"&search[value]=&search[regex]=false&{COLUMNS_PARAM}"
    )
    body = http_request(
        API_URL,
        data=params.encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{BASE_URL}/Reports/Details/{LIST_ID}",
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
            print(f"Totaal aantal toezeggingen: {total}")
        all_records.extend(result["data"])
        print(f"  Lijst opgehaald: {len(all_records)}/{total}")
        if len(all_records) >= total or len(result["data"]) == 0:
            break
        start += PAGE_SIZE
        draw += 1

    return all_records


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


def get_document_url(html):
    """Extraheer de PDF-document URL uit het Hoofddocument veld."""
    pattern = r'<dt[^>]*>\s*Hoofddocument\s*</dt>\s*<dd[^>]*>(.*?)</dd>'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return ""
    doc_link = re.search(r'href="(/Reports/Document/[^"]+)"', match.group(1))
    if doc_link:
        return f"{BASE_URL}{doc_link.group(1)}"
    return ""


def get_date_field(html, label):
    """Haal datumveld op."""
    value = get_text_field(html, label)
    # Soms zit er extra tekst bij, probeer alleen de datum te pakken
    date_match = re.search(r'\d{2}-\d{2}-\d{4}', value)
    if date_match:
        return date_match.group(0)
    return value


def fetch_item_details(record):
    """Haal detailpagina op voor een toezegging en extraheer statusvelden."""
    row_id = record["DT_RowId"]
    url = f"{BASE_URL}/Reports/Item/{row_id}"

    try:
        html = http_request(url)

        record["document_url"] = get_document_url(html)
        record["beleidsveld"] = get_list_field(html, "Beleidsveld")
        record["omschrijving"] = get_text_field(html, "Omschrijving")
        record["verwachte_datum_afdoening"] = get_date_field(html, "Verwachte datum afdoening")
        record["stand_van_zaken"] = get_text_field(html, "Stand van zaken")
        record["afgedaan"] = get_checkbox_field(html, "Afgedaan")
        record["datum_afgedaan"] = get_date_field(html, "Datum afgedaan")
        record["afdoeningsvoorstel_aanwezig"] = get_checkbox_field(html, "Afdoeningsvoorstel aanwezig")
        record["toelichting"] = get_text_field(html, "Toelichting")
        record["datum_tussenbericht"] = get_date_field(html, "Datum tussenbericht")
        record["detail_opgehaald"] = True

    except Exception as e:
        print(f"  FOUT bij {row_id} ({record.get('externalid', '')}): {e}", file=sys.stderr)
        for key in ["document_url", "beleidsveld", "omschrijving",
                     "verwachte_datum_afdoening", "stand_van_zaken", "afgedaan",
                     "datum_afgedaan", "afdoeningsvoorstel_aanwezig", "toelichting",
                     "datum_tussenbericht"]:
            record[key] = ""
        record["detail_opgehaald"] = False

    return record


def fetch_details_for_open(records):
    """Haal details op voor alle openstaande toezeggingen."""
    openstaand = [r for r in records if not r.get("_afgedaan_hint")]
    total = len(openstaand)
    print(f"  {total} openstaande toezeggingen gevonden, details ophalen...")
    completed = 0

    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        futures = {executor.submit(fetch_item_details, r): r for r in openstaand}
        for future in as_completed(futures):
            completed += 1
            if completed % 100 == 0 or completed == total:
                print(f"  Details opgehaald: {completed}/{total}")

    return records


def fetch_details_for_all(records):
    """Haal details op voor alle toezeggingen."""
    total = len(records)
    print(f"  {total} toezeggingen, details ophalen...")
    completed = 0

    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as executor:
        futures = {executor.submit(fetch_item_details, r): r for r in records}
        for future in as_completed(futures):
            completed += 1
            if completed % 200 == 0 or completed == total:
                print(f"  Details opgehaald: {completed}/{total}")

    return records


# --- Excel generatie ---

def make_styles():
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="00674A", end_color="00674A", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_alignment = Alignment(vertical="top", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )
    return {
        "header_font": header_font,
        "header_fill": header_fill,
        "header_alignment": header_alignment,
        "cell_alignment": cell_alignment,
        "thin_border": thin_border,
    }


def write_sheet(ws, columns, records, styles):
    """Schrijf data naar een werkblad."""
    for col_idx, (header, _, width) in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = styles["header_font"]
        cell.fill = styles["header_fill"]
        cell.alignment = styles["header_alignment"]
        cell.border = styles["thin_border"]
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    for row_idx, record in enumerate(records, 2):
        for col_idx, (_, key, _) in enumerate(columns, 1):
            value = record.get(key)
            if value is None:
                value = ""
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = styles["cell_alignment"]
            cell.border = styles["thin_border"]

    ws.freeze_panes = "A2"
    last_col = get_column_letter(len(columns))
    ws.auto_filter.ref = f"A1:{last_col}{len(records) + 1}"


def create_excel(records, filename):
    wb = Workbook()
    styles = make_styles()
    groen = Font(name="Calibri", color="1B5E20", bold=True)
    rood = Font(name="Calibri", color="B71C1C", bold=True)

    # Voeg url toe
    for r in records:
        r["url"] = f"{BASE_URL}/Reports/Item/{r['DT_RowId']}"

    # --- Blad 1: Alle toezeggingen ---
    ws1 = wb.active
    ws1.title = "Alle toezeggingen"
    alle_kolommen = [
        ("BB-nummer", "externalid", 16),
        ("Titel", "title", 60),
        ("Datum toezegging", "registrationdate", 17),
        ("Portefeuillehouder", "portefeuillehouder", 35),
        ("Commissie", "commissie", 40),
        ("Afgedaan", "afgedaan", 10),
        ("Datum afgedaan", "datum_afgedaan", 16),
        ("URL", "url", 50),
        ("Document", "document_url", 50),
    ]
    write_sheet(ws1, alle_kolommen, records, styles)

    # Kleur afgedaan kolom
    afgedaan_col = 6
    for row_idx, record in enumerate(records, 2):
        cell = ws1.cell(row=row_idx, column=afgedaan_col)
        if record.get("afgedaan") == "Ja":
            cell.font = groen
        elif record.get("afgedaan") == "Nee":
            cell.font = rood

    # --- Blad 2: Openstaande toezeggingen (detail) ---
    ws2 = wb.create_sheet("Openstaande toezeggingen")
    openstaand = [r for r in records if r.get("afgedaan") != "Ja"]

    detail_kolommen = [
        ("BB-nummer", "externalid", 16),
        ("Titel", "title", 55),
        ("Datum toezegging", "registrationdate", 17),
        ("Portefeuillehouder", "portefeuillehouder", 35),
        ("Beleidsveld", "beleidsveld", 22),
        ("Commissie", "commissie", 40),
        ("Verwachte afdoening", "verwachte_datum_afdoening", 18),
        ("Stand van zaken", "stand_van_zaken", 60),
        ("Datum tussenbericht", "datum_tussenbericht", 17),
        ("Afdoeningsvoorstel", "afdoeningsvoorstel_aanwezig", 16),
        ("Toelichting", "toelichting", 50),
        ("URL", "url", 50),
        ("Document", "document_url", 50),
    ]

    # Sorteer op portefeuillehouder, dan datum
    openstaand.sort(key=lambda r: (r.get("portefeuillehouder") or "", r.get("registrationdate") or ""))
    write_sheet(ws2, detail_kolommen, openstaand, styles)

    # --- Blad 3: Samenvatting per portefeuillehouder ---
    ws3 = wb.create_sheet("Per portefeuillehouder")

    ph_stats = {}
    for r in records:
        ph = r.get("portefeuillehouder", "") or "(onbekend)"
        if ph not in ph_stats:
            ph_stats[ph] = {"totaal": 0, "afgedaan": 0, "open": 0}
        ph_stats[ph]["totaal"] += 1
        if r.get("afgedaan") == "Ja":
            ph_stats[ph]["afgedaan"] += 1
        else:
            ph_stats[ph]["open"] += 1

    samenvatting_headers = [
        ("Portefeuillehouder", 35),
        ("Totaal", 12),
        ("Afgedaan", 12),
        ("Open", 12),
        ("% Afgedaan", 12),
    ]
    for col_idx, (header, width) in enumerate(samenvatting_headers, 1):
        cell = ws3.cell(row=1, column=col_idx, value=header)
        cell.font = styles["header_font"]
        cell.fill = styles["header_fill"]
        cell.alignment = styles["header_alignment"]
        cell.border = styles["thin_border"]
        ws3.column_dimensions[get_column_letter(col_idx)].width = width

    for row_idx, (ph, stats) in enumerate(sorted(ph_stats.items()), 2):
        pct = round(stats["afgedaan"] / stats["totaal"] * 100) if stats["totaal"] else 0
        values = [ph, stats["totaal"], stats["afgedaan"], stats["open"], f"{pct}%"]
        for col_idx, val in enumerate(values, 1):
            cell = ws3.cell(row=row_idx, column=col_idx, value=val)
            cell.alignment = styles["cell_alignment"]
            cell.border = styles["thin_border"]

    ws3.freeze_panes = "A2"
    ws3.auto_filter.ref = f"A1:E{len(ph_stats) + 1}"

    # --- Blad 4: Samenvatting per commissie ---
    ws4 = wb.create_sheet("Per commissie")

    com_stats = {}
    for r in records:
        com = r.get("commissie", "") or "(onbekend)"
        if com not in com_stats:
            com_stats[com] = {"totaal": 0, "afgedaan": 0, "open": 0}
        com_stats[com]["totaal"] += 1
        if r.get("afgedaan") == "Ja":
            com_stats[com]["afgedaan"] += 1
        else:
            com_stats[com]["open"] += 1

    com_headers = [
        ("Commissie", 50),
        ("Totaal", 12),
        ("Afgedaan", 12),
        ("Open", 12),
        ("% Afgedaan", 12),
    ]
    for col_idx, (header, width) in enumerate(com_headers, 1):
        cell = ws4.cell(row=1, column=col_idx, value=header)
        cell.font = styles["header_font"]
        cell.fill = styles["header_fill"]
        cell.alignment = styles["header_alignment"]
        cell.border = styles["thin_border"]
        ws4.column_dimensions[get_column_letter(col_idx)].width = width

    for row_idx, (com, stats) in enumerate(sorted(com_stats.items()), 2):
        pct = round(stats["afgedaan"] / stats["totaal"] * 100) if stats["totaal"] else 0
        values = [com, stats["totaal"], stats["afgedaan"], stats["open"], f"{pct}%"]
        for col_idx, val in enumerate(values, 1):
            cell = ws4.cell(row=row_idx, column=col_idx, value=val)
            cell.alignment = styles["cell_alignment"]
            cell.border = styles["thin_border"]

    ws4.freeze_panes = "A2"
    ws4.auto_filter.ref = f"A1:E{len(com_stats) + 1}"

    wb.save(filename)
    print(f"\nExcel bestand opgeslagen: {filename}")
    print(f"  Blad 'Alle toezeggingen': {len(records)} rijen")
    print(f"  Blad 'Openstaande toezeggingen': {len(openstaand)} rijen")
    print(f"  Blad 'Per portefeuillehouder': {len(ph_stats)} portefeuillehouders")
    print(f"  Blad 'Per commissie': {len(com_stats)} commissies")


# --- Main ---

CACHE_FILE = "toezeggingen_cache.json"


def save_cache(records):
    """Sla tussenresultaten op als JSON cache."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)
    print(f"  Cache opgeslagen: {CACHE_FILE} ({len(records)} records)")


def load_cache():
    """Laad tussenresultaten uit JSON cache."""
    import os
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            records = json.load(f)
        print(f"  Cache geladen: {len(records)} records uit {CACHE_FILE}")
        return records
    return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Toezeggingen ophalen en exporteren als Excel")
    parser.add_argument("--from-cache", action="store_true",
                        help="Gebruik cache van eerder opgehaalde data")
    args = parser.parse_args()

    if args.from_cache:
        records = load_cache()
        if not records:
            print("Geen cache gevonden, data wordt opnieuw opgehaald.")
            args.from_cache = False

    if not args.from_cache:
        print("Stap 1: Alle toezeggingen ophalen via API...")
        records = fetch_all_records()

        print(f"\nStap 2: Details ophalen voor alle toezeggingen...")
        fetch_details_for_all(records)
        save_cache(records)

    # Statistieken
    opgehaald = sum(1 for r in records if r.get("detail_opgehaald"))
    afgedaan = sum(1 for r in records if r.get("afgedaan") == "Ja")
    print(f"\n  Details succesvol opgehaald: {opgehaald}/{len(records)}")
    print(f"  Afgedaan: {afgedaan}")
    print(f"  Nog open: {len(records) - afgedaan}")

    print("\nStap 3: Excel genereren...")
    create_excel(records, "toezeggingen.xlsx")
