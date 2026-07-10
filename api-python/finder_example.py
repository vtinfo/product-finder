"""
VIP Brand Finder - Web Services (API) example in Python.

WHAT THIS DOES
--------------
Calls VIP's Brand Finder "results" action to list retail locations near a
ZIP code (here: 05446) that recently sold your products, then prints them.

This is an EXAMPLE implementation meant to teach the request-signing flow.
It is deliberately verbose and uses ONLY the Python standard library so you
can drop it anywhere with a stock Python 3.13 install (no `pip install`).

For a real integration you would:
  - call this from your own backend (never expose your API secret to a browser),
  - cache the slow-changing "brands"/"package"/"category" lookups,
  - add real error handling, retries, and logging.

HOW SIGNING WORKS (the #1 source of support tickets)
----------------------------------------------------
Every request carries three headers:
  vipCustID    - your 3-5 character VIP customer ID
  vipTimestamp - GMT time, seconds forced to :00 (see build_timestamp)
  vipSignature - lowercase SHA-256 hex of these 4 pieces concatenated,
                 IN THIS EXACT ORDER, with NO separators between them:

                     vipTimestamp + yourSecret + queryString + vipCustID

Two rules that trip people up:
  1. The queryString used to BUILD the signature must be byte-for-byte the
     same string you actually send in the URL. We build it once and reuse it.
  2. Your server clock must be within ~10 minutes of VIP's (GMT). VIP tries a
     +/-10 minute window of timestamps, so small drift is tolerated.

RUN IT
------
  # PowerShell
  $env:FINDER_SAMPLE_VIP_SECRET = "your-secret-here"
  python finder_example.py

  # bash
  export FINDER_SAMPLE_VIP_SECRET="your-secret-here"
  python finder_example.py
"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration - edit these for your own customer / search.
# ---------------------------------------------------------------------------

# The public Brand Finder API endpoint. Confirm the exact host with VIP;
# this is the documented path.
API_URL = "https://api.vtinfo.com/analytics/v2/finder"

# Your VIP customer ID (3 or 5 characters). Provided by VIP.
CUST_ID = "VIP"

# The shared API secret. NEVER hard-code this or commit it. We read it from an
# environment variable so it stays out of source control.
#
# NOTE: when you use an Implementation (UUID) below, this secret must be that
# Implementation's secret, NOT your customer-level API secret. VIP validates
# the signature against the Implementation secret when a UUID is present.
API_SECRET_ENV_VAR = "FINDER_SAMPLE_VIP_SECRET"

# OPTIONAL: Implementation ("UUID") support.
# VIP's Implementation system (the recommended way to configure data filters,
# themes, markers, analytics, etc.) produces a UUID. Passing it lets you change
# configuration on VIP's side with no code change here. Leave the env var unset
# to run a plain customer-level query without an Implementation.
UUID_ENV_VAR = "FINDER_SAMPLE_VIP_UUID"

# The search we want to run. See VIP's web service docs for every parameter.
# NOTE: order matters for the signature, so we keep this as an ordered list of
# (name, value) pairs rather than a dict. build_search_params() may prepend the
# optional UUID to this list at runtime.
SEARCH_PARAMS = [
    ("custID", CUST_ID),   # required on every call; must match the vipCustID header
    ("action", "results"), # "results" = nearby locations (vs. brands/package/category)
    ("format", "JSON"),    # ask for JSON instead of the default XML
    ("zip", "05446"),      # 5-digit ZIP to search around (Colchester, VT)
    ("miles", "10"),       # search radius in miles (1-100, default 10)
    ("page", "0"),         # 0 = first page of results
    ("pagesize", "50"),    # max 400
]


def build_search_params() -> list[tuple[str, str]]:
    """
    Return the ordered (name, value) pairs to send, adding the optional UUID.

    If the UUID env var is set, we include it as a "UUID" query parameter so
    VIP applies that Implementation's configuration. We place it right after
    custID; any stable order is fine as long as the SAME order is used for both
    the signature and the URL (which it is, since both come from this list).
    """
    params = list(SEARCH_PARAMS)
    uuid = os.environ.get(UUID_ENV_VAR)
    if uuid:
        params.insert(1, ("UUID", uuid))
    return params

# English weekday/month names. We spell these out instead of using strftime()
# because strftime is locale-dependent, and VIP expects English names.
_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def build_timestamp(now: datetime) -> str:
    """
    Format the current time exactly the way VIP expects, e.g.:

        Tue, 17 Sep 2019 17:41:00 GMT

    Rules that must be followed precisely:
      - English weekday and month abbreviations.
      - Day number has NO leading zero (e.g. "1", not "01").
      - Hours/minutes are 2 digits, 24-hour clock.
      - Seconds are always "00".
      - Trailing " GMT" (the time itself is UTC/GMT).
    """
    gmt = now.astimezone(timezone.utc)
    weekday = _WEEKDAYS[gmt.weekday()]
    month = _MONTHS[gmt.month - 1]
    # %-d isn't portable (fails on Windows), so we format the day ourselves.
    return f"{weekday}, {gmt.day} {month} {gmt.year} {gmt.hour:02d}:{gmt.minute:02d}:00 GMT"


def build_query_string(params: list[tuple[str, str]]) -> str:
    """
    Build the URL query string, URL-encoding each value.

    We URL-encode the VALUES here (before signing) because VIP hashes the
    same encoded string it receives. We keep the pairs in the given order and
    never duplicate a parameter name - both matter for the signature to match.

    Returns something like: custID=VIP&action=results&format=JSON&zip=05446...
    (no leading "?").
    """
    # quote_via=urllib.parse.quote encodes spaces as %20 (VIP's preferred form).
    return urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def build_signature(timestamp: str, secret: str, query_string: str, cust_id: str) -> str:
    """
    SHA-256 hex of: timestamp + secret + queryString + custID  (no separators).

    The result is 64 lowercase hex characters. .hexdigest() is already
    lowercase, which is exactly what VIP requires.
    """
    value_to_hash = timestamp + secret + query_string + cust_id
    return hashlib.sha256(value_to_hash.encode("utf-8")).hexdigest()


def call_finder(secret: str) -> dict:
    """Sign and send one Finder API request, returning the parsed JSON body."""
    # 1) Build the query string ONCE and reuse it for both signing and the URL.
    #    build_search_params() adds the optional Implementation UUID if set.
    query_string = build_query_string(build_search_params())

    # 2) Build the timestamp and signature over that exact query string.
    timestamp = build_timestamp(datetime.now(timezone.utc))
    signature = build_signature(timestamp, secret, query_string, CUST_ID)

    # 3) Assemble the request. The signed params go in the URL; auth in headers.
    url = f"{API_URL}?{query_string}"
    request = urllib.request.Request(url, method="GET")
    request.add_header("vipCustID", CUST_ID)
    request.add_header("vipTimestamp", timestamp)
    request.add_header("vipSignature", signature)

    print(f"GET {url}")
    print(f"  vipTimestamp: {timestamp}")
    print(f"  vipSignature: {signature}\n")

    # 4) Send it. We only accept HTTPS - plain HTTP is not supported by VIP.
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")

    return json.loads(body)


def print_locations(result: dict) -> None:
    """
    Pretty-print the location results.

    The exact JSON shape can vary; this walks it defensively and falls back to
    dumping the raw payload so the example still teaches you something if the
    structure differs from what we assumed.
    """
    # Based on the actual API response, locations are directly under "location" key
    locations = None
    if isinstance(result, dict):
        # Try the actual key name from the JSON response first
        value = result.get("location")
        if isinstance(value, list):
            locations = value
        else:
            # Fall back to checking other common key names
            for key in ("locations", "results", "data"):
                value = result.get(key)
                if isinstance(value, list):
                    locations = value
                    break

    if not locations:
        print("No location list found in the response. Raw payload:")
        print(json.dumps(result, indent=2))
        return

    print(f"Found {len(locations)} location(s):\n")
    for i, loc in enumerate(locations, start=1):
        # Field names adjusted to match the actual API response
        name = (loc.get("dba") or loc.get("name") or loc.get("outletName") or "(unknown)").strip()
        # The actual response has "street" field for address
        street = loc.get("street", "").strip()
        city = loc.get("city", "").strip()
        state = loc.get("state", "").strip()
        distance = loc.get("distance") or loc.get("miles") or ""

        print(f"{i:>3}. {name}")
        if street or city or state:
            print(f"     {street}, {city} {state}".rstrip(", "))
        if distance != "":
            print(f"     ~{distance} miles away")
        print()  # blank line between locations for readability


def main() -> int:
    # Read the secret from the environment; fail loudly if it's missing.
    secret = os.environ.get(API_SECRET_ENV_VAR)
    if not secret:
        print(
            f"ERROR: environment variable {API_SECRET_ENV_VAR} is not set.\n"
            f"Set it to your VIP API secret and re-run. See the header of this "
            f"file for how.",
            file=sys.stderr,
        )
        return 1

    try:
        result = call_finder(secret)
    except urllib.error.HTTPError as e:
        # Non-2xx response. A 401/403 almost always means the signature or
        # timestamp is off - re-read the signing rules at the top of this file.
        print(f"HTTP {e.code} error: {e.reason}", file=sys.stderr)
        print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        return 1

    print_locations(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
