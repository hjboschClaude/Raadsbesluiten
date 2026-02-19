# Voorstel: Hierarchische categorisering raadsbesluiten Rotterdam

## Analyse bestaande situatie

De gemeente Rotterdam gebruikt momenteel het veld **beleidsveld** als enige
categorisering voor raadsvoorstellen. Deze categorisering kent problemen:

| Probleem | Voorbeeld |
|---|---|
| **Inconsistente naamgeving** | "Financien-inactief", "Financïen", "Financien", "Financiën" (4 varianten) |
| **Dominantie van één categorie** | "Bouwen en Wonen" bevat 309 van 723 voorstellen (43%) — te breed |
| **Vermenging van dimensies** | Beleidsveld zegt niets over het *type besluit* (vaststelling, wijziging, benoeming) |
| **Ontbrekende categorieën** | Geen onderscheid tussen financiële en inhoudelijke besluiten |

---

## Voorstel: Twee-dimensionale categorisering

In plaats van één vlak beleidsveld, stel ik een **twee-dimensionale** indeling voor:

1. **Besluittype** — *Wat voor soort besluit is het?* (procedureel)
2. **Beleidsdomein** — *Over welk thema gaat het?* (inhoudelijk)

Dit maakt kruisanalyses mogelijk: "Hoeveel bestemmingsplannen zijn er op het
gebied van wonen?" of "Welke financiële besluiten gaan over duurzaamheid?"

---

## Dimensie 1: Besluittype (hierarchisch)

```
Besluittype
├── 1. Ruimtelijk
│   ├── 1.1 Bestemmingsplan / Omgevingsplan
│   │   ├── Vaststelling
│   │   ├── Wijziging
│   │   └── Zienswijze
│   ├── 1.2 Ambitiedocument
│   │   ├── Gebiedsambitiedocument
│   │   └── Projectambitiedocument
│   ├── 1.3 Grondexploitatie
│   │   ├── Openen
│   │   ├── Herzien
│   │   └── Afsluiten
│   ├── 1.4 Welstandsnota / Welstandsparagraaf
│   ├── 1.5 Verklaring van geen bedenkingen (VVGB)
│   └── 1.6 Erfpacht
│
├── 2. Regelgeving
│   ├── 2.1 Verordening
│   │   ├── Vaststelling
│   │   ├── Wijziging
│   │   └── Intrekking
│   ├── 2.2 Beleidsregel / Nota
│   └── 2.3 Kadernota / Visiedocument
│
├── 3. Financieel
│   ├── 3.1 Begroting
│   │   ├── Vaststelling
│   │   ├── Wijziging
│   │   └── Deelbegroting (BOOR, Havenbedrijf, etc.)
│   ├── 3.2 Jaarrekening / Jaarstukken
│   ├── 3.3 Belasting / Tarieven / Leges
│   ├── 3.4 Krediet
│   ├── 3.5 Subsidie
│   └── 3.6 Lening / Garantie / Borgstelling
│
├── 4. Bestuurlijk
│   ├── 4.1 Benoeming / Herbenoeming
│   │   ├── Rekenkamer
│   │   ├── Commissielid
│   │   └── Overig
│   ├── 4.2 Gemeenschappelijke regeling
│   │   ├── Vaststelling / Wijziging
│   │   └── Zienswijze
│   └── 4.3 Organisatie / Werkwijze raad
│
├── 5. Controle
│   ├── 5.1 Rekenkamerrapport
│   ├── 5.2 Geheimhouding (opleggen/opheffen)
│   └── 5.3 Decharge / Verantwoording
│
└── 6. Overig
    └── 6.1 Vervallen
```

### Verdeling over 723 raadsvoorstellen (schatting)

| Besluittype | Aantal | % |
|---|---:|---:|
| 1. Ruimtelijk | ~176 | 24% |
| 2. Regelgeving | ~99 | 14% |
| 3. Financieel | ~83 | 11% |
| 4. Bestuurlijk | ~84 | 12% |
| 5. Controle | ~30 | 4% |
| 6. Overig | ~251 | 35% |

> De grote "Overig" categorie (35%) bevat voornamelijk raadsvoorstellen die
> inhoudelijk zeer divers zijn maar geen standaard procedureel type volgen.
> Deze worden beter onderscheiden via Dimensie 2 (Beleidsdomein).

---

## Dimensie 2: Beleidsdomein (hierarchisch)

```
Beleidsdomein
├── A. Ruimte & Wonen
│   ├── A.1 Stedelijke ontwikkeling
│   ├── A.2 Woningbouw / Woonbeleid
│   ├── A.3 Buitenruimte / Groen
│   └── A.4 Monumenten / Erfgoed
│
├── B. Economie & Haven
│   ├── B.1 Haven / Havengebied
│   ├── B.2 Economisch beleid
│   └── B.3 Arbeidsmarkt / Werk en Inkomen
│
├── C. Mobiliteit & Infrastructuur
│   ├── C.1 Verkeer / Wegen
│   ├── C.2 Openbaar vervoer
│   └── C.3 Parkeren
│
├── D. Duurzaamheid & Klimaat
│   ├── D.1 Energietransitie
│   ├── D.2 Klimaatadaptatie / Water
│   └── D.3 Milieu / Luchtkwaliteit
│
├── E. Sociaal
│   ├── E.1 Onderwijs (incl. BOOR)
│   ├── E.2 Zorg / Jeugd / WMO
│   ├── E.3 Cultuur
│   ├── E.4 Sport
│   ├── E.5 Welzijn / Armoede
│   └── E.6 Samenleven / Wijken
│
├── F. Veiligheid
│   ├── F.1 Openbare orde
│   └── F.2 Handhaving
│
├── G. Bestuur & Financiën
│   ├── G.1 Gemeentefinanciën
│   ├── G.2 Gemeentelijke organisatie
│   ├── G.3 Raadsorganisatie / Presidium
│   └── G.4 Interbestuurlijk (VNG, MRDH, GR)
│
└── X. Niet van toepassing / Divers
```

