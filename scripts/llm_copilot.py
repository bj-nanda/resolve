"""Resolve — Investigator Copilot, LLM-backed version.

Drop-in upgrade for copilot.py. The two "understanding" layers become LLM calls;
the deterministic citation validator is unchanged and now acts as a retry gate.

    Layer                      copilot.py (demo)     llm_copilot.py (this file)
    1. Evidence extraction     regex patterns        LLM structured output + grounding check
    2. Letter drafting         f-string template     LLM generation, constrained to inventory
    3. Citation validator      deterministic         deterministic (UNCHANGED — the gate)

Run locally:
    pip install anthropic pandas
    export ANTHROPIC_API_KEY=sk-ant-...
    python llm_copilot.py                # regenerates copilot_results.json
    python build_demo.py                 # rebuilds resolve_prototype.html with LLM output

Cost: 6 demo cases = 12 small calls; well under $0.05 with the default model.
"""
import os, json, re, sys
import pandas as pd

MODEL = os.environ.get("RESOLVE_MODEL", "claude-haiku-4-5")
N_CASES = 6

# ---------------------------------------------------------------- LLM client
try:
    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
except Exception as e:
    sys.exit(f"Install the SDK and set ANTHROPIC_API_KEY first ({e})")

# ------------------------------------------------- 1. LLM evidence extraction
# Structured output via forced tool use: the model must return JSON matching
# this schema — no free-text parsing. Each item carries a verbatim quote so we
# can run a deterministic GROUNDING CHECK (quote must appear in the narrative).
EXTRACT_TOOL = {
    "name": "record_evidence",
    "description": "Record every piece of evidence the customer says they have or submitted.",
    "input_schema": {
        "type": "object",
        "properties": {
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string",
                                  "description": "Short evidence-type label, e.g. 'Receipt', 'Police report', 'Doctor's documentation'"},
                        "quote": {"type": "string",
                                  "description": "Exact verbatim substring of the narrative proving this evidence exists"},
                    },
                    "required": ["label", "quote"],
                },
            },
            "disputed_amounts": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["evidence", "disputed_amounts"],
    },
}

def extract_llm(narrative: str):
    msg = client.messages.create(
        model=MODEL, max_tokens=1024,
        tools=[EXTRACT_TOOL], tool_choice={"type": "tool", "name": "record_evidence"},
        messages=[{"role": "user", "content":
            "Extract the evidence inventory from this credit-card dispute narrative. "
            "Only list evidence the customer states they possess or submitted — never "
            "infer evidence that is not mentioned.\n\n<narrative>\n" + narrative + "\n</narrative>"}],
    )
    data = next(b.input for b in msg.content if b.type == "tool_use")
    # Deterministic grounding check: drop any item whose quote isn't in the text.
    # (Same philosophy as the citation validator — gates are code, not prompts.)
    grounded, dropped = [], []
    for item in data.get("evidence", []):
        (grounded if item.get("quote", "") in narrative else dropped).append(item)
    return [i["label"] for i in grounded], data.get("disputed_amounts", []), dropped

# --------------------------------------------------- 2. LLM letter drafting
def draft_letter_llm(case_id, inventory, amounts, feedback=None):
    inv_list = "\n".join(f"[E{i+1}: {e}]" for i, e in enumerate(inventory))
    amt = amounts[0] if amounts else "the disputed charge"
    prompt = f"""Draft a customer response letter for credit-card billing dispute case {case_id}.

Context: initial acknowledgment under Reg Z billing-error rights; a provisional
credit for {amt} has been issued while the investigation proceeds.

STRICT RULES:
- You may cite ONLY these evidence items, using their exact bracket tags:
{inv_list}
- Never invent, rename, or renumber a citation. Every claim about the customer's
  evidence must carry its [E#: label] tag inline.
- Plain, warm, professional language. No legalese beyond what the rules require.
- 90-140 words. No subject line, no signature block."""
    if feedback:
        prompt += f"\n\nYour previous draft FAILED validation: {feedback}. Fix this and redraft."
    msg = client.messages.create(model=MODEL, max_tokens=600,
                                 messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text.strip()

# ------------------------------------- 3. Deterministic validator (unchanged)
def validate(letter, inventory):
    cited = re.findall(r"\[E(\d+): ([^\]]+)\]", letter)
    failures = [f"E{n}" for n, name in cited
                if int(n) > len(inventory) or inventory[int(n) - 1] != name]
    return {"citations": len(cited), "failures": failures, "passed": not failures}

def draft_with_gate(case_id, inventory, amounts, max_retries=2):
    """Generation -> validation loop. The gate, not the prompt, guarantees safety."""
    feedback = None
    for attempt in range(max_retries + 1):
        letter = draft_letter_llm(case_id, inventory, amounts, feedback)
        v = validate(letter, inventory)
        if v["passed"]:
            return letter, v, attempt
        feedback = f"unresolvable citations {v['failures']}"
    # Hard-fail fallback: assembled file + blank template, never a bad draft
    return None, v, max_retries

# ------------------------------------------------------------------- run demo
if __name__ == "__main__":
    df = pd.read_csv("capone_narratives_2025plus.csv").dropna(subset=["Consumer complaint narrative"])
    pool = df[df["Sub-issue"].astype(str).str.contains("resolving a dispute", case=False, na=False)]
    pool = pool[pool["Consumer complaint narrative"].str.len().between(350, 900)]

    demo, retries_total = [], 0
    for _, r in pool.head(30).iterrows():
        if len(demo) >= N_CASES:
            break
        narrative = r["Consumer complaint narrative"]
        inventory, amounts, dropped = extract_llm(narrative)
        if len(inventory) < 2:
            continue
        cid = f"RZ-2026-{1000 + len(demo)}"
        letter, v, attempts = draft_with_gate(cid, inventory, amounts)
        retries_total += attempts
        if letter is None:
            print(f"{cid}: draft blocked after retries — falls back to blank template")
            continue
        if dropped:
            print(f"{cid}: grounding check dropped {len(dropped)} ungrounded item(s)")
        demo.append({"case_id": cid, "state": r["State"], "date": str(r["Date received"])[:10],
                     "narrative": narrative, "inventory": inventory,
                     "amounts": [a.strip("$") for a in amounts][:3],
                     "letter": letter, "validator": v})
        print(f"{cid}: {inventory} | validator passed={v['passed']} (attempts={attempts})")

    # Negative demo for the dashboard's "gate in action" card
    bad_letter = demo[0]["letter"] + " We also reviewed [E9: Merchant response letter]."
    demo_bad = {"case_id": demo[0]["case_id"], "letter": bad_letter,
                "validator": validate(bad_letter, demo[0]["inventory"])}

    stats = {"pool_size": int(len(pool)), "model": MODEL, "retries": retries_total,
             "pct_with_evidence_mentions": None, "avg_items_when_present": None}
    json.dump({"cases": demo, "bad_case": demo_bad, "stats": stats},
              open("copilot_results.json", "w"), indent=1)
    print(f"\nSaved {len(demo)} LLM-drafted cases -> copilot_results.json")
    print("Now run: python build_demo.py  (rebuilds the dashboard with LLM output)")
