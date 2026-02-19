# Classificatie-instructie Raadsbesluiten Rotterdam

Dit document beschrijft de systematiek, regels en geleerde lessen voor de
twee-dimensionale classificatie van raadsvoorstellen van de gemeente Rotterdam.

## 1. Overzicht classificatiemodel

Elk raadsvoorstel wordt langs twee dimensies geclassificeerd:

1. **Besluittype** (procedureel): _Wat voor soort besluit is het?_
2. **Beleidsdomein** (inhoudelijk): _Over welk beleidsonderwerp gaat het?_

### Classificatiebronnen

**Besluittype** (procedureel):

| Prioriteit | Bron | Dekkingsgraad |
|---|---|---|
| 1 | **Gevraagd besluit** (PDF-inhoud) | 633 (87.6%) |
| 2 | **Titel** van het raadsvoorstel | 90 (12.4%) |

**Beleidsdomein** (inhoudelijk):

| Prioriteit | Bron | Rol |
|---|---|---|
| 1 | **Beleidsveld** (metadata API) | Bepaalt altijd de **hoofdcategorie** |
| 2 | **PDF-tekst** (trefwoorden) | Verfijnt het **subdomein** binnen de hoofdcategorie |

---

## 2. Dimensie 1: Besluittype

### 2.1 Hoofdcategorieën en subcategorieën

#### 1. Ruimtelijk (237 raadsvoorstellen, 32.8%)

| Code | Subcategorie | Aantal | Sleutelwoorden in gevraagd besluit |
|---|---|---|---|
| 1.1 | Bestemmingsplan (vaststelling) | 48 | `bestemmingsplan`, `omgevingsplan` zonder `zienswijze` |
| 1.1 | Bestemmingsplan (zienswijze) | 95 | `bestemmingsplan` + `zienswijze` |
| 1.2 | Ambitiedocument | 27 | `ambitiedocument` |
| 1.3 | Grondexploitatie | 10 | `grondexploitatie` (generiek) |
| 1.3 | Grondexploitatie (openen) | 12 | `grondexploitatie` + `openen` / `open te stellen` |
| 1.3 | Grondexploitatie (herzien) | 9 | `grondexploitatie` + `herzie` |
| 1.4 | Welstandsnota | 6 | `welstand` |
| 1.5 | VVGB / Adviesrecht | 3 | `adviesrecht`, `vvgb`, `buitenplanse` + `omgevingsvergunning`, `bindend advies` + `omgevingsvergunning` |
| 1.6 | Erfpacht | 7 | `erfpacht`, of `aanwijzen`/`aan te wijzen` + `terrein` |
| 1.7 | Wegonttrekking | 4 | `openbaar verkeer` + `onttrekk` |
| 1.7 | Vastgoed | 3 | _(titel-gebaseerd)_ |
| 1.8 | Coördinatieregeling | 4 | regex: `co\s*[öo]rdinatieregeling` (spatie-tolerant) |
| 1.9 | Voorkeursrecht (WVG) | 9 | `voorkeursrecht` |

#### 2. Regelgeving (201, 27.8%)

| Code | Subcategorie | Aantal | Sleutelwoorden |
|---|---|---|---|
| 2.1 | Verordening (vaststelling) | 55 | `verordening` zonder `wijzig` |
| 2.1 | Verordening (wijziging) | 69 | `verordening` + `wijzig` |
| 2.2 | Beleidsnota / Beleidsregel | 64 | `vaststellen` + nota-trefwoorden (zie sectie 2.2) |
| 2.3 | Kadernota / Visie | 11 | _(titel-gebaseerd)_ |

**Nota-trefwoorden** (voor 2.2, in combinatie met `vaststellen`):
`nota`, `kader`, `visie`, `strategie`, `programma`, `handboek`, `plan`,
`beleidsplan`, `grondprijzen`, `woonakkoord`, `huisvestingsplan`, `vuistregels`,
`wateratlas`, `kiesreglement`, `wijkplan`, `beleidsregel`, `leidraad`,
`richtlijn`, `beleidskader`, `beleidsnota`, `gebiedsuitwerking`,
`uitvoeringsvoorstel`, `horecanota`, `grondstoffennota`, `transitie`,
`huisvestingsplannen`, `stijl`

