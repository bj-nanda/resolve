"""Resolve — Triage classifier: complaint narrative -> regulatory lane."""
import pandas as pd, numpy as np, json, re
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score

df = pd.read_csv('capone_narratives_2025plus.csv')

# --- Lane labeling from CFPB product/issue taxonomy (ground truth proxy) ---
def lane(row):
    p, i, s = str(row['Product']), str(row['Issue']), str(row['Sub-issue'])
    if 'Credit reporting' in p or 'report' in i.lower():
        return 'FCRA — credit reporting'
    if 'Debt collection' in p:
        return 'FDCPA — debt collection'
    if p in ('Checking or savings account',) and re.search(r'deposit|withdraw|transfer|unauthorized|error', (i+s).lower()):
        return 'Reg E — EFT dispute'
    if 'Credit card' in p and re.search(r'purchase shown|dispute|fees or interest|billing', (i+s).lower()):
        return 'Reg Z — billing dispute'
    return 'General servicing'

df['lane'] = df.apply(lane, axis=1)
df = df.dropna(subset=['Consumer complaint narrative'])
print('Lane distribution:'); print(df['lane'].value_counts().to_string())

X = df['Consumer complaint narrative']
y = df['lane']
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

pipe = Pipeline([
    ('tfidf', TfidfVectorizer(max_features=40000, ngram_range=(1,2), min_df=3, sublinear_tf=True, stop_words='english')),
    ('clf', LogisticRegression(max_iter=2000, C=4.0, class_weight='balanced')),
])
pipe.fit(X_tr, y_tr)
pred = pipe.predict(X_te)
rep = classification_report(y_te, pred, output_dict=True)
print(classification_report(y_te, pred))
labels = sorted(y.unique())
cm = confusion_matrix(y_te, pred, labels=labels)
print('Confusion matrix (rows=true):')
print(pd.DataFrame(cm, index=labels, columns=labels).to_string())

# Confidence-based routing: high-confidence auto-route vs human review queue
proba = pipe.predict_proba(X_te)
conf = proba.max(axis=1)
for thresh in (0.5, 0.7, 0.8):
    mask = conf >= thresh
    acc = (pred[mask] == y_te.values[mask]).mean()
    print(f"conf>={thresh}: coverage {mask.mean():.1%}, accuracy {acc:.1%}")

out = {
    'macro_f1': round(f1_score(y_te, pred, average='macro'), 3),
    'accuracy': round(rep['accuracy'], 3),
    'per_lane': {k: {'precision': round(v['precision'],3), 'recall': round(v['recall'],3), 'f1': round(v['f1-score'],3), 'support': int(v['support'])} for k,v in rep.items() if k in labels},
    'labels': labels,
    'confusion': cm.tolist(),
    'lane_counts': df['lane'].value_counts().to_dict(),
    'routing': {str(t): {'coverage': round(float((conf>=t).mean()),3), 'accuracy': round(float((pred[conf>=t]==y_te.values[conf>=t]).mean()),3)} for t in (0.5,0.7,0.8)},
}
json.dump(out, open('triage_results.json','w'), indent=1)

# Save example predictions for the demo (short, varied, correctly & interestingly routed)
ex = []
te = pd.DataFrame({'text': X_te, 'true': y_te, 'pred': pred, 'conf': conf})
te['len'] = te['text'].str.len()
for lane_name in labels:
    sub = te[(te['pred']==lane_name) & (te['true']==lane_name) & te['len'].between(200,500)].nlargest(2,'conf')
    for _, r in sub.iterrows():
        ex.append({'text': r['text'], 'lane': r['pred'], 'conf': round(float(r['conf']),2)})
json.dump(ex, open('triage_examples.json','w'), indent=1)
print('saved results + examples')
