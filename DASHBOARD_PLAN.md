# Dashboard Schriftelijke Vragen Rotterdam — Implementatieplan

## Doel

Een statisch, interactief webdashboard dat alle schriftelijke vragen van de
Rotterdamse gemeenteraad (2022–2026) visueel presenteert in de officiële
huisstijl van de gemeente Rotterdam. Het dashboard werkt volledig zonder
server: één HTML-bestand dat de JSON-data inlaadt en live filtert/zoekt.

---

## Huisstijl gemeente Rotterdam

Gebaseerd op `onzestijl.rotterdam.nl`:

### Kleuren

| Token              | Hex       | Gebruik                              |
|--------------------|-----------|--------------------------------------|
| Groen primair      | `#00811F` | Koppen, links, accenten, header      |
| Groen donker       | `#005F16` | Hover-states, actieve elementen      |
| Roze primair       | `#C93675` | CTA-knoppen, badges "open"           |
| Roze donker        | `#A12B5E` | Knop-borders                         |
| Tekstgrijs         | `#404B4F` | Bodytekst, tabelinhoud               |
| Tertiair grijs     | `#657B7B` | Subtekst, labels                     |
| Licht blauw-grijs  | `#EFF4F6` | Achtergrond kaarten, zebra-rijen     |
| Wit                | `#FFFFFF` | Achtergrond pagina, knoppen op groen |
| Rood waarschuwing  | `#B53322` | Foutmeldingen, aandachtssignalen     |

### Typografie

- **Primair**: `Bolder` (custom, geladen via CDN of self-hosted)
- **Fallback**: `Space Grotesk`, `system-ui`, `sans-serif`

| Niveau | Grootte | Gewicht |
|--------|---------|---------|
| H1     | 48px    | 900     |
| H2     | 32px    | 100     |
| H3     | 24px    | 100     |
| Body   | 16px    | 100     |
| Label  | 14px    | 700     |

### Vormgeving

- **Border-radius**: 0px — harde hoeken (kenmerkend voor Rotterdam)
- **Schaduw**: subtiel (`0 2px 8px rgba(0,0,0,.08)`)
- **Logo**: Rotterdam-logo (groene R met Maas) linksboven in header

---

## Architectuur

```
dashboard/
├── index.html          ← Enkel HTML-bestand (alles-in-één)
├── style.css           ← Rotterdam huisstijl + dashboard layout
├── app.js              ← Filter, zoek, grafieken, tabel
└── data/
    └── vragen.json     ← Gegenereerd door generate_json.py

generate_json.py        ← Converteert schriftelijke_vragen_compleet.xlsx → JSON
```

Geen frameworks, geen build-stap. Afhankelijkheden via CDN:
- **Chart.js 4** — grafieken
- **Google Fonts / Bunny Fonts** — Space Grotesk als Bolder-fallback

---

## Paginalayout

```
┌────────────────────────────────────────────────────┐
│  [Rotterdam logo]  Schriftelijke Vragen Raad       │  ← Header (#00811F)
├────────────────────────────────────────────────────┤
│  [Zoekbalk]  [Partij ▼]  [Jaar ▼]  [Status ▼]     │  ← Filterbar
├──────────┬──────────┬──────────┬────────────────────┤
│ 1.789    │  68%     │  573     │  Leefbaar Rotterdam │  ← KPI-kaarten
│ Vragen   │ Beantw.  │  Open    │  Meest actief       │
├──────────┴──────────┴──────────┴────────────────────┤
│  [Bar: per jaar]           [Donut: open vs beantw.] │  ← Grafieken rij 1
├────────────────────────────────────────────────────┤
│  [Horizontale bar: vragen per partij]               │  ← Grafiek rij 2
├────────────────────────────────────────────────────┤
│  [Lijndiagram: vragen per kwartaal]                 │  ← Grafiek rij 3
├────────────────────────────────────────────────────┤
│  Tabel: BB-nr | Titel | Partij | Datum | Status ... │  ← Datatable
│  [< 1 2 3 ... >]                                    │  ← Paginering
└────────────────────────────────────────────────────┘
```

---

## Componenten

### 1. Header
- Achtergrond: `#00811F`
- Rotterdam-logo (wit) links
- Titel "Schriftelijke vragen gemeenteraad" rechts in wit
- Ondertitel: geselecteerde periode + live-teller gefilterde vragen

### 2. Filterbar
- **Zoekbalk**: real-time zoeken op titel en BB-nummer
- **Partij**: dropdown met alle partijen (gesorteerd op aantal vragen)
- **Jaar**: 2022 / 2023 / 2024 / 2025 / 2026 / Alle jaren
- **Status**: Alle / Beantwoord / Nog open
- **Beleidsveld**: dropdown
- **Reset**-knop: wist alle filters

Alle filters werken cumulatief en updaten tegelijk KPI's, grafieken én tabel.

