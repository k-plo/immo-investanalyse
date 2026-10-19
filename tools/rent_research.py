"""Best-effort regional rent research for quick checks."""
from __future__ import annotations

import html
import json
import math
import re
import urllib.parse
from datetime import datetime, timezone
from functools import lru_cache
from html.parser import HTMLParser

from listing_import import ListingError, ListingParser, fetch_public

KASSEL_RECHNER_JS = "https://www.kassel.de/_daten/aliases/mietspiegelrechner2026/index.js"
KASSEL_RECHNER_PAGE = "https://www.kassel.de/_daten/aliases/mietspiegelrechner2026/index.html"


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._hidden += 1
        elif tag == "img" and not self._hidden:
            alt = dict(attrs).get("alt")
            if alt:
                self.parts.append(alt)

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._hidden:
            self._hidden -= 1

    def handle_data(self, data):
        if not self._hidden and data.strip():
            self.parts.append(data.strip())


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _market_page_url(listing_page: bytes, source_url: str) -> str | None:
    source = urllib.parse.urlsplit(source_url)
    if source.hostname == "www.immowelt.de" and "/immobilienpreise/mietpreise/" in source.path:
        return source_url

    parser = ListingParser()
    parser.feed(listing_page.decode("utf-8", errors="replace"))
    candidates = []
    for node in _walk(parser.jsonld):
        node_type = node.get("@type", [])
        if "BreadcrumbList" not in (node_type if isinstance(node_type, list) else [node_type]):
            continue
        for entry in node.get("itemListElement", []):
            item = entry.get("item") if isinstance(entry, dict) else None
            item_url = item.get("@id") or item.get("url") if isinstance(item, dict) else item
            if not isinstance(item_url, str):
                continue
            parsed = urllib.parse.urlsplit(item_url)
            if parsed.hostname != "www.immowelt.de":
                continue
            match = re.search(r"/suche/[^/]+/wohnung/(.+)$", parsed.path, re.I)
            if not match:
                continue
            location_path = match.group(1).strip("/")
            if not re.search(r"/(?:ad08|ad09|nbh2)[a-z0-9]+/?$", location_path, re.I):
                continue
            candidates.append(location_path)

    if not candidates:
        return None
    location_path = candidates[-1]
    return "https://www.immowelt.de/immobilienpreise/mietpreise/" + location_path


def _apartment_rate(page: bytes) -> tuple[float, str | None] | None:
    parser = _VisibleText()
    parser.feed(page.decode("utf-8", errors="replace"))
    text = re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts)))
    patterns = (
        r"Wohnung\s+Preis pro Quadratmeter\s+([\d.,]+)\s*€",
        r"Der Mietpreis für Eigentumswohnungen in .*?durchschnittlich\s+([\d.,]+)\s*€\s+pro Quadratmeter",
    )
    rate = None
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            try:
                raw_rate = match.group(1)
                rate = float(raw_rate.replace(".", "").replace(",", ".") if "," in raw_rate else raw_rate)
            except ValueError:
                pass
            if rate:
                break
    if not rate:
        return None
    updated = re.search(r"Geschätzter Preis aktualisiert am\s+(.{1,40}?\b20\d{2}\b)", text, re.I)
    return rate, updated.group(1).strip() if updated else None


def _json_assignment(script: str, variable: str):
    marker = f"{variable}=JSON.parse('"
    start = script.find(marker)
    if start < 0:
        raise ValueError(f"Kasseler Mietspiegeldaten fehlen: {variable}")
    payload_start = start + len(marker)
    value, _ = json.JSONDecoder().raw_decode(script[payload_start:])
    return value


@lru_cache(maxsize=1)
def _kassel_data() -> tuple[list[dict], dict[str, list[dict]]]:
    _, script, content_type = fetch_public(KASSEL_RECHNER_JS, limit=5_000_000)
    if "javascript" not in content_type.lower() and "text/plain" not in content_type.lower():
        raise ListingError("Kasseler Mietspiegel-Rechner liefert kein JavaScript")
    source = script.decode("utf-8", errors="replace")
    addresses = _json_assignment(source, "dC")
    tables = {name: _json_assignment(source, name) for name in ("uF", "cF", "mF", "fF")}
    return addresses, tables


