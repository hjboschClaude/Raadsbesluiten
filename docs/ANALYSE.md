# Analyse: gemeenteraad.rotterdam.nl - Raadsvoorstellen

## Platform

De website draait op het **iBabs Publieksportaal**, een vergadermanagement-systeem van iBabs (onderdeel van MSI). Het is een ASP.NET MVC-applicatie die server-side rendered HTML levert, met client-side data-loading via jQuery DataTables.

## Architectuur overzicht

```
Browser
  │
  ├─ GET /Reports/Details/{listId}     ← Server-side rendered HTML pagina
  │     (bevat filters, lege tabel, en DataTables configuratie als data-attributen)
  │
  ├─ POST /Reports/GetReportData/{listId}   ← AJAX API call (DataTables server-side)
  │     (retourneert JSON met raadsvoorstellen)
  │
  └─ GET /Reports/Item/{entryId}       ← Detail pagina per raadsvoorstel
        └─ GET /Reports/Document/{entryId}?documentId={docId}  ← Document download
```

## Hoe de pagina werkt (stap voor stap)

### 1. Initiële page load

De browser laadt `GET /Reports/Details/4a6cb9e4-2668-4729-852a-ddb3b3ea90d3`.
De server retourneert complete HTML met:

- **Navigatie en filters** (server-side rendered)
- **Een lege tabel** (`<table id="overzichten-data">`) met alleen headers en een loading GIF
- **DataTables configuratie** als `data-*` attributen op het `<table>` element
- **JavaScript bundles** onderaan de pagina

### 2. JavaScript initialisatie

De pagina laadt vier JavaScript-bestanden:

| Script | Inhoud |
|--------|--------|
| `/scripts/main?v=...` | jQuery 3.6.3 + DataTables 2.3.3 + iBabs custom code (~530KB bundel) |
| `/scripts/localization/nl?v=...` | Nederlandse vertalingen voor DataTables |
| `/Scripts/views/layout.js` | Roept `ibabs.core.initialize()` aan |
| `/lib/duetds-datepicker/duet.esm.js` | Duet Date Picker web component voor datumfilters |

Bij initialisatie roept `ibabs.core.initialize()` o.a. `ibabs.dataTables.init()` aan, die alle `<table class="table-datatable">` elementen vindt en initialiseert.

### 3. DataTables configuratie (via data-attributen)

De tabel bevat alle configuratie als HTML data-attributen:

```html
<table id="overzichten-data"
       class="table table-datatable table-clickable"
       data-server-side="true"
       data-ajax='{"url":"/Reports/GetReportData/4a6cb9e4-2668-4729-852a-ddb3b3ea90d3","type":"POST"}'
       data-columns='[
         {"data":"beleidsveld","name":"beleidsveld"},
         {"data":"externalid","name":"externalid"},
         {"data":"title","name":"title","searchable":false},
         {"data":"registrationdate","name":"registrationdate"},
         {"data":"portefeuillehouder","name":"portefeuillehouder"},
         {"data":"aanwie","name":"aanwie","searchable":false},
         {"data":"behandeladvies","name":"behandeladvies"}
       ]'
       data-order='[[3,"desc"]]'
       data-page-length="50"
       data-paging="true"
       data-state-save="true"
       data-item-url="/Reports/Item/_id_">
```

Key settings:
- **Server-side processing**: DataTables vraagt data op bij de server per pagina
- **POST methode**: Alle requests zijn POST (niet GET)
- **Standaard sortering**: Kolom 3 (`registrationdate`) aflopend
- **Paginering**: 50 items per pagina
- **State save**: Filter- en sorteerstatus wordt in localStorage bewaard

### 4. De API call (data laden)

DataTables stuurt een `POST` request naar:

```
POST /Reports/GetReportData/4a6cb9e4-2668-4729-852a-ddb3b3ea90d3
Content-Type: application/x-www-form-urlencoded
```

#### Request parameters (DataTables server-side protocol)

