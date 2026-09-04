"""Resolve — Sentinel: root-cause theme extraction + emerging-issue detection."""
import pandas as pd, numpy as np, json, re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF

df = pd.read_csv('capone_narratives_2025plus.csv')
df['Date received'] = pd.to_datetime(df['Date received'], format='mixed', utc=True)
df = df.dropna(subset=['Consumer complaint narrative']).reset_index(drop=True)

# Clean: CFPB redactions (XXXX) and boilerplate dollar-brace tokens add noise
def clean(t):
    t = re.sub(r'X{2,}', ' ', t)
    t = re.sub(r'\{\$[\d.,]+\}', ' amount ', t)
    return t.lower()
texts = df['Consumer complaint narrative'].map(clean)

vec = TfidfVectorizer(max_features=30000, ngram_range=(1,2), min_df=10, max_df=0.4,
                      stop_words='english', sublinear_tf=True)
X = vec.fit_transform(texts)

K = 12
nmf = NMF(n_components=K, random_state=42, init='nndsvda', max_iter=400)
W = nmf.fit_transform(X)   # doc-topic
H = nmf.components_        # topic-term
terms = np.array(vec.get_feature_names_out())

df['theme'] = W.argmax(axis=1)
df['theme_strength'] = W.max(axis=1)

themes = []
for k in range(K):
    top_terms = terms[H[k].argsort()[::-1][:10]].tolist()
    sub = df[df['theme']==k]
    # representative narrative: strongest doc of moderate length
    cand = sub[sub['Consumer complaint narrative'].str.len().between(200,600)]
    rep = (cand.nlargest(1,'theme_strength')['Consumer complaint narrative'].iloc[0]
           if len(cand) else sub.nlargest(1,'theme_strength')['Consumer complaint narrative'].iloc[0])
    themes.append({'id': k, 'top_terms': top_terms, 'count': int(len(sub)),
                   'top_issue': sub['Issue'].mode().iloc[0] if len(sub) else '',
                   'rep': rep[:420]})
    print(f"\nTheme {k} (n={len(sub)}), issue mode: {themes[-1]['top_issue']}")
    print('  terms:', ', '.join(top_terms))

# Monthly trend per theme + spike detection (use Jan 2025 - Mar 2026; later months lag-suppressed)
df['month'] = df['Date received'].dt.tz_localize(None).dt.to_period('M').astype(str)
months = sorted(df['month'].unique())
months = months[:-2] if len(months) > 2 else months  # drop last 2 months (CFPB publication lag)
trend = {k: [] for k in range(K)}
totals = df[df['month'].isin(months)].groupby('month').size()
for k in range(K):
    s = df[(df['theme']==k) & df['month'].isin(months)].groupby('month').size()
    # share of month's volume -> robust to publication-lag volume swings
    trend[k] = [round(float(s.get(m,0))/float(totals.get(m,1))*100, 2) for m in months]

# Spike flag: last-3-month mean share vs prior baseline mean, z-ish score
spikes = []
for k in range(K):
    v = np.array(trend[k]); base, recent = v[:-3], v[-3:]
    if base.std() > 0:
        z = (recent.mean() - base.mean())/base.std()
        if z > 2.0: spikes.append({'id': k, 'z': round(float(z),2),
                                   'base_share': round(float(base.mean()),2), 'recent_share': round(float(recent.mean()),2)})
spikes.sort(key=lambda s: -s['z'])
print('\nSpikes (recent 3-mo vs baseline):', spikes)

json.dump({'themes': themes, 'months': months, 'trend': trend, 'spikes': spikes},
          open('sentinel_results.json','w'), indent=1)
print('saved sentinel results')
