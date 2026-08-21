"""Download the latest Capital One complaint narratives from the CFPB public API.

The CFPB endpoint rejects some User-Agent strings with HTTP 403 (inconsistently),
so we try a sequence of request strategies and retries until one succeeds.
"""
import urllib.request, urllib.error, sys, time

URL = ("https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
       "?company=CAPITAL%20ONE%20FINANCIAL%20CORPORATION"
       "&date_received_min=2025-01-01&has_narrative=true"
       "&format=csv&no_aggs=true&size=25000")

STRATEGIES = [
    {},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
     "Accept": "text/csv,*/*"},
    {"User-Agent": "curl/8.4.0"},
]

def download():
    last_err = None
    for attempt in range(2):
        for headers in STRATEGIES:
            try:
                req = urllib.request.Request(URL, headers=headers)
                with urllib.request.urlopen(req, timeout=300) as r:
                    data = r.read()
                if len(data) > 100_000:
                    return data
                last_err = f"suspiciously small response ({len(data)} bytes)"
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}"
            except Exception as e:
                last_err = str(e)
            time.sleep(3)
    raise RuntimeError(f"all download strategies failed; last error: {last_err}")

data = download()
with open("capone_narratives_2025plus.csv", "wb") as f:
    f.write(data)

lines = sum(1 for _ in open("capone_narratives_2025plus.csv", "rb"))
print(f"downloaded CSV: {len(data)} bytes, {lines} lines")
if lines < 1000:
    sys.exit("Download looks too small — aborting so the site keeps its previous data.")
