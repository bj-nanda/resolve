"""Resolve — Investigator Copilot demo.
Pipeline: case -> evidence inventory (extraction) -> drafted letter (template layer,
LLM in production) -> deterministic citation validator (the zero-tolerance gate).
"""
import pandas as pd, json, re

df = pd.read_csv('capone_narratives_2025plus.csv')
df = df.dropna(subset=['Consumer complaint narrative'])

# --- 1. Evidence extraction (in production: LLM structured extraction; here: pattern layer) ---
EVIDENCE_PATTERNS = {
    'Receipt': r'\breceipts?\b',
    'Bank/card statement': r'\bstatements?\b',
    'Police report': r'\bpolice report\b',
    'FTC identity-theft report': r'\bftc\b.{0,30}\breport\b|\bidentity theft report\b',
    'Screenshot': r'\bscreen ?shots?\b',
    'Email/confirmation': r'\bconfirmation (email|number)\b|\bemail confirmation\b',
    'Tracking/delivery proof': r'\btracking\b|\bproof of delivery\b',
    'Photos': r'\bphotos?\b|\bpictures?\b',
    'Contract/agreement': r'\bcontract\b|\bagreement\b',
    'Dispute letter previously sent': r'\b(sent|mailed|submitted).{0,30}(dispute|letter)\b',
}
AMOUNT = re.compile(r'\{\$([\d.,]+)\}')

def extract(narrative):
    inv = [name for name, pat in EVIDENCE_PATTERNS.items() if re.search(pat, narrative, re.I)]
    amounts = AMOUNT.findall(narrative)
    return inv, amounts

# --- 2. Letter drafter: may only cite items present in the inventory ---
def draft_letter(case_id, lane, inventory, amounts, outcome='provisional'):
    amt = f"${amounts[0]}" if amounts else "the disputed charge"
    cites = '; '.join(f"[E{i+1}: {e}]" for i, e in enumerate(inventory)) if inventory else None
    if outcome == 'provisional':
        body = (f"We have opened an investigation into your dispute of {amt} (Case {case_id}). "
                f"Based on our initial review of the evidence you provided — {cites or 'your account records'} — "
                f"we have issued a provisional credit of {amt} to your account while our investigation is completed, "
                f"in accordance with your billing-error rights. We will notify you of the outcome within the "
                f"regulatory timeframe. No further action is required from you at this time.")
    else:
        body = (f"We have completed our investigation of your dispute of {amt} (Case {case_id}). "
                f"Our determination is based on the following evidence reviewed: {cites or 'your account records'}. "
                f"A detailed summary of findings is enclosed. If you have additional documentation, "
                f"you may reopen this case at any time.")
    return body

# --- 3. Deterministic citation validator (zero-tolerance gate) ---
def validate(letter, inventory):
    cited = re.findall(r'\[E(\d+): ([^\]]+)\]', letter)
    failures = [f"E{n}" for n, name in cited
                if int(n) > len(inventory) or inventory[int(n)-1] != name]
    return {'citations': len(cited), 'failures': failures, 'passed': not failures}

# --- Build demo cases: real Reg Z-flavored dispute narratives with rich evidence ---
pool = df[df['Sub-issue'].astype(str).str.contains("resolving a dispute", case=False, na=False)]
pool = pool[pool['Consumer complaint narrative'].str.len().between(350, 900)]
demo, seen = [], set()
for _, r in pool.iterrows():
    inv, amounts = extract(r['Consumer complaint narrative'])
    key = tuple(inv)
    if len(inv) >= 2 and key not in seen and len(demo) < 6:
        seen.add(key)
        cid = f"RZ-2026-{1000+len(demo)}"
        letter = draft_letter(cid, 'Reg Z', inv, amounts)
        v = validate(letter, inv)
        demo.append({'case_id': cid, 'state': r['State'], 'date': str(r['Date received'])[:10],
                     'narrative': r['Consumer complaint narrative'], 'inventory': inv,
                     'amounts': amounts[:3], 'letter': letter, 'validator': v})

# Negative demo: a deliberately corrupted draft (cites nonexistent evidence) -> validator blocks
bad_letter = demo[0]['letter'].replace(']', '] and [E9: Merchant response letter]', 1)
demo_bad = {'case_id': demo[0]['case_id'], 'letter': bad_letter,
            'validator': validate(bad_letter, demo[0]['inventory'])}

# Extraction coverage stat across the dispute pool
pool_inv = pool['Consumer complaint narrative'].map(lambda t: len(extract(t)[0]))
stats = {'pool_size': int(len(pool)),
         'pct_with_evidence_mentions': round(float((pool_inv > 0).mean())*100, 1),
         'avg_items_when_present': round(float(pool_inv[pool_inv>0].mean()), 2)}
print(stats)
for d in demo:
    print(d['case_id'], d['inventory'], 'validator:', d['validator']['passed'])
print('corrupted draft validator:', demo_bad['validator'])

json.dump({'cases': demo, 'bad_case': demo_bad, 'stats': stats},
          open('copilot_results.json','w'), indent=1)
print('saved copilot results')