def _kassel_official_mean(data: dict) -> tuple[float, str] | None:
    street = _normalize_street(str(data.get("strasse") or ""))
    number = re.sub(r"\s+", "", str(data.get("hausnummer") or "").casefold())
    area = data.get("area") or data.get("wohnflaeche")
    year = data.get("baujahr")
    if not street or not number or not area or not year:
        return None

    addresses, tables = _kassel_data()
    range_match = re.fullmatch(r"(\d+)[a-z]?[-/](\d+)[a-z]?", number)
    if range_match:
        first_number, last_number = map(int, range_match.groups())
        matching_residences = [
            entry for entry in addresses
            if _normalize_street(str(entry.get("straße") or "")) == street
            and (entry_number := re.fullmatch(r"(\d+)[a-z]?", re.sub(
                r"\s+", "", str(entry.get("nr") or "").casefold())))
            and first_number <= int(entry_number.group(1)) <= last_number
        ]
        locations = {entry.get("wohnlage") for entry in matching_residences}
        if not matching_residences or len(locations) != 1:
            return None
        residence = matching_residences[0]
    else:
        residence = next((entry for entry in addresses
                          if _normalize_street(str(entry.get("straße") or "")) == street
                          and re.sub(r"\s+", "", str(entry.get("nr") or "").casefold()) == number), None)
    if not residence:
        return None

    table_name = {"einfach": "uF", "mittel": "cF", "gut": "mF", "sehr gut": "fF"}.get(residence["wohnlage"])
    if not table_name:
        return None
    area_row = math.floor(float(area) + 0.5)
    row = next((entry for entry in tables[table_name] if entry.get("wohnflaeche") == area_row), None)
    if not row:
        return None
    year_key = next((key for key in row if key != "wohnflaeche" and int(year) <= int(key)), None)
    if not year_key:
        return None

    # Mirrors the official calculator's 2026 index adjustment and area rounding.
    return float(row[year_key]) * 1.0407, residence["wohnlage"]


def _monthly_rent(area: float, rate: float) -> float:
    return round(float(area) * rate, 2)


def _normalize_street(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    normalized = re.sub(r"str\.(?=\s|$)|\bstr\b", "strasse", normalized)
    return re.sub(r"[^\w]+", " ", normalized).strip()


def research_potential_rent(data: dict, listing_page: bytes, source_url: str) -> dict:
    area = data.get("area") or data.get("wohnflaeche")
    if not area:
        return {"kaltmiete_pot": None, "miete_pot_quelle": "KM-pot-Recherche nicht möglich: Wohnfläche fehlt."}

    researched = datetime.now(timezone.utc).date().isoformat()
    official_fallback = ""
    if str(data.get("ort") or "").casefold() == "kassel" and data.get("strasse") and data.get("hausnummer"):
        try:
            official = _kassel_official_mean(data)
        except (ListingError, ValueError, KeyError, TypeError):
            official = None
            official_fallback = "Kasseler Mietspiegel-Rechner nicht abrufbar; "
        if official:
            rate, wohnlage = official
            monthly = _monthly_rent(area, rate)
            note = (f"Kasseler Mietspiegel 2026: Straße/Hausnr. bestätigt Wohnlage {wohnlage}; "
                    f"Baujahr {year if (year := data.get('baujahr')) else 'unbekannt'}, {area} m². "
                    f"Mittelwert {rate:.2f} EUR/m² = {monthly:.2f} EUR/Monat; Basiswert ohne individuelle "
                    f"Wohnungszuschläge. Recherchiert {researched}. Quelle: {KASSEL_RECHNER_PAGE}")
            return {"kaltmiete_pot": monthly, "miete_pot_quelle": note[:500]}

    market_url = _market_page_url(listing_page, source_url)
    if not market_url:
        region = " ".join(str(data.get(key) or "") for key in ("stadtteil", "ort", "plz")).strip()
        return {
            "kaltmiete_pot": None,
            "miete_pot_quelle": f"KM-pot-Recherche {researched}: {official_fallback}keine regionale Immowelt-Mietpreisseite aus dem Anzeigenlink bestimmbar ({region or 'Ort fehlt'}).",
        }

    try:
        _, market_page, content_type = fetch_public(market_url)
        if "html" not in content_type.lower():
            raise ListingError("Mietpreisseite liefert kein HTML")
    except ListingError as error:
        return {"kaltmiete_pot": None, "miete_pot_quelle": f"KM-pot-Recherche {researched}: Mietpreisseite nicht abrufbar ({error})."}

    result = _apartment_rate(market_page)
    if result is None:
        return {"kaltmiete_pot": None, "miete_pot_quelle": f"KM-pot-Recherche {researched}: kein Wohnungsmittelwert auf {market_url}."}

    rate, source_date = result
    monthly = _monthly_rent(area, rate)
    district = data.get("stadtteil")
    location_path = urllib.parse.urlsplit(market_url).path.lower()
    district_page = bool(re.search(r"/(?:ad09|nbh2)[a-z0-9]+/?$", location_path))
    scope = (f"{district}, {data.get('ort')}" if district else data.get("ort") or "Region") if district_page \
        else f"{data.get('ort')} (Stadt)" if data.get("ort") else "Region"
    stand = f"Marktstand {source_date}; " if source_date else ""
    note = (f"{official_fallback}Immowelt Wohnungsmiete {scope}: {rate:.2f} EUR/m²; {stand}recherchiert {researched}. "
            f"{area} m² x {rate:.2f} EUR/m² = {monthly:.2f} EUR/Monat; Angebotsmarkt-Orientierung. Quelle: {market_url}")
    return {"kaltmiete_pot": monthly, "miete_pot_quelle": note[:500]}