### 3. KPI-kaarten (4 stuks)
Grote getal bovenaan, label eronder. Achtergrond wit, groene bovenbalk van 4px.

| Kaart | Waarde | Logica |
|-------|--------|--------|
| Totaal vragen | n | Gefilterde selectie |
| % Beantwoord | n% | datecompleted aanwezig |
| Nog open | n | Geen datecompleted |
| Actieve partij | naam | Meeste vragen in selectie |

### 4. Grafieken (Chart.js)

#### Grafiek A — Vragen per jaar (staafdiagram)
- X-as: jaren 2022–2026
- Y-as: aantal vragen
- Kleur: `#00811F` (beantwoord) + `#C93675` (open) gestapeld
- Reageert op partij-/statusfilter

#### Grafiek B — Open vs beantwoord (donutdiagram)
- Segmenten: groen (beantwoord) + roze (open)
- Cijfer in het midden: totaal

#### Grafiek C — Vragen per partij (horizontale balk)
- Top 10 partijen op aantal vragen
- Gesorteerd aflopend
- Kleur: `#00811F`

#### Grafiek D — Vragen per kwartaal (lijndiagram)
- X-as: Q1 2022 t/m Q4 2026
- Y-as: ingediende vragen
- Lijn: `#00811F`, fill lichtgroen

### 5. Datatable
Kolommen: BB-nummer | Titel | Partij | Datum ingediend | Status | Beleidsveld

- **BB-nummer**: klikbare link naar het portaal (opens in new tab)
- **Status**: badge "Beantwoord" (groen) of "Open" (roze), 0px radius
- **Paginering**: 25 rijen per pagina, prev/next en paginanummers
- **Sortering**: klik op kolomkop wisselt asc/desc
- **Hover**: rij-highlight met `#EFF4F6`

---

## Stap-voor-stap implementatie

### Stap 1 — `generate_json.py`
Python-script dat `schriftelijke_vragen_compleet.xlsx` inleest en omzet
naar `dashboard/data/vragen.json`. Velden per record:

```json
{
  "id": "BB22001",
  "titel": "...",
  "partij": "Leefbaar Rotterdam",
  "raadslid": "...",
  "datum_ingediend": "2022-03-15",
  "datum_beantwoord": "2022-05-01",
  "beleidsveld": "Veiligheid",
  "portefeuillehouder": "...",
  "commissie": "...",
  "omschrijving": "...",
  "stand_van_zaken": "...",
  "doc_naam": "...",
  "doc_url": "...",
  "portaal_url": "..."
}
```

### Stap 2 — `style.css`
- CSS-variabelen voor alle Rotterdam-tokens
- Responsive grid (CSS Grid + Flexbox)
- Mobiel-vriendelijk (breakpoint 768px)
- Print-stylesheet (geen grafieken, tabel uitgedrukt)

### Stap 3 — `app.js`
Structuur:
```
loadData()          ← fetch vragen.json
applyFilters()      ← filtert data op alle actieve filters
renderKPIs()        ← update 4 kaarten
renderCharts()      ← (her)tekent Chart.js grafieken
renderTable()       ← vult tabel + paginering
bindEvents()        ← alle event listeners
```

### Stap 4 — `index.html`
Semantische HTML5 structuur. Alle stijlen en scripts extern.
`<noscript>`-melding voor gebruikers zonder JavaScript.

---

## Dataflow

```
schriftelijke_vragen_compleet.xlsx
        ↓  generate_json.py
dashboard/data/vragen.json          (eenmalig genereren)
        ↓  fetch() in app.js
Geheugen (JavaScript array)
        ↓  applyFilters()
Gefilterde array
        ↓
  renderKPIs() + renderCharts() + renderTable()
```

---

## Toegankelijkheid & kwaliteit

- WCAG 2.1 AA: contrastverhouding groen/wit = 4.6:1 (voldoet)
- `aria-label` op alle interactieve elementen
- Toetsenbord-navigeerbaar (tab-volgorde, focus-ring in groen)
- `lang="nl"` op `<html>`
- Geen externe tracking of cookies

---

## Bestanden samenvatting

| Bestand | Beschrijving |
|---------|-------------|
| `generate_json.py` | Converteert Excel → JSON |
| `dashboard/index.html` | Enkel-pagina dashboard |
| `dashboard/style.css` | Rotterdam huisstijl CSS |
| `dashboard/app.js` | Dashboard logica + Chart.js |
| `dashboard/data/vragen.json` | Gegenereerde data (niet in git) |

---

## Na implementatie

1. Open `dashboard/index.html` lokaal in browser (of via een eenvoudige
   HTTP-server: `python3 -m http.server 8000`)
2. Draai `generate_json.py` opnieuw na elke nieuwe Excel-export om de
   data te verversen
3. Optioneel: deploy als GitHub Pages voor online toegang
