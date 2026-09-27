"""Conservative public listing extraction; no login, captcha bypass or guessed facts."""
from __future__ import annotations

import html
import ipaddress
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
            "User-Agent": "Mozilla/5.0 (compatible; ImmoInvestanalyse/1.0)",
            "Accept": "text/html,image/avif,image/webp,image/*;q=0.8,*/*;q=0.5",
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

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
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

    def handle_endtag(self, tag):
        if tag == "script" and self._script:
            try:
                data = json.loads(self._buffer)
                self.jsonld.extend(data if isinstance(data, list) else [data])
            except (ValueError, TypeError):
                pass
            self._script = False
        elif tag == "title":
            self._title = False


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


def extract_listing(page: bytes, base_url: str) -> dict:
    parser = ListingParser()
    parser.feed(page.decode("utf-8", errors="replace"))
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
    return {
        "title": title, "description": description,
        "price": _number(offers.get("price") if isinstance(offers, dict) else None),
        "area": _number(_first(property_node.get("floorSize"), property_node.get("size"))),
        "rooms": _number(_first(property_node.get("numberOfRooms"), property_node.get("numberOfBedrooms"))),
        "address": ", ".join(x for x in (street, f"{postal} {locality}".strip()) if x),
        "locality": locality, "image_url": urllib.parse.urljoin(base_url, image) if image else None,
        "source_url": base_url,
    }
