#!/usr/bin/env python3
"""Gedeelde cache-utilities voor incrementele updates van gemeenteraad scripts.

Werking:
  - Bij elke run wordt de volledige API-lijst opgehaald (lichte requests).
  - Per record wordt een hash berekend van de lijst-velden.
  - Alleen records met een nieuwe of gewijzigde hash krijgen een detail-pagina scrape.
  - Ongewijzigde records worden direct uit de cache geladen.
  - Na elke run wordt de cache bijgewerkt met alle records.

Cache-bestandsformaat (cache/<naam>.json):
  {
    "metadata": { "last_updated": "...", "total_records": N },
    "records": {
      "<DT_RowId>": { "hash": "<md5>", "data": { ... alle velden ... } },
      ...
    }
  }
"""

import json
import hashlib
import os
from datetime import datetime

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")


def load_cache(name):
    """Laad cache van disk.

    Geeft dict: {DT_RowId: {'hash': str, 'data': dict}}
    Geeft leeg dict terug als er nog geen cache is.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{name}.json")
    if not os.path.exists(path):
        print(f"  Geen cache gevonden ({path}), eerste volledige run.")
        return {}
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)
    meta = stored.get("metadata", {})
    records = stored.get("records", {})
    last_updated = meta.get("last_updated", "onbekend")
    print(f"  Cache geladen: {len(records)} records (laatste update: {last_updated})")
    return records


def save_cache(name, records, hash_fields):
    """Sla alle records op in cache.

    Args:
        name: naam van het cache-bestand (zonder .json)
        records: lijst van volledige record-dicts (inclusief detail-velden)
        hash_fields: lijst van veldnamen waarover de hash berekend wordt
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{name}.json")
    records_dict = {
        r["DT_RowId"]: {
            "hash": compute_hash(r, hash_fields),
            "data": r,
        }
        for r in records
    }
    cache_data = {
        "metadata": {
            "last_updated": datetime.now().isoformat(),
            "total_records": len(records),
        },
        "records": records_dict,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    print(f"  Cache opgeslagen: {path} ({len(records)} records)")


def compute_hash(record, fields):
    """Bereken MD5-hash van de opgegeven velden in een record."""
    values = "|".join(str(record.get(f, "") or "") for f in fields)
    return hashlib.md5(values.encode("utf-8")).hexdigest()


def find_changes(api_records, cache, hash_fields):
    """Vergelijk API-lijstrecords met de cache.

    Args:
        api_records: lijst van records zoals teruggegeven door de API (lijst-niveau)
        cache: dict geladen via load_cache()
        hash_fields: velden die in de hash meegenomen worden

    Returns:
        to_fetch:  records die een detail-scrape nodig hebben (nieuw of gewijzigd)
        unchanged: volledige records uit cache die ongewijzigd zijn
        stats:     dict met tellingen {'nieuw', 'gewijzigd', 'ongewijzigd'}
    """
    to_fetch = []
    unchanged = []
    new_count = changed_count = unchanged_count = 0

    for record in api_records:
        row_id = record["DT_RowId"]
        current_hash = compute_hash(record, hash_fields)

        if row_id not in cache:
            new_count += 1
            to_fetch.append(record)
        elif cache[row_id]["hash"] != current_hash:
            changed_count += 1
            to_fetch.append(record)
        else:
            unchanged_count += 1
            unchanged.append(dict(cache[row_id]["data"]))

    stats = {
        "nieuw": new_count,
        "gewijzigd": changed_count,
        "ongewijzigd": unchanged_count,
    }
    return to_fetch, unchanged, stats


def restore_order(api_records, fetched, unchanged):
    """Herstel de originele API-volgorde (meest recent eerst).

    Args:
        api_records: originele API-recordlijst (bepaalt volgorde)
        fetched:     records waarvoor detail opgehaald is
        unchanged:   records uit cache

    Returns:
        lijst in originele API-volgorde
    """
    lookup = {r["DT_RowId"]: r for r in fetched + unchanged}
    return [lookup[r["DT_RowId"]] for r in api_records if r["DT_RowId"] in lookup]
