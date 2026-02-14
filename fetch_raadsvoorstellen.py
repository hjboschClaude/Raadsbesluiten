#!/usr/bin/env python3
"""Haal alle raadsvoorstellen op van gemeenteraad.rotterdam.nl en sla ze op als Excel."""

import urllib.request
import json
import re
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

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
    ("Beleidsveld", "beleidsveld", 25),
    ("Datum ontvangen", "registrationdate", 18),
    ("Portefeuillehouder", "portefeuillehouder", 35),
    ("Aan wie gericht", "aanwie", 20),
    ("Behandeladvies", "behandeladvies", 45),
    ("Hoofddocument", "hoofddocument_naam", 80),
    ("Hoofddocument URL", "hoofddocument_url", 50),
    ("Aantal bijlagen", "aantal_bijlagen", 15),
    ("Bijlagen", "bijlagen_tekst", 100),
]


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


def create_excel(records, filename):
    wb = Workbook()
    ws = wb.active
    ws.title = "Raadsvoorstellen"

    # Styles
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="00674A", end_color="00674A", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_alignment = Alignment(vertical="top", wrap_text=True)
    url_font = Font(name="Calibri", color="0563C1", underline="single", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"),
        right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"),
        bottom=Side(style="thin", color="D9D9D9"),
    )

    # Headers
    for col_idx, (header, _, width) in enumerate(EXCEL_COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
        ws.column_dimensions[cell.column_letter].width = width

    # Data
    for row_idx, record in enumerate(records, 2):
        for col_idx, (_, key, _) in enumerate(EXCEL_COLUMNS, 1):
            value = record.get(key, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = cell_alignment
            cell.border = thin_border

            # Maak URL-kolom klikbaar
            if key == "hoofddocument_url" and value:
                cell.hyperlink = value
                cell.font = url_font

    # Freeze top row
    ws.freeze_panes = "A2"

    # Auto-filter
    last_col = chr(ord("A") + len(EXCEL_COLUMNS) - 1)
    ws.auto_filter.ref = f"A1:{last_col}{len(records) + 1}"

    wb.save(filename)
    print(f"\nExcel bestand opgeslagen: {filename} ({len(records)} rijen)")


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

    print("\nStap 3: Excel genereren...")
    create_excel(records, "raadsvoorstellen.xlsx")
