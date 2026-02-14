#!/usr/bin/env python3
"""Haal alle raadsvoorstellen op van gemeenteraad.rotterdam.nl en sla ze op als Excel."""

import urllib.request
import urllib.parse
import json
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

API_URL = "https://gemeenteraad.rotterdam.nl/Reports/GetReportData/4a6cb9e4-2668-4729-852a-ddb3b3ea90d3"
PAGE_SIZE = 100

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
]


def fetch_page(draw, start, length):
    params = f"draw={draw}&start={start}&length={length}&order[0][column]=3&order[0][dir]=desc&search[value]=&search[regex]=false&{COLUMNS_PARAM}"
    data = params.encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all():
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
        print(f"  Opgehaald: {len(all_records)}/{total}")

        if len(all_records) >= total or len(records) == 0:
            break

        start += PAGE_SIZE
        draw += 1

    return all_records


def create_excel(records, filename):
    wb = Workbook()
    ws = wb.active
    ws.title = "Raadsvoorstellen"

    # Styles
    header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="00674A", end_color="00674A", fill_type="solid")  # Rotterdam groen
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_alignment = Alignment(vertical="top", wrap_text=True)
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
            cell = ws.cell(row=row_idx, column=col_idx, value=record.get(key, ""))
            cell.alignment = cell_alignment
            cell.border = thin_border

    # Freeze top row
    ws.freeze_panes = "A2"

    # Auto-filter
    ws.auto_filter.ref = f"A1:G{len(records) + 1}"

    wb.save(filename)
    print(f"Excel bestand opgeslagen: {filename} ({len(records)} rijen)")


if __name__ == "__main__":
    records = fetch_all()
    create_excel(records, "raadsvoorstellen.xlsx")
