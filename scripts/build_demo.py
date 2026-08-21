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
tpl = open(os.path.join(os.path.dirname(__file__), 'template.html')).read()
data['built'] = datetime.date.today().isoformat()
html = tpl.replace('__DATA__', json.dumps(data))
open('index.html', 'w').write(html)
print('built', len(html), 'bytes')