| Parameter | Beschrijving | Voorbeeld |
|-----------|-------------|-----------|
| `draw` | Sequentienummer (tegen race conditions) | `1` |
| `start` | Offset voor paginering | `0`, `50`, `100`, ... |
| `length` | Aantal records per pagina | `50` |
| `order[0][column]` | Kolom-index om op te sorteren | `3` (= registrationdate) |
| `order[0][dir]` | Sorteerrichting | `desc` of `asc` |
| `search[value]` | Globale zoekterm | `""` |
| `columns[N][data]` | Kolomnaam | `beleidsveld` |
| `columns[N][name]` | Kolomnaam voor filtering | `beleidsveld` |
| `columns[N][search][value]` | Filterwaarde per kolom | GUID of tekst |

#### Response formaat (JSON)

```json
{
  "draw": 1,
  "recordsTotal": 723,
  "recordsFiltered": 723,
  "data": [
    {
      "DT_RowId": "d08e2f1b-1b6f-49b9-a58e-97902e9c4ed4",
      "beleidsveld": "Bestuur",
      "externalid": "26bb001376",
      "title": "Het voorstel van het presidium tot vaststelling van ...",
      "registrationdate": "12-02-2026",
      "portefeuillehouder": "C.J. Schouten (Burgemeester)",
      "aanwie": "Gemeenteraad",
      "behandeladvies": "Direct doorgeleiden naar de raad 26-02-2026"
    }
  ]
}
```

| Veld | Beschrijving |
|------|-------------|
| `DT_RowId` | Unieke GUID van het raadsvoorstel (wordt ook het `id` attribuut van de `<tr>`) |
| `beleidsveld` | Beleidsveld/categorie |
| `externalid` | BB-nummer (uniek referentienummer) |
| `title` | Titel van het raadsvoorstel |
| `registrationdate` | Datum ontvangen (formaat: `dd-MM-yyyy`) |
| `portefeuillehouder` | Verantwoordelijke wethouder/burgemeester |
| `aanwie` | Aan wie gericht |
| `behandeladvies` | Advies voor behandeling |
| `recordsTotal` | Totaal aantal records in de lijst |
| `recordsFiltered` | Aantal records na filtering |

### 5. Filtering

De sidebar bevat filters die als `data-filter-for` attributen gekoppeld zijn aan kolommen:

| Filter | Type | Kolomnaam | Werking |
|--------|------|-----------|---------|
| Beleidsveld | `<select>` dropdown | `beleidsveld` | Filtert op GUID-waarde van het beleidsveld |
| BB-nummer | `<input type="text">` | `externalid` | Vrije tekstzoeking |
| Datum ontvangen | `<duet-date-picker>` (van/tot) | `registrationdate` | Datumbereik filter |
| Portefeuillehouder | `<select>` dropdown | `portefeuillehouder` | Filtert op GUID-waarde |
| Behandeladvies | `<input type="text">` | `behandeladvies` | Vrije tekstzoeking |

Bij wijziging van een filter leest de JavaScript de waarde uit en zet die in `columns[N][search][value]`, waarna DataTables een nieuw POST request stuurt.

Voor dropdown filters wordt de **GUID** van de geselecteerde optie meegegeven (niet de tekst). Bijvoorbeeld voor portefeuillehouder "A. Aboutaleb": `columns[4][search][value]=c249028f-daf6-466d-8462-c659bb52e819`.

### 6. Klikken op een rij (detail)

Bij klik op een tabelrij navigeert de browser naar:

```
/Reports/Item/{DT_RowId}
```

Bijvoorbeeld: `/Reports/Item/d08e2f1b-1b6f-49b9-a58e-97902e9c4ed4`

Dit is geconfigureerd via `data-item-url="/Reports/Item/_id_"` op de tabel, waarbij `_id_` vervangen wordt door het `id` attribuut van de `<tr>` (= `DT_RowId` uit de API response).

Op de detailpagina zijn bijbehorende documenten beschikbaar via:

