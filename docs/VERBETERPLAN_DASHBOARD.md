# Verbeterplan Dashboard Schriftelijke Vragen
## Gebaseerd op component.gallery — 60 componenten, 95 design systems

---

## Analyse huidige situatie

Het dashboard bevat nu: header, filterbar (4 `<select>`-elementen + zoekveld),
5 KPI-kaarten, 4 Chart.js-grafieken en een sorteerbare datatable met paginering.

Onderstaand plan koppelt concrete verbeteringen aan bewezen UI-componenten uit
component.gallery, geordend op prioriteit.

---

## Prioriteit 1 — Kritieke UX-gaps (doen vóór publicatie)

### 1.1 Skeleton loading state
**Component:** [Skeleton](https://component.gallery/components/skeleton/)
**Probleem nu:** De tabel toont één tekstrij "Data wordt geladen…" terwijl de
JSON (≈1 MB) opgehaald wordt. KPI-kaarten en grafieken staan leeg met `—`.
**Verbetering:**
- Render grijs-geanimeerde placeholders voor KPI-waarden (3 blokjes per kaart)
- Render 10 skeletonrijen in de tabel met placeholders in elke cel
- Vervang chartcontainers door een pulserend grijs vlak
- Na laden: smooth swap naar echte content (geen flikkering)

```
Hoe:  CSS-klasse .skeleton { background: linear-gradient(90deg,
      #EFF4F6 25%, #C8D6DB 50%, #EFF4F6 75%); animation: shimmer 1.5s infinite; }
      Voeg toe aan alle id-elementen (kpiTotaal, tableBody, etc.) vóór fetch().
```

### 1.2 Empty State
**Component:** [Empty state](https://component.gallery/components/empty-state/)
**Probleem nu:** Geen resultaten toont alleen de tekst "Geen vragen gevonden met
deze filters." — passief, geen actie.
**Verbetering:**
- Illustratie (eenvoudige SVG — vergrootglas of lege inbox)
- Koptekst: "Geen vragen gevonden"
- Subtekst: welke filters actief zijn
- Actieknop: **"Wis alle filters"** (directe link naar resetBtn)

```
Richtlijn component.gallery: "Always provide an alternative action rather than
passive messaging."
```

### 1.3 Skip Link
**Component:** [Skip link](https://component.gallery/components/skip-link/)
**Probleem nu:** Toetsenbordgebruikers moeten de volledige header + filterbar
doorloopen om de tabel te bereiken.
**Verbetering:**
- Eerste element in `<body>`: `<a class="skip-link" href="#main">Ga naar inhoud</a>`
- Alleen zichtbaar bij `:focus` (opacity transitie)
- Voldoet aan WCAG 2.4.1 (Bypass Blocks)

### 1.4 Alert — informatieve banner over tussenberichten
**Component:** [Alert](https://component.gallery/components/alert/)
**Probleem nu:** De noot over tussenberichten/antwoorden staat alleen in de footer
(kleine grijze tekst, niet opvallend).
**Verbetering:**
- Sluitbare informatie-alert direct boven de tabel:
  "ℹ️ Tussenberichten en antwoorden staan op de portaalpagina van elke vraag.
   Klik op een BB-nummer of titel om de portaalpagina te openen."
- Kleur: lichtblauw (informatief), niet waarschuwend
- `role="note"` + `aria-live="polite"`
- Sluitknop met `aria-label="Melding sluiten"`, voorkeur opgeslagen in
  `localStorage`

---

## Prioriteit 2 — Filterverbeteringen

### 2.1 Combobox voor partijfilter
**Component:** [Combobox](https://component.gallery/components/combobox/)
**Probleem nu:** `<select>` met 30+ partijen is onhandig — gebruikers moeten
scrollen door een lange lijst.
**Verbetering:**
- Vervang partij-`<select>` door een combobox (text-input + gefilterde dropdown)
- Typen "Groen" → toont direct "GroenLinks", "PvdA/GroenLinks", etc.
- Keyboard: pijltjestoetsen navigeren, Enter selecteert, Escape sluit
- ARIA: `role="combobox"`, `aria-expanded`, `aria-autocomplete="list"`,
  `aria-activedescendant`
- Geen externe library nodig — implementeerbaar in ≈80 regels vanilla JS

```
Richtlijn component.gallery: "Use for substantial option lists where filtering
reduces cognitive load."
```

### 2.2 Segmented Control voor statusfilter
**Component:** [Segmented control](https://component.gallery/components/segmented-control/)
**Probleem nu:** Status is een dropdown met slechts 3 opties — overkill voor zo
weinig keuzes, visueel minder duidelijk.
**Verbetering:**
- Vervang de `<select id="statusFilter">` door drie knoppen:
  `[Alle]  [Beantwoord]  [Nog open]`
- Actieve optie: groene achtergrond + wit (Rotterdam stijl)
- `role="group"` + `aria-label="Filter op status"` op de container
- Elke knop: `aria-pressed="true/false"`
- Responsief: krimpt op mobiel tot volledige breedte

### 2.3 Actieve filter-badges (chips)
**Component:** [Badge](https://component.gallery/components/badge/)
**Probleem nu:** Gebruiker ziet niet welke filters actief zijn zonder alle
dropdowns te bekijken.
**Verbetering:**
- Toon actieve filters als chips/badges onder de filterbar:
  `GroenLinks ×`  `2024 ×`  `Nog open ×`
- Klikken op `×` verwijdert die filter
- Leeg als alle filters op standaard staan
- `aria-label="Verwijder filter: GroenLinks"` per chip

```
Richtlijn component.gallery: "Use badges for metadata display and state
communication with concise text."
```

---

## Prioriteit 3 — Tabelverbeteringen

### 3.1 Detailpaneel (Drawer/Modal) per vraag
**Component:** [Modal](https://component.gallery/components/modal/) /
[Drawer](https://component.gallery/components/drawer/)
**Probleem nu:** Klikken op een rij opent direct de externe portaalpagina in een
nieuw tabblad — gebruiker verlaat het dashboard.
**Verbetering:**
- Klikken op een rij opent een **drawer** (zijpaneel van rechts) met:
  - BB-nummer + volledige titel
  - Partij, raadslid, beleidsveld
  - Datum ingediend / datum beantwoord
  - Doorlooptijd (prominent, met kleurcode)
  - Stand van zaken (als die beschikbaar is)
  - Knop: "Open op portaal →" (voor tussenberichten + antwoorden)
- Drawer sluit met Escape, klik buiten, of sluitknop
- Focus trap: Tab-cyclus binnen drawer (`aria-modal="true"`)
- Focus keert terug naar de tabelrij na sluiten

```
Richtlijn component.gallery: "Keep content task-focused with obvious close
mechanism. Use for focused content presentation before accessing full resource."
```

### 3.2 Tooltip op doorlooptijdkolom
**Component:** [Tooltip](https://component.gallery/components/tooltip/)
**Probleem nu:** Kleuren groen/oranje/rood zijn aanwezig, maar de betekenis is
niet uitgelegd in de UI (alleen in een HTML `title`-attribuut, niet toegankelijk
op touch).
**Verbetering:**
- Info-icoon `ⓘ` naast de kolomkop "Doorlooptijd"
- Hover/focus toont tooltip:
  "🟢 ≤ 42 d — binnen 6 weken  🟠 43–84 d — 6–12 weken  🔴 > 84 d — meer dan 12 weken"
- `role="tooltip"` + `aria-describedby` op de kolomkop
- Positie: boven de kolomkop, zichtbaar op focus (niet alleen hover)

```
Richtlijn component.gallery: "Keep content brief and single-concept.
Don't rely on hover-only triggers for touch devices."
```

### 3.3 Inline progress bar voor doorlooptijd
**Component:** [Progress bar](https://component.gallery/components/progress-bar/)
**Probleem nu:** Doorlooptijd is alleen een getal in dagen — moeilijk om snel te
scannen en te vergelijken tussen rijen.
**Verbetering:**
- Voeg een dunne horizontale balk (6px hoogte) toe ónder het dagenaantal
- Breedte = doorlooptijd / 180 dagen (max cap voor visualisatie)
- Kleur volgt hetzelfde schema als het getal (groen/oranje/rood)
- `role="progressbar"` + `aria-valuenow` + `aria-valuemax="180"` +
  `aria-label="{n} van max. 180 dagen"`
- Geeft instant visuele vergelijking tussen rijen

### 3.4 Rijkere badge voor status
**Component:** [Badge](https://component.gallery/components/badge/)
**Probleem nu:** Badges tonen alleen "Beantwoord" / "Nog open" in tekst.
**Verbetering:**
- Voeg een icoontje toe voor snellere scanbaarheid:
  `✓ Beantwoord` (groen) / `⏳ Nog open` (roze)
- Combineer badge met doorlooptijdkleur voor open vragen die lang lopen:
  `⚠ Nog open — 143 d` (rood, voor vragen > 84 dagen open)
- Zorg dat kleur nooit de enige indicator is (`aria-label` bevat de volledige
  betekenis)

---

## Prioriteit 4 — Navigatiestructuur & weergaven

### 4.1 Tabs voor hoofd­navigatie
**Component:** [Tabs](https://component.gallery/components/tabs/)
**Reden:** Het dashboard groeit; samenvatting en detailtabel zijn nu gecombineerd
op één lange pagina.
**Verbetering — 3 tabbladen:**

| Tab | Inhoud |
|-----|--------|
| **Overzicht** | KPI-kaarten + 4 grafieken (huidige bovenkant) |
| **Vragen** | Filterbar + datatable (huidige onderkant) |
| **Per partij** | Tabel met partijstatistieken (totaal, beantwoord, open, gem. doorlooptijd) |

- ARIA: `role="tablist"`, `role="tab"`, `role="tabpanel"`, `aria-selected`
- Keyboard: pijltjestoetsen wisselen tab, Tab verlaat de tablist
- URL-hash bijhouden (`#overzicht`, `#vragen`, `#per-partij`) zodat delen werkt

```
Richtlijn component.gallery: "The main benefit of tabs is that they allow a
large amount of information to be displayed in a limited space."
```

### 4.2 Accordion voor filterbar op mobiel
**Component:** [Accordion](https://component.gallery/components/accordion/)
**Probleem nu:** Op mobiel (<600px) neemt de filterbar veel ruimte in beslag en
vouwt niet samen.
**Verbetering:**
- Op schermen < 768px: filterbar wordt een accordion
  `▶ Filters (3 actief)` → klikken ontvouwt alle filteropties
- Badge met actief-aantal op de accordeonkop
- `aria-expanded`, `aria-controls` voor toegankelijkheid

---

## Prioriteit 5 — Meldingen & feedback

### 5.1 Toast-melding bij filters wissen
**Component:** [Toast](https://component.gallery/components/toast/)
**Verbetering:**
- Na klikken op "Wis filters": toast rechtsonder:
  "Filters gewist — alle 1.789 vragen zichtbaar"
- Verdwijnt automatisch na 4 seconden (of handmatig te sluiten)
- `role="status"` + `aria-live="polite"`
- Geen toast bij élke filterwijziging — alleen bij expliciete acties

### 5.2 Spinner bij herlaad-actie (toekomst)
**Component:** [Spinner](https://component.gallery/components/spinner/)
**Reden:** Als de data ooit dynamisch wordt ververst (bijv. via een "Ververs
data"-knop), is een laad-indicator nodig.
**Verbetering:**
- Kleine inline spinner naast de "Ververs"-knop tijdens fetch
- `aria-label="Data wordt geladen"` + `role="status"`
- Niet blokkend (geen overlay)

---

## Prioriteit 6 — Toegankelijkheid & kwaliteit (WCAG 2.1 AA)

### 6.1 Kolom-zichtbaarheid toggle
**Component:** [Toggle](https://component.gallery/components/toggle/) /
[Dropdown menu](https://component.gallery/components/dropdown-menu/)
**Verbetering:**
- Knop "Kolommen ▾" boven de tabel opent een dropdown met checkboxes per kolom
- Gebruiker kan "Raadslid", "Beleidsveld" of "Doorlooptijd" verbergen
- Voorkeur opgeslagen in `localStorage`

### 6.2 Datum-invoer voor periode-filter
**Component:** [Date input](https://component.gallery/components/date-input/) /
[Datepicker](https://component.gallery/components/datepicker/)
**Verbetering:**
- Vervang het jaar-dropdown door een "Van — Tot" datumbereik
- Twee `<input type="date">` velden met goede label-koppeling
- Valideert: begindatum ≤ einddatum

### 6.3 Verbeterde paginering
**Component:** [Pagination](https://component.gallery/components/pagination/)
**Probleem nu:** Huidige paginering heeft geen "Ga naar pagina"-invoer en geen
info over paginagrootte.
**Verbetering:**
- Toon "Rijen per pagina: [25 ▾]" (opties: 10, 25, 50, 100)
- Toon "Pagina 3 van 72" als tekst (screenreader-vriendelijk)
- `aria-label="Pagina {n} van {total}"` per paginaknop

---

## Samenvatting prioriteiten

| # | Verbetering | Component.gallery | Prioriteit | Inspanning |
|---|-------------|------------------|-----------|------------|
| 1.1 | Skeleton loading | Skeleton | ⬛ Kritiek | Klein |
| 1.2 | Empty state met actie | Empty state | ⬛ Kritiek | Klein |
| 1.3 | Skip link | Skip link | ⬛ Kritiek | Minimaal |
| 1.4 | Informatieve alert | Alert | 🔴 Hoog | Klein |
| 2.1 | Combobox partijfilter | Combobox | 🔴 Hoog | Gemiddeld |
| 2.2 | Segmented control status | Segmented control | 🔴 Hoog | Klein |
| 2.3 | Actieve filter-chips | Badge | 🔴 Hoog | Gemiddeld |
| 3.1 | Detailpaneel (drawer) | Modal / Drawer | 🟠 Gemiddeld | Groot |
| 3.2 | Tooltip doorlooptijd | Tooltip | 🟠 Gemiddeld | Klein |
| 3.3 | Inline progress bar | Progress bar | 🟠 Gemiddeld | Klein |
| 3.4 | Rijkere status-badge | Badge | 🟠 Gemiddeld | Klein |
| 4.1 | Tabs hoofdnavigatie | Tabs | 🟡 Laag | Groot |
| 4.2 | Accordion mobiel | Accordion | 🟡 Laag | Gemiddeld |
| 5.1 | Toast bij filters wissen | Toast | 🟡 Laag | Klein |
| 6.1 | Kolom-toggle | Toggle / Dropdown | 🟡 Laag | Gemiddeld |
| 6.2 | Datumbereik-filter | Date input | 🟡 Laag | Gemiddeld |
| 6.3 | Paginering verbeteren | Pagination | 🟡 Laag | Klein |

---

*Bron: [component.gallery](https://component.gallery) — 60 componenten,
95 design systems, 2.676 voorbeelden.*
