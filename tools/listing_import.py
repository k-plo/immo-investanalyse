"""Conservative public listing extraction; no login, captcha bypass or guessed facts."""
from __future__ import annotations

import html
import ipaddress
from io import BytesIO
import json
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


class ListingError(ValueError):
    pass


def validate_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ListingError("Ungültiger Link")
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ListingError("Nur öffentliche HTTP(S)-Anzeigenlinks sind erlaubt")
    if parsed.port not in (None, 80, 443):
        raise ListingError("Der Link darf keinen Sonder-Port verwenden")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in ("localhost", "localhost.localdomain") or hostname.endswith(".local"):
        raise ListingError("Lokale Ziele sind nicht erlaubt")
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ListingError("Anzeigen-Domain nicht erreichbar") from error
    if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses):
        raise ListingError("Nur öffentliche Internetadressen sind erlaubt")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def fetch_public(url: str, limit: int = 3_000_000) -> tuple[str, bytes, str]:
    # python.org's macOS build may have no CA bundle at its OpenSSL default path.
    # Use the OS CA bundle when present; certificate validation stays enabled.
    default_ca = ssl.get_default_verify_paths().cafile
    system_ca = Path("/etc/ssl/cert.pem")
    context = ssl.create_default_context(cafile=str(system_ca) if not default_ca and system_ca.is_file() else None)
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context))
    for _ in range(5):
        url = validate_url(url)
        request = urllib.request.Request(url, headers={
            # Realistischer Browser-UA: Portale wie Immowelt blockieren Bot-Kennungen (HTTP 403)
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,image/*;q=0.8,*/*;q=0.5",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        })
        try:
            with opener.open(request, timeout=12) as response:
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise ListingError("Anzeige/Bild ist zu groß")
                return url, data, response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            if error.code in (301, 302, 303, 307, 308):
                location = error.headers.get("Location")
                if not location:
                    raise ListingError("Weiterleitung ohne Ziel") from error
                url = urllib.parse.urljoin(url, location)
                continue
            raise ListingError(f"Anzeige nicht abrufbar (HTTP {error.code})") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise ListingError("Anzeige nicht erreichbar") from error
    raise ListingError("Zu viele Weiterleitungen")


class ListingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}
        self.jsonld: list[dict] = []
        self._script = False
        self._title = False
        self.title = ""
        self._buffer = ""
        self._provider_depth = 0
        self._provider_done = False
        self.provider_company = ""
        self.provider_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            if self._provider_depth:
                self._provider_depth += 1
            elif not self._provider_done and attrs.get("data-testid") == "aviv.CDP.Contacting.ProviderSection":
                self._provider_depth = 1
        if self._provider_depth and attrs.get("aria-label") and not self.provider_company:
            self.provider_company = html.unescape(attrs["aria-label"]).strip()
        if tag == "meta":
            key = attrs.get("property") or attrs.get("name")
            if key and attrs.get("content"):
                self.meta[key.lower()] = attrs["content"]
        elif tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self._script = True
            self._buffer = ""
        elif tag == "title":
            self._title = True

    def handle_data(self, data):
        if self._script:
            self._buffer += data
        if self._title:
            self.title += data
        if self._provider_depth and data.strip():
            self.provider_text.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "div" and self._provider_depth:
            self._provider_depth -= 1
            if not self._provider_depth:
                self._provider_done = True
        if tag == "script" and self._script:
            try:
                data = json.loads(self._buffer)
                self.jsonld.extend(data if isinstance(data, list) else [data])
            except (ValueError, TypeError):
                pass
            self._script = False
        elif tag == "title":
            self._title = False


def _provider_person(text: str) -> str:
    text = re.split(r"\b(?:Dein Kontakt|Your contact)\b", text, maxsplit=1, flags=re.I)[0]
    match = re.search(
        r"\b(?:Herrn?|Frau)\s+([A-ZÄÖÜ][\wÄÖÜäöüß'’.-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß'’.-]*){1,3})\b",
        text,
    )
    return match.group(1).strip() if match else ""


def _structured_provider(nodes: list[dict]) -> tuple[str, str]:
    company = ""
    contact = ""
    for node in nodes:
        for key in ("seller", "provider", "realEstateAgent", "broker"):
            value = node.get(key)
            candidates = value if isinstance(value, list) else [value]
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                name = str(candidate.get("name") or "").strip()
                kind = str(candidate.get("@type") or "").casefold()
                if name and kind == "person" and not contact:
                    contact = name
                elif name and not company:
                    company = name
                point = candidate.get("contactPoint")
                if isinstance(point, dict) and not contact:
                    contact = str(point.get("name") or "").strip()
    return company, contact


def _first(*values):
    return next((value for value in values if value not in (None, "", [])), None)


def _number(value):
    if isinstance(value, dict):
        value = _first(value.get("value"), value.get("amount"))
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"\d[\d.,\s]*", value)
    if not match:
        return None
    raw = match.group().strip().replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".") if len(raw.rsplit(",", 1)[-1]) <= 2 else raw.replace(",", "")
    elif raw.count(".") > 1 or ("." in raw and len(raw.rsplit(".", 1)[-1]) == 3):
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _nodes(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _nodes(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _nodes(item)


def split_street(street: str) -> tuple[str, str]:
    """Split 'Hauptstr. 12a' in Strasse und Hausnummer (nur abschliessende Nummer)."""
    match = re.match(r"^(.*?)[\s,]+(\d+\s*[a-zA-Z]?(?:\s*[-/]\s*\d+\s*[a-zA-Z]?)?)$", (street or "").strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return (street or "").strip(), ""


def _text_match(pattern: str, text: str) -> str:
    match = re.search(pattern, text or "", re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _embedded_json_value(text: str, key: str):
    unescaped = text
    slash_quote = chr(92) + chr(34)
    while slash_quote in unescaped:
        unescaped = unescaped.replace(slash_quote, chr(34))
    matches = list(re.finditer(rf'"{re.escape(key)}"\s*:', unescaped))
    for match in reversed(matches):
        start = unescaped.find("{", match.end())
        if start < 0 or start - match.end() > 2:
            continue
        try:
            return json.JSONDecoder().raw_decode(unescaped, start)[0]
        except json.JSONDecodeError:
            continue
    return None


def extract_extra_facts(text: str) -> dict:
    """Konservative Zusatzfakten (Baujahr, Energieklasse, Geschoss, Kaltmiete) aus Freitext."""
    baujahr = _text_match(r"baujahr[:\s]*(?:ca\.?\s*)?((?:18|19|20)\d{2})", text)
    energie = _text_match(r"energie(?:effizienz)?klasse[:\s]*([A-H][+-]?)", text.upper()) or \
        _text_match(r"effizienzklasse[:\s]*([A-H][+-]?)", text.upper())
    geschoss = _text_match(
        r"((?:\d{1,2})\.\s*(?:geschoss|og|obergeschoss|etage)|erdgeschoss|\beg\b|dachgeschoss|\bdg\b)",
        text)
    annual_rent = _text_match(
        r"(?:jährliche[nr]?\s+(?:netto)?kaltmiete|(?:(?:ist[-\s]?)?mieteinnahmen|(?:netto)?kaltmiete)"
        r"\s*(?:pro\s+jahr|jährlich|p\.?\s*a\.?))"
        r"\s*[:=]?\s*(?:€|eur|euro)?\s*([\d.,]+)", text)
    if not annual_rent:
        annual_rent = _text_match(
            r"(?:netto)?kaltmiete\s*[:=]?\s*(?:€|eur|euro)?\s*([\d.,]+)\s*(?:€|eur|euro)?"
            r"\s*(?:pro\s+jahr|jährlich|p\.?\s*a\.?)", text)
    if annual_rent:
        annual_amount = _number(annual_rent)
        kaltmiete = round(annual_amount / 12, 2) if annual_amount is not None else None
    else:
        kaltmiete = _number(_text_match(
            r"(?:netto)?kaltmiete(?:\s*ist)?[:\s]*(?:ca\.?\s*)?(?:von\s*)?([\d.,\s]+)\s*(?:€|eur|euro)",
            text))
        if kaltmiete is None:
            kaltmiete = _number(_text_match(r"([\d.,]+)\s*€\s*(?:netto)?kaltmiete", text))
    return {
        "baujahr": float(baujahr) if baujahr else None,
        "energieklasse": energie.rstrip("+") or None,
        "geschoss": geschoss or None,
        "kaltmiete": kaltmiete,
    }


def extract_embedded_state(text: str) -> dict:
    """Fallback fuer JS-gerenderte Portale (z. B. Immowelt): maskiertes JSON im Seiten-Payload."""
    unesc = text.replace('\\\\"', '"').replace('\\"', '"')

    def field(pattern: str, source: str = unesc) -> str | None:
        match = re.search(pattern, source)
        return match.group(1) if match else None

    out: dict = {"title": field(r'"headline":"((?:[^"\\]|\\.)*)"\},"hardFacts"'),
                 "price": _number(field(r'"price":(\d+)') or field(r'"price":\{"value":"([\d.,]+)')),
                 "rooms": _number(field(r'"type":"numberOfRooms","value":"[^"]*","splitValue":"([\d,]+)"')),
                 "area": _number(field(r'"type":"livingSpace","value":"[^"]*","splitValue":"([\d,]+)"')),
                 "geschoss": field(r'"type":"numberOfFloors","value":"([^"]+)"'),
                 "baujahr": _number(field(r'"type":"yearOfConstruction","label":"[^"]*","value":"(\d{4})"')
                                    or field(r'"Baujahr":(\d{4})')),
                 "energieklasse": field(r'"efficiencyClass":\{"rating":"([A-H]\+?)"')}
    if out["area"] is None:
        out["area"] = _number(field(r'"Wohnflaeche":([\d.,]+)'))
    address = re.search(r'"address":\{([^{}]*)\},"isAddressPublished"', unesc) or \
        re.search(r'"address":\{([^{}]*"zipCode"[^{}]*)\}', unesc)
    if address:
        block = address.group(1)
        out["ort"] = field(r'"city":"([^"]*)"', block) or ""
        out["plz"] = field(r'"zipCode":"([^"]*)"', block) or ""
        out["stadtteil"] = field(r'"district":"([^"]*)"', block) or ""
        out["strasse"] = field(r'"street":"([^"]*)"', block) or ""
        out["hausnummer"] = field(r'"houseNumber":"([^"]*)"', block) or ""
    extras = extract_extra_facts(unesc)
    out["kaltmiete"] = extras["kaltmiete"]
    if not out.get("baujahr"):
        out["baujahr"] = extras["baujahr"]
    if not out.get("energieklasse"):
        out["energieklasse"] = extras["energieklasse"]
    if not out.get("geschoss"):
        out["geschoss"] = extras["geschoss"]
    documents = _embedded_json_value(text, "documents")
    out["energy_certificate_files"] = [
        {"url": item.get("url"), "title": item.get("title")}
        for item in (documents.get("files", []) if isinstance(documents, dict) else [])
        if isinstance(item, dict) and isinstance(item.get("url"), str)
    ]
    return out


def _read_pdf_text(pdf_data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_data), strict=False)
    return "\n".join(page.extract_text() or "" for page in list(reader.pages)[:20])


def _energy_certificate_address(text: str) -> dict:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    address_line = ""
    for index, line in enumerate(lines):
        if not re.fullmatch(r"Adresse", line, re.I):
            continue
        for offset in (-1, 1, -2, 2, 3):
            candidate_index = index + offset
            if 0 <= candidate_index < len(lines) and re.search(r"\b\d{5}\b", lines[candidate_index]):
                address_line = lines[candidate_index]
                break
        if address_line:
            break
    if not address_line:
        return {}
    address = address_line.strip(" ,;")
    postal_match = re.search(r"\b(\d{5})\b", address)
    if not postal_match:
        return {}
    street_text = address[:postal_match.start()].strip(" ,;").replace("–", "-").replace("—", "-")
    street_text = re.sub(r"(?<=[A-Za-zÄÖÜäöüß])(?=\d)", " ", street_text)
    street, number = split_street(street_text)
    locality = address[postal_match.end():].strip(" ,;")
    if not street or not number:
        return {}
    return {"strasse": street, "hausnummer": number,
            "plz": postal_match.group(1), "ort": locality}


def extract_energy_certificate_facts(page: bytes) -> dict:
    """Read the address from an attached energy certificate PDF when available."""
    raw_text = page.decode("utf-8", errors="replace")
    files = extract_embedded_state(raw_text).get("energy_certificate_files", [])
    for document in files:
        title = str(document.get("title") or "")
        if not re.search(r"energieausweis|energy\s*certificate", title, re.I):
            continue
        try:
            final_url, pdf_data, content_type = fetch_public(document["url"], limit=8_000_000)
            if "pdf" not in content_type.lower() and not pdf_data.startswith(b"%PDF-"):
                continue
            pdf_text = _read_pdf_text(pdf_data)
        except ImportError:
            return {"energy_certificate_note": "Energieausweis-PDF nicht lesbar: pypdf fehlt."}
        except Exception:
            continue
        address = _energy_certificate_address(pdf_text)
        if address:
            address["energy_certificate_source"] = f"{title}: {final_url}"
            address["energy_certificate_address"] = ", ".join((
                f"{address['strasse']} {address['hausnummer']}",
                f"{address['plz']} {address['ort']}"))
            return address
    return {}


def extract_listing(page: bytes, base_url: str) -> dict:
    raw_text = page.decode("utf-8", errors="replace")
    parser = ListingParser()
    parser.feed(raw_text)
    nodes = list(_nodes(parser.jsonld))
    property_node = next((n for n in nodes if any(word in str(n.get("@type", "")).lower() for word in
                          ("residence", "house", "apartment", "realestate", "product"))), {})
    offers = property_node.get("offers") or next((n for n in nodes if "price" in n), {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    address = property_node.get("address") or next((n for n in nodes if "addressLocality" in n), {})
    if isinstance(address, str):
        address = {"streetAddress": address}
    locality = address.get("addressLocality", "") if isinstance(address, dict) else ""
    street = address.get("streetAddress", "") if isinstance(address, dict) else ""
    postal = address.get("postalCode", "") if isinstance(address, dict) else ""
    image = _first(property_node.get("image"), parser.meta.get("og:image"), parser.meta.get("twitter:image"))
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url")
    title = html.unescape(str(_first(property_node.get("name"), parser.meta.get("og:title"), parser.title, "Neue Immobilie"))).strip()[:180]
    description = html.unescape(str(_first(property_node.get("description"), parser.meta.get("og:description"), parser.meta.get("description"), ""))).strip()[:5000]
    extras = extract_extra_facts(" ".join((title, description, raw_text)))
    structured_company, structured_contact = _structured_provider(nodes)
    provider_text = " ".join(parser.provider_text)
    strasse, hausnummer = split_street(street)
    stadtteil = ""
    if "-" in locality:
        locality_parts = locality.split("-", 1)
        locality, stadtteil = locality_parts[0].strip(), locality_parts[1].strip()
    result = {
        "title": title, "description": description,
        "price": _number(offers.get("price") if isinstance(offers, dict) else None),
        "area": _number(_first(property_node.get("floorSize"), property_node.get("size"))),
        "rooms": _number(_first(property_node.get("numberOfRooms"), property_node.get("numberOfBedrooms"))),
        "address": ", ".join(x for x in (street, f"{postal} {locality}".strip()) if x),
        "locality": locality, "image_url": urllib.parse.urljoin(base_url, image) if image else None,
        "source_url": base_url,
        "strasse": strasse, "hausnummer": hausnummer, "plz": postal or "",
        "ort": locality, "stadtteil": stadtteil,
        "baujahr": extras["baujahr"], "energieklasse": extras["energieklasse"],
        "geschoss": extras["geschoss"], "kaltmiete": extras["kaltmiete"],
        "maklerfirma": parser.provider_company or structured_company,
        "ansprechpartner": _provider_person(provider_text) or structured_contact,
    }
    # Fallback fuer JS-gerenderte Portale: fehlende Felder aus eingebettetem JSON ergaenzen
    fallback = extract_embedded_state(raw_text)
    if fallback.get("title") and (result["title"] == "Neue Immobilie" or "zum Kauf" in result["title"]):
        result["title"] = html.unescape(fallback["title"])[:180]
    for key in ("price", "area", "rooms", "geschoss", "baujahr", "energieklasse", "kaltmiete"):
        if result.get(key) in (None, "") and fallback.get(key) not in (None, ""):
            result[key] = fallback[key]
    for key in ("strasse", "hausnummer", "plz", "ort", "stadtteil"):
        if not result.get(key) and fallback.get(key):
            result[key] = fallback[key]
    if not result["locality"] and result["ort"]:
        result["locality"] = result["ort"]
    if not result["address"]:
        result["address"] = ", ".join(x for x in (
            f"{result['strasse']} {result['hausnummer']}".strip(),
            f"{result['plz']} {result['ort']}".strip()) if x)
    return result
