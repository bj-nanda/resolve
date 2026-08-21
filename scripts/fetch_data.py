"""Download the latest Capital One complaint narratives from the CFPB public API."""
import urllib.request, sys

URL = ("https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
       "?company=CAPITAL%20ONE%20FINANCIAL%20CORPORATION"
       "&date_received_min=2025-01-01&has_narrative=true"
       "&format=csv&no_aggs=true&size=25000")

req = urllib.request.Request(URL, headers={"User-Agent": "resolve-poc/1.0 (research project)"})
with urllib.request.urlopen(req, timeout=300) as r, open("capone_narratives_2025plus.csv", "wb") as f:
    f.write(r.read())

lines = sum(1 for _ in open("capone_narratives_2025plus.csv", "rb"))
print(f"downloaded CSV: {lines} lines")
if lines < 1000:
    sys.exit("Download looks too small — aborting so the site keeps its previous data.")