---

## Gecombineerd voorbeeld

Met deze twee dimensies ontstaan informatieve combinaties:

| BB-nummer | Titel | Besluittype | Beleidsdomein |
|---|---|---|---|
| 25bb007753 | Gebiedsambitiedocument Zuidrand Oud-Charlois | 1.2 Ambitiedocument | A.1 Stedelijke ontwikkeling |
| 25bb004826 | Projectambitiedocument windenergie Beneluxplein | 1.2 Ambitiedocument | D.1 Energietransitie |
| 26bb000364 | Wijziging Havenverordening Rotterdam 2020 | 2.1 Verordening (wijziging) | B.1 Haven |
| 25bb008506 | Vaststellen belastingverordeningen 2026 | 3.3 Belasting/Tarieven | G.1 Gemeentefinanciën |
| 25bb002929 | Benoeming lid Rekenkamer Rotterdam | 4.1 Benoeming (Rekenkamer) | G.3 Raadsorganisatie |
| 25bb004078 | Bestemmingsplan Oud Crooswijk-west | 1.1 Bestemmingsplan | A.1 Stedelijke ontwikkeling |

---

## Automatische classificatie

Veel categorisering is **automatiseerbaar** op basis van titelpatronen:

| Patroon in titel | → Besluittype |
|---|---|
| `bestemmingsplan` | 1.1 Bestemmingsplan |
| `omgevingsplan` | 1.1 Omgevingsplan |
| `ambitiedocument` | 1.2 Ambitiedocument |
| `grondexploitatie` | 1.3 Grondexploitatie |
| `welstand` | 1.4 Welstandsnota |
| `verordening` | 2.1 Verordening |
| `nota` / `kadernota` | 2.2/2.3 Beleidsregel |
| `begroting` | 3.1 Begroting |
| `jaarrekening` / `jaarstukken` | 3.2 Jaarrekening |
| `belasting` / `tarieven` / `leges` | 3.3 Belasting |
| `krediet` | 3.4 Krediet |
| `subsidie` | 3.5 Subsidie |
| `benoeming` / `herbenoeming` | 4.1 Benoeming |
| `gemeenschappelijke regeling` | 4.2 Gemeenschappelijke regeling |
| `rekenkamer` (in combinatie met `rapport`) | 5.1 Rekenkamerrapport |
| `geheimhouding` | 5.2 Geheimhouding |
| `VERVALLEN` | 6.1 Vervallen |

Met deze regels is naar schatting **65-70%** automatisch te classificeren.
De rest vereist handmatige toewijzing of meer geavanceerde tekstanalyse.

---

## Vergelijking met huidig beleidsveld

| Huidig beleidsveld | Voorgesteld beleidsdomein |
|---|---|
| Bouwen en Wonen | A.1 + A.2 (splitsen!) |
| Bestuur | G.3 Raadsorganisatie |
| Buitenruimte | A.3 Buitenruimte/Groen |
| Economie | B.2 Economisch beleid |
| Financien* (4 varianten) | G.1 Gemeentefinanciën |
| Zorg | E.2 Zorg/Jeugd/WMO |
| Mobiliteit | C.1 + C.2 + C.3 |
| Onderwijs | E.1 Onderwijs |
| Organisatie | G.2 Gemeentelijke organisatie |
| Projecten | *(vervalt als apart veld, zit in besluittype)* |
| Veiligheid | F.1 + F.2 |
| Cultuur | E.3 Cultuur |
| Duurzaam | D.1 + D.2 + D.3 |
| Wijken | E.6 Samenleven/Wijken |
| Haven | B.1 Haven |
| Werk en Inkomen | B.3 Arbeidsmarkt |
| Armoedebestrijding | E.5 Welzijn/Armoede |
| Sport | E.4 Sport |
| Welzijn | E.5 Welzijn/Armoede |

---

## Aanbevelingen

1. **Voeg "Besluittype" toe als nieuwe dimensie** — dit is het belangrijkste
   gemis in de huidige data en grotendeels automatisch af te leiden uit titels.

2. **Normaliseer het beleidsveld** — de 4 varianten van "Financiën" en
   de vermenging van "Bouwen en Wonen" (43% van alle voorstellen!) vragen om
   standaardisatie en opsplitsing.

3. **Splits "Bouwen en Wonen"** — dit beleidsveld bevat bestemmingsplannen,
   ambitiedocumenten, grondexploitaties, welstandsbesluiten, woonbeleid EN
   culturele/sportvoorzieningen. Een opsplitsing in minimaal "Stedelijke
   ontwikkeling" en "Woonbeleid" is noodzakelijk.

4. **Implementeer geautomatiseerde classificatie** — een Python-script kan
   ~70% van de besluiten automatisch categoriseren op basis van titelpatronen.
   De rest kan handmatig worden aangevuld.