#### 3. Financieel (111, 15.4%)

| Code | Subcategorie | Aantal | Sleutelwoorden |
|---|---|---|---|
| 3.1 | Begroting | 47 | `begroting` |
| 3.2 | Jaarrekening / Jaarstukken | 17 | `jaarrekening`, `jaarstukken` |
| 3.3 | Belasting / Tarieven | 5 | `belasting`, `tarieven`, `leges` |
| 3.4 | Krediet | 20 | `krediet`, `budget beschikbaar`, `middelen beschikbaar`, `bestemmingsreserve`, `grondprijs(zen)`, `kostendekkend` + `huren`, `gunning`, `1-op-1` |
| 3.5 | Subsidie | 12 | `subsidie` |
| 3.6 | Investering | 6 | `investering`, `eneco-middelen`, `investeringsvoorstel`, `fonds` + `instellen`, `aandelen`, `deelneming` |
| 3.7 | Declaratie / Kostenverhaal | 4 | `oorlogsresten`, `ontplofbare` |

#### 4. Bestuurlijk (133, 18.4%)

| Code | Subcategorie | Aantal | Sleutelwoorden |
|---|---|---|---|
| 4.1 | Benoeming / Aanwijzing | 55 | `te benoemen`, `benoemen`, `herbenoemen` |
| 4.1 | Benoeming (lid/voorzitter) | 7 | _(titel-gebaseerd)_ |
| 4.2 | Gemeenschappelijke regeling | 10 | `gemeenschappelijke regeling` (whitespace-tolerant) |
| 4.2 | Gem. regeling (zienswijze) | 4 | `zienswijze` + `gemeenschappelijke regeling` |
| 4.3 | Zienswijze | 17 | `zienswijze` (zonder GR-context) |
| 4.3 | Organisatie / Werkwijze raad | 12 | `instellen`/`instelling`/`inrichting` + `commissie`/`adviesorgaan`/`raadscommissie`, `wethouder` + `aantal`/`tijdsbestedingsnorm`, `wijk aan zet`, `opdracht` + `college` |
| 4.4 | Burgerinitiatief | 3 | _(titel-gebaseerd)_ |
| 4.5 | Bezwaarschrift | 17 | _(titel-gebaseerd)_ |

#### 5. Controle (36, 5.0%)

| Code | Subcategorie | Aantal | Sleutelwoorden |
|---|---|---|---|
| 5.1 | Rekenkamerrapport | 14 | `rekenkamer` |
| 5.2 | Geheimhouding | 16 | `geheimhouding` |
| 5.3 | Decharge / Verantwoording | 1 | titel: `eindrapportage`, `eindevaluatie` |
| 5.4 | Rechtmatigheid / Accountant | 5 | `accountant`, `accountantscontrole` |

#### 6. Overig (5, 0.7%)

| Code | Subcategorie | Aantal | Toelichting |
|---|---|---|---|
| 6.1 | Vervallen | 5 | Raadsvoorstellen met status "Vervallen" |

---

## 3. Dimensie 2: Beleidsdomein

### 3.1 Principe: beleidsveld is leidend

Het **beleidsveld** uit de API-metadata bepaalt altijd de hoofdcategorie
(beleidsdomein). PDF-inhoud wordt alleen gebruikt om het subdomein te verfijnen
*binnen* de door het beleidsveld bepaalde hoofdcategorie. De inhoud kan de
hoofdcategorie nooit overschrijven.

### 3.2 Vaste mapping: beleidsveld → beleidsdomein

