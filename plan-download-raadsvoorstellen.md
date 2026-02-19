# Plan: Download en classificeer alle raadsvoorstellen

## Doel

Een nieuw script `download_raadsvoorstellen.py` dat:
1. Alle 723 hoofddocumenten (PDFs) downloadt naar `raadsvoorstellen/`
2. De tekst extraheert en het "Gevraagd besluit" parseert
3. Op basis van de **inhoud** het besluittype en beleidsdomein bepaalt
4. Een uitgebreide Excel genereert met inhoud, gevraagde besluiten en categorisering

## Stappen

### Stap 1: Lijst ophalen en documenten identificeren
- Haal alle 723 raadsvoorstellen op via de lijst-API
- Haal per record de detailpagina op om het document-ID te verkrijgen
- Sla metadata + document-IDs op als tussenbestand (JSON cache)

### Stap 2: PDFs downloaden naar `raadsvoorstellen/`
- Download elke PDF via `/Document/View/{document_id}`
- Bestandsnaam: `[BB-nummer] Titel.pdf` (max 150 tekens)
- Sla over als bestand al bestaat (herstart-veilig)
- Parallel downloaden (3 workers) met rate limiting
- Verwachte grootte: ~500MB-1GB totaal

### Stap 3: Tekst extraheren en secties parsen
Per PDF:
- Extraheer tekst met pypdf
- Parse de standaardsecties uit de tekst:
  - **"Gevraagd besluit"** — alles tussen "Gevraagd besluit" en "Waarom dit voorstel"
  - **"Waarom dit voorstel"** — motivering
  - **"Relatie met coalitieakkoord"** — beleidscontext
  - **Cluster/Portefeuille** — metadata uit het document
- Sla geëxtraheerde tekst op in cache (JSON)

### Stap 4: Inhoud-gebaseerde classificatie
Verbeter de bestaande titelgebaseerde classificatie met documentinhoud:

**Besluittype** — gebruik "Gevraagd besluit" om te detecteren:
- "vast te stellen" → vaststelling
- "wijziging" → wijziging
- "krediet" / "budget" / "middelen" → financieel
- "te benoemen" → benoeming
- "zienswijze" → zienswijze
- "verordening" → verordening
- "geheimhouding op te heffen/leggen" → controle

**Beleidsdomein** — gebruik volledige tekst + "Relatie met coalitieakkoord":
- Zoek naar beleidstrefwoorden in de hele tekst (niet alleen titel)
- Gebruik "Cluster:" veld als aanvullend signaal (bijv. "Stadsontwikkeling",
  "Maatschappelijke Ontwikkeling")
- Gebruik "Portefeuille:" veld als bevestiging

Classificatielogica:
1. Eerst: inhoud "Gevraagd besluit" → besluittype
2. Dan: titelpatronen (bestaande logica als fallback)
3. Eerst: trefwoorden in volledige tekst → beleidsdomein
4. Dan: Cluster/Portefeuille veld → beleidsdomein
5. Tenslotte: origineel beleidsveld → beleidsdomein (fallback)

### Stap 5: Excel genereren
Bladen:

1. **Raadsvoorstellen** — alle records met kolommen:
   - BB-nummer, Titel, Datum, Portefeuillehouder
   - Besluittype, Besluittype detail (inhoud-gebaseerd)
   - Beleidsdomein, Beleidsdomein detail (inhoud-gebaseerd)
   - Beleidsveld (origineel)
   - Gevraagd besluit (tekst uit PDF)
   - Waarom dit voorstel (tekst uit PDF)
   - Cluster (uit PDF)
   - Classificatiebron ("inhoud" / "titel" / "beleidsveld")
   - PDF bestandsnaam, Aantal pagina's
   - URL, Document URL

2. **Per besluittype** — samenvatting

3. **Per besluittype (detail)** — gedetailleerde samenvatting

4. **Per beleidsdomein** — samenvatting

5. **Per beleidsdomein (detail)** — gedetailleerde samenvatting

6. **Kruistabel** — Besluittype x Beleidsdomein

7. **Per portefeuillehouder** — samenvatting

8. **Classificatiekwaliteit** — overzicht:
   - Hoeveel geclassificeerd op inhoud vs titel vs fallback
   - Hoeveel PDFs succesvol gedownload/geëxtraheerd
   - Hoeveel "Gevraagd besluit" secties gevonden

## Technische details

### Herstart-veiligheid
- JSON cache na elke fase (lijst, documenten, extractie, classificatie)
- `--from-cache` flag om vanaf cache verder te gaan
- `--skip-download` flag om alleen classificatie/Excel te herdraaien
- PDF-download slaat bestaande bestanden over

### Rate limiting
- 3 parallelle downloads (PDF)
- 5 parallelle detail-pagina requests
- Exponential backoff bij fouten

### Verwachte doorlooptijd
- Stap 1 (lijst + detail-pagina's): ~5 min (723 requests)
- Stap 2 (PDF download): ~20-30 min (723 PDFs, ~500MB)
- Stap 3 (extractie): ~5 min (lokaal, geen network)
- Stap 4 (classificatie): <1 min
- Stap 5 (Excel): <1 min
- **Totaal: ~30-40 min eerste run**

### Afhankelijkheden
- `pypdf` (al geïnstalleerd voor download_motie.py)
- `openpyxl` (al geïnstalleerd)
- Geen nieuwe dependencies nodig

### Bestandsstructuur
```
raadsvoorstellen/
├── [26bb001376] Voorstel presidium verordeningen ombudsman Rekenkamer.pdf
├── [26bb001075] HERZIEN Bestemmingsplan Pompenburg.pdf
├── [26bb000823] Aanvraag Bijdrageregeling Ontplofbare Oorlogsresten.pdf
└── ... (723 bestanden)
```

### Sectie-parsing pseudocode
```python
def parse_gevraagd_besluit(tekst):
    """Extraheer 'Gevraagd besluit' sectie uit de volledige PDF-tekst."""
    # Zoek begin: "Gevraagd besluit" (met variaties)
    # Zoek einde: "Waarom dit voorstel" of "Toelichting" of "Aan de gemeenteraad"
    # Return tekst daartussen

def parse_cluster(tekst):
    """Extraheer Cluster/Portefeuille uit PDF-tekst."""
    # Zoek "Cluster:" gevolgd door waarde
    # Zoek "Portefeuille:" gevolgd door waarde

def classificeer_op_inhoud(gevraagd_besluit, volledige_tekst, titel, beleidsveld):
    """Classificeer op basis van inhoud, met titel/beleidsveld als fallback."""
    # 1. Probeer besluittype op basis van "Gevraagd besluit"
    # 2. Fallback naar titel-classificatie
    # 3. Probeer beleidsdomein op basis van trefwoorden in volledige tekst
    # 4. Fallback naar Cluster veld
    # 5. Fallback naar beleidsveld
```