```
/Reports/Document/{entryId}?documentId={documentId}
```

## Alle beschikbare lijsten (overzichten)

Elke lijst heeft een eigen GUID en is toegankelijk via dezelfde `/Reports/Details/{listId}` structuur:

| Lijst | GUID (listId) |
|-------|---------------|
| Actualiteiten | `04546df6-fe14-4b73-92f4-a01c16587aab` |
| Amendementen | `f7307a5e-0e03-4360-a88a-c0b56202c747` |
| Besluiten | `ed13ec46-0027-4992-b3ac-eaa1d8dcbdab` |
| Brieven B&W | `a164b9e0-5669-4508-8669-fc94780c5131` |
| Burgerbrieven | `cc77e6ed-9a79-47c8-aed9-98a87beb9e67` |
| Initiatiefvoorstellen | `f477a1ec-3ab8-472f-9d4f-a1cb60fa3b88` |
| Moties | `a61fab39-bc62-464f-968d-db31925a66e5` |
| Onderwerpdossiers | `dc6a4581-0738-4d0c-ad90-072868a13572` |
| Overige documenten t.b.v. de raad | `a2ff8862-fec4-4526-bf5c-f9565f3d0026` |
| **Raadsvoorstellen** | **`4a6cb9e4-2668-4729-852a-ddb3b3ea90d3`** |
| Schriftelijke vragen | `da9b533f-5f24-4f51-8567-19fe410f15d4` |
| Themapagina's | `50e491e0-ac55-43b1-b0aa-cf6557da3f81` |
| Toezeggingen | `32881df4-b70b-4ede-942c-d4135415883f` |
| Wijkraadadviezen | `85c7d75a-22d0-497e-ae8e-8d993f41ed32` |
| Archief raadsperiode 2018-2022 | `7e74e418-5882-42b5-8253-d28c2242c1ed` |

## Voorbeeld: API aanroepen met curl

### Alle raadsvoorstellen ophalen (eerste 5, gesorteerd op datum aflopend)

```bash
curl -X POST "https://gemeenteraad.rotterdam.nl/Reports/GetReportData/4a6cb9e4-2668-4729-852a-ddb3b3ea90d3" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d 'draw=1&start=0&length=5&order[0][column]=3&order[0][dir]=desc&columns[0][data]=beleidsveld&columns[0][name]=beleidsveld&columns[0][searchable]=true&columns[1][data]=externalid&columns[1][name]=externalid&columns[1][searchable]=true&columns[2][data]=title&columns[2][name]=title&columns[2][searchable]=false&columns[3][data]=registrationdate&columns[3][name]=registrationdate&columns[3][searchable]=true&columns[4][data]=portefeuillehouder&columns[4][name]=portefeuillehouder&columns[4][searchable]=true&columns[5][data]=aanwie&columns[5][name]=aanwie&columns[5][searchable]=false&columns[6][data]=behandeladvies&columns[6][name]=behandeladvies&columns[6][searchable]=true'
```

### Filteren op portefeuillehouder (Aboutaleb)

Voeg toe aan bovenstaande request:
```
&columns[4][search][value]=c249028f-daf6-466d-8462-c659bb52e819
```

### Paginering (pagina 2)

```
&start=50&length=50
```

### Alle records ophalen

Gebruik `length=-1` of itereer met `start=0,50,100,...` tot `start >= recordsTotal`.

## Technische stack samenvatting

| Component | Technologie |
|-----------|------------|
| Backend | ASP.NET MVC (iBabs Publieksportaal) |
| Frontend framework | jQuery 3.6.3 |
| Tabel component | DataTables 2.3.3 (server-side processing) |
| Datumkiezer | Duet Date Picker (web component) |
| Styling | Bootstrap 4 + custom iBabs CSS |
| API formaat | DataTables server-side protocol (POST, form-urlencoded) |
| Response formaat | JSON |
| Authenticatie | Geen (publiek toegankelijk) |
| i18n | i18next (Nederlandse vertalingen) |