| Beleidsveld (API) | Beleidsdomein | Default subdomein |
|---|---|---|
| Bouwen en Wonen | A. Ruimte & Wonen | A.1 Stedelijke ontwikkeling |
| Buitenruimte | A. Ruimte & Wonen | A.3 Buitenruimte / Groen |
| Projecten | A. Ruimte & Wonen | A.1 Stedelijke ontwikkeling |
| Economie | B. Economie & Haven | B.2 Economisch beleid |
| Haven | B. Economie & Haven | B.1 Haven |
| Werk en Inkomen | B. Economie & Haven | B.3 Werk & Inkomen |
| Mobiliteit | C. Mobiliteit | C.1 Verkeer |
| Duurzaam | D. Duurzaamheid | D.1 Energie / Klimaat |
| Onderwijs | E. Sociaal | E.1 Onderwijs |
| Zorg | E. Sociaal | E.2 Zorg / Jeugd |
| Jeugd | E. Sociaal | E.2 Zorg / Jeugd |
| Cultuur | E. Sociaal | E.3 Cultuur |
| Sport | E. Sociaal | E.4 Sport |
| Armoedebestrijding | E. Sociaal | E.5 Welzijn / Armoede |
| Welzijn | E. Sociaal | E.5 Welzijn / Armoede |
| Samenleven | E. Sociaal | E.6 Samenleven / Wijken |
| Wijken | E. Sociaal | E.6 Samenleven / Wijken |
| Gebieden | E. Sociaal | E.6 Samenleven / Wijken |
| Veiligheid | F. Veiligheid | F.1 Openbare orde / Handhaving |
| Bestuur | G. Bestuur & Financiën | G.3 Raadsorganisatie |
| Organisatie | G. Bestuur & Financiën | G.2 Gemeentelijke organisatie |
| PRESIDIUM | G. Bestuur & Financiën | G.3 Raadsorganisatie |
| cor | G. Bestuur & Financiën | G.4 Interbestuurlijk |
| Financien* | G. Bestuur & Financiën | G.1 Gemeentefinanciën |

\* Financiën kent 4 spelvarianten: `Financien`, `Financiën`, `Financïen`,
`Financien-inactief`. Alle worden genormaliseerd naar G.1.

### 3.3 Hoofddomeinen (verdeling)

| Code | Domein | Aantal | Percentage |
|---|---|---|---|
| A | Ruimte & Wonen | 360 | 49.8% |
| B | Economie & Haven | 51 | 7.1% |
| C | Mobiliteit | 26 | 3.6% |
| D | Duurzaamheid | 13 | 1.8% |
| E | Sociaal | 96 | 13.3% |
| F | Veiligheid | 13 | 1.8% |
| G | Bestuur & Financiën | 164 | 22.7% |

### 3.4 Subdomein-verfijning via PDF-inhoud

Na bepaling van de hoofdcategorie worden trefwoorden in de eerste 5000
tekens van de PDF-tekst gematcht om het subdomein te verfijnen. Er zijn
minimaal 2 hits vereist. De trefwoorden zijn gegroepeerd per hoofddomein,
zodat ze alleen *binnen* het beleidsveld-bepaalde domein zoeken.

Voorbeeld voor A. Ruimte & Wonen:
- `bestemmingsplan`, `omgevingsplan`, `grondexploitatie` → A.1 Stedelijke ontwikkeling
- `woning`, `huurwoning`, `woonvisie`, `huisvesting` → A.2 Woonbeleid
- `groen`, `bomen`, `buitenruimte` → A.3 Buitenruimte / Groen
- `monument`, `erfgoed` → A.4 Monumenten / Erfgoed

Als geen enkel subdomein ≥ 2 hits haalt, wordt het default subdomein
uit de beleidsveld-mapping gebruikt.

---

## 4. Geleerde lessen

### 4.1 PDF-tekst extractie artefacten

PDF-extractie met pypdf levert regelmatig tekst op met:
- **Samengevoegde woorden**: "DeWateratlasbinnenstedelijke", "HoofdlijnenenkadersHorecanota"
- **Gesplitste woorden**: "co ördinatieregeling" (ö met spatie), "vast testellen"
- **Verbroken regelafbrekingen**: "Gemeenschappelijke\nRegeling"

