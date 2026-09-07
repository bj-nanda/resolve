"""Assemble resolve_prototype.html from template + results JSONs."""
import json

triage = json.load(open('triage_results.json'))
triage_ex = json.load(open('triage_examples.json'))
sentinel = json.load(open('sentinel_results.json'))
copilot = json.load(open('copilot_results.json'))

THEME_NAMES = {
    0: 'Funds availability / deposit holds',
    1: 'Merchant disputes — evidence ignored',
    2: '360 Savings rate practices',
    3: 'FCRA inaccurate reporting',
    4: 'Identity theft / fraudulent accounts',
    5: 'Direct deposit delays',
    6: 'Late fees & payment posting',
    7: 'Credit-repair template letters (15 USC 1681)',
    8: 'Debt validation (FDCPA)',
    9: 'Unauthorized hard inquiries',
    10: 'Auto finance servicing',
    11: 'Card servicing / call-center runaround',
}
for t in sentinel['themes']:
    t['name'] = THEME_NAMES[t['id']]

data = {'triage': triage, 'triage_ex': triage_ex, 'sentinel': sentinel, 'copilot': copilot}
import os, datetime
# Live corpus counts (from fetch_data.py); fall back gracefully if absent.
try:
    data['counts'] = json.load(open('counts.json'))
except Exception:
    data['counts'] = {'analyzed': None, 'all_time_total': None}
# --- Alert history: a permanent log of every spike Sentinel has flagged ---
# Spikes decay by design (a surge eventually becomes part of the baseline), so the
# history keeps past detections visible after the live alert clears. Never edited
# by hand: entries are appended/updated by this nightly build only.
HIST = 'alert_history.json'
today = datetime.date.today().isoformat()
try:
    history = json.load(open(HIST))
except Exception:
    history = []
months = sentinel['months']
window = f"{months[-3]} – {months[-1]}" if len(months) >= 3 else '—'
active_names = set()
for sp in sentinel['spikes']:
    th = next(t for t in sentinel['themes'] if t['id'] == sp['id'])
    active_names.add(th['name'])
    e = next((h for h in history if h['theme'] == th['name'] and h['status'] == 'active'), None)
    if e is None:
        e = {'theme': th['name'], 'first_seen': today, 'peak_z': sp['z'], 'peak_seen': today,
             'peak_window': window, 'peak_base_share': sp['base_share'], 'peak_recent_share': sp['recent_share'],
             'status': 'active'}
        history.append(e)
    if sp['z'] > e['peak_z']:
        e.update(peak_z=sp['z'], peak_seen=today, peak_window=window,
                 peak_base_share=sp['base_share'], peak_recent_share=sp['recent_share'])
    e.update(last_seen=today, latest_z=sp['z'], latest_window=window,
             latest_base_share=sp['base_share'], latest_recent_share=sp['recent_share'],
             top_terms=th['top_terms'][:6], top_issue=th['top_issue'])
for e in history:
    if e['status'] == 'active' and e['theme'] not in active_names:
        e['status'] = 'cleared'; e['cleared_on'] = today   # fell back under 2σ
history.sort(key=lambda h: h['first_seen'], reverse=True)
json.dump(history, open(HIST, 'w'), indent=1)
data['alert_history'] = history

tpl = open(os.path.join(os.path.dirname(__file__), 'template.html')).read()
data['built'] = datetime.date.today().isoformat()
html = tpl.replace('__DATA__', json.dumps(data))
open('index.html', 'w').write(html)
print('built', len(html), 'bytes')