**Oplossing:** Normaliseer alle whitespace naar enkele spaties vóór patroonherkenning:
```python
gb = re.sub(r'\s+', ' ', tekst.lower().strip())
```

Gebruik voor specifieke woorden regex met spatie-tolerantie:
```python
re.search(r'co\s*[öo]rdinatieregeling', gb)   # coördinatieregeling
re.search(r'vast\s*(?:te\s*)?stellen', gb)     # vaststellen / vast te stellen
re.search(r'wijk\s*aan\s*zet', gb)             # Wijk aan Zet
re.search(r'gemeenschappelijke\s+regeling', gb) # Gemeenschappelijke Regeling
```

### 4.2 Records zonder "Gevraagd besluit"

Circa 5.5% van de PDFs (40 van 723) levert geen parseerbaar "Gevraagd besluit"
op, door afwijkende documentstructuur. Voor deze records zijn titel-gebaseerde
fallbacks nodig:

| Titelpatroon | Classificatie |
|---|---|
| `instelling` + `commissie`/`raadscommissie` | 4.3 Organisatie / Werkwijze raad |
| `accountant` | 5.4 Rechtmatigheid / Accountant |
| `vaststelling` + `wijkplan` | 2.2 Beleidsnota / Beleidsregel |
| `eindrapportage` / `eindevaluatie` | 5.3 Decharge / Verantwoording |
| `bestuursmodel` | 4.3 Organisatie / Werkwijze raad |

### 4.3 Volgorde van patroonherkenning is cruciaal

De volgorde van de if-statements bepaalt de classificatie. Specifieke patronen
moeten vóór generieke komen:

1. **Coördinatieregeling vóór Verordening**: het woord "regeling" zou anders
   als verordening gematcht kunnen worden.
2. **Gemeenschappelijke regeling + zienswijze vóór losse zienswijze**: anders
   vallen GR-zienswijzen in de generieke zienswijze-categorie.
3. **Specifieke financiële patronen vóór het generieke "vaststellen"**: anders
   worden begrotingen en jaarrekeningen als beleidsnota geclassificeerd.
4. **Bestemmingsplan vóór alle andere patronen**: het woord "plan" in de
   nota-trefwoorden zou anders bestemmingsplannen als nota classificeren.

### 4.4 Het "vaststellen"-patroon

Veel raadsvoorstellen bevatten "vast te stellen" in het gevraagd besluit. Dit
is op zichzelf niet onderscheidend - het komt voor bij bestemmingsplannen,
verordeningen, begrotingen én beleidsnota's. Het "vaststellen"-patroon wordt
daarom alleen als vangnet ingezet, nadat alle specifiekere patronen zijn
gecontroleerd, en uitsluitend in combinatie met nota-trefwoorden.

**Let op:** Het woord `plan` is bewust in de nota-trefwoordenlijst opgenomen
maar is veilig omdat `bestemmingsplan` en `omgevingsplan` eerder in de keten
worden afgevangen.

### 4.5 Beleidsveld als leidende bron

Het beleidsveld uit de API is leidend voor de beleidsdomein-classificatie,
ondanks bekende beperkingen:
- **Inconsistente spelling**: 4 varianten van "Financiën" worden genormaliseerd
- **Brede categorieën**: "Bouwen en Wonen" bevat 43% van alle records — de
  subdomein-verfijning via PDF-inhoud differentieert binnen deze categorie
- **27 unieke waarden** worden via een vaste mapping omgezet naar 7 hoofddomeinen

De eerdere aanpak (inhoud-gebaseerd met beleidsveld als fallback) leidde tot
194 records die in een verkeerd hoofddomein terechtkwamen. Bijvoorbeeld
bestemmingsplannen met energietrefwoorden die bij "Duurzaamheid" werden
geclassificeerd in plaats van bij "Ruimte & Wonen" (conform hun beleidsveld
"Bouwen en Wonen").

### 4.6 Cluster uit PDF is geen betrouwbare detailbron

Het "Cluster:"-veld in de PDF geeft de gemeentelijke organisatie-eenheid aan
(bijv. "Maatschappelijke Ontwikkeling", "Stadsontwikkeling"), niet het
beleidsdomein. Het cluster is te grof voor subdomein-verfijning: het cluster
"Maatschappelijke Ontwikkeling" omvat Zorg, Onderwijs, Cultuur, Sport én
Welzijn. Gebruik van het cluster als detailbron leidde tot 28 foute
overschrijvingen (bijv. Cultuur-records die als Zorg werden geclassificeerd).
Het cluster wordt daarom niet meer gebruikt voor classificatie.

### 4.7 Eén PDF kon niet gedownload worden

Record `25bb001137` heeft geen hoofddocument in iBabs. Dit is het enige record
(1 van 723) waarvoor geen PDF beschikbaar is. Het wordt puur op titel
geclassificeerd.

---

## 5. Classificatiekwaliteit (huidige stand)

### Besluittype
| Bron | Aantal | Percentage |
|---|---|---|
| Inhoud (gevraagd besluit) | 633 | 87.6% |
| Titel (fallback) | 90 | 12.4% |
| **Totaal** | **723** | **100%** |

### Beleidsdomein
| Component | Bron | Toelichting |
|---|---|---|
| Hoofdcategorie | Beleidsveld (API) | Altijd leidend, 100% dekking |
| Subdomein | PDF-tekst (trefwoorden) | Verfijnt binnen hoofdcategorie |
| Subdomein (fallback) | Beleidsveld-default | Als PDF < 2 trefwoord-hits |

### Iteratiegeschiedenis besluittype
| Versie | Inhoud | Titel | Niet geclassificeerd |
|---|---|---|---|
| v1 (alleen titel) | - | 500 (69%) | 223 (31%) |
| v2 (uitgebreide titel) | - | 593 (82%) | 130 (18%) |
| v3 (inhoud + titel) | 486 (67%) | 173 (24%) | 64 (9%) |
| v4 (verbeterde patronen) | 584 (81%) | 111 (15%) | 28 (4%) |
| **v5 (huidig)** | **633 (87.6%)** | **90 (12.4%)** | **0 (0%)** |

### Iteratiegeschiedenis beleidsdomein
| Versie | Aanpak | Resultaat |
|---|---|---|
| v1-v5 | Inhoud leidend, beleidsveld fallback | 194 records in verkeerd hoofddomein |
| **v6 (huidig)** | **Beleidsveld leidend, inhoud verfijnt** | **100% correct hoofddomein** |

---

## 6. Technische referentie

### Bestanden

| Bestand | Functie |
|---|---|
| `download_raadsvoorstellen.py` | Hoofdscript: download, extractie, classificatie, Excel |
| `fetch_raadsvoorstellen.py` | API-aanroepen, titel-classificatie, Excel-helpers |
| `raadsvoorstellen_cache.json` | Cache van alle records (zonder PDF-tekst) |
| `raadsvoorstellen/` | Map met 722 gedownloade PDF-bestanden |
| `raadsvoorstellen.xlsx` | Output Excel met 8 bladen |

### Classificatiefuncties

| Functie | Bestand | Doel |
|---|---|---|
| `classificeer_besluittype_inhoud()` | `download_raadsvoorstellen.py` | Inhoud-gebaseerde besluittype-classificatie |
| `classificeer_beleidsdomein_inhoud()` | `download_raadsvoorstellen.py` | Beleidsveld → hoofddomein + inhoud → subdomein |
| `classificeer_besluittype()` | `fetch_raadsvoorstellen.py` | Titel-gebaseerde besluittype-classificatie (fallback) |
| `classificeer_alle_records()` | `download_raadsvoorstellen.py` | Orchestreert alle classificatie |

### API-gegevens

| Parameter | Waarde |
|---|---|
| Base URL | `https://gemeenteraad.rotterdam.nl` |
| ListID Raadsvoorstellen | `4a6cb9e4-2668-4729-852a-ddb3b3ea90d3` |
| Protocol | DataTables server-side (POST, form-urlencoded) |
