#!/usr/bin/env python3
"""
term_audit.py  ·  Adds / maps / drops WikiLink terms that aren’t yet
in 00_Core/13. Dictionary (Q&A + Links).md

• KEEP  → appends with 1-line definition
• MAP   → rewires links to canonical term
• DROP  → leaves as-is; ai_doc_fix.py will flag later
"""

import os, re, json, subprocess, pathlib, collections, sys
 HEAD
 HEAD
import openai

ROOT   = pathlib.Path(__file__).resolve().parents[2]   # repo root
DICT   = ROOT / "00_Core" / "13. Dictionary (Q&A + Links).md"
OPENAI = os.getenv("OPENAI_API_KEY")

# ---------- helpers -------------------------------------------------
def shell(cmd):
    subprocess.run(cmd, shell=True, check=True)

def load_dictionary():
    known = {}
    if not DICT.exists():
        return known
    for ln in DICT.read_text(encoding="utf8").splitlines():
        if "—" in ln:
            term = ln.split("—")[0].strip()
            known[term] = ln
    return known

def extract_unknown_terms(known):
    wiki_rx = re.compile(r"\[\[([^\]]+?)\]\]")
    hits = collections.Counter()
    for md in ROOT.rglob("*.md"):
        if "99_Archive" in md.parts or md == DICT:
            continue
        for t in wiki_rx.findall(md.read_text(errors="ignore")):
            t = t.strip()
            if t and t not in known:
                hits[t] += 1
    return hits

# ---------- main ----------------------------------------------------
def main():
    # Example of using the new API
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how can I fix this issue?"}
        ]
    )
    print(response['choices'][0]['message']['content'])

a3bdbb3b49c522f3786f21b881a21bec4a7d78c2
ROOT   = pathlib.Path(__file__).resolve().parents[2]   # repo root
DICT   = ROOT / "00_Core" / "13. Dictionary (Q&A + Links).md"
OPENAI = os.getenv("OPENAI_API_KEY")

# ---------- helpers -------------------------------------------------
def shell(cmd):
    subprocess.run(cmd, shell=True, check=True)

def load_dictionary():
    known = {}
    if not DICT.exists():
        return known
    for ln in DICT.read_text(encoding="utf8").splitlines():
        if "—" in ln:
            term = ln.split("—")[0].strip()
            known[term] = ln
    return known

def extract_unknown_terms(known):
    wiki_rx = re.compile(r"\[\[([^\]]+?)\]\]")
    hits = collections.Counter()
    for md in ROOT.rglob("*.md"):
        if "99_Archive" in md.parts or md == DICT:
            continue
        for t in wiki_rx.findall(md.read_text(errors="ignore")):
            t = t.strip()
            if t and t not in known:
                hits[t] += 1
    return hits

# ---------- main ----------------------------------------------------
def main():
    known   = load_dictionary()
    unknown = extract_unknown_terms(known)
    if not unknown:
        print("✓ No new WikiLink terms — term audit skipped")
        return

    # Build prompt for GPT
    prompt = (
        "For each TERM decide: KEEP | MAP | DROP.\n"
        "If KEEP → return a one-line definition.\n"
        "If MAP  → specify canonical TERM from list below.\n"
        "Respond as JSON list of objects:\n"
        '[{"term":"...","action":"KEEP","definition":"..."}, ...]\n\n'
        f"KNOWN TERMS: {', '.join(known)[:4000]}\n\n"
        f"TERMS TO CLASSIFY: {', '.join(unknown)}"
    )

    import openai
    openai.api_key = OPENAI
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":prompt}],
        temperature=0
    ).choices[0].message.content.strip()

    try:
        decisions = json.loads(resp)
    except json.JSONDecodeError:
        print("✗ GPT response not valid JSON")
        sys.exit(1)

    # Patch dictionary / notes
    edits = False
    with DICT.open("a", encoding="utf8") as d:
        for row in decisions:
            t, act = row["term"], row["action"].upper()
            if act == "KEEP":
                d.write(f"{t} — {row.get('definition','TBD')}  |  avoid: n/a\n")
                edits = True
            elif act == "MAP":
                canon = row.get("canonical") or row.get("definition")  # fallback
                for md in ROOT.rglob("*.md"):
                    if "99_Archive" in md.parts or md == DICT:
                        continue
                    text = md.read_text(encoding="utf8")
                    new  = text.replace(f"[[{t}]]", f"[[{canon}]]")
                    if new != text:
                        md.write_text(new, encoding="utf8")
                        edits = True
            # DROP = do nothing

    if edits:
        # Commit the changes made by this script
        shell('git config user.name  "vault-bot"')
        shell('git config user.email "actions@github"')
        shell('git add .')
        shell('git commit -m "[AI fix] term audit"')
    else:
        print("✓ Term audit found nothing to change")
 HEAD
 2dfe4d7fd85a387b60d4f509c05f0ba1efc17d3f

a3bdbb3b49c522f3786f21b881a21bec4a7d78c2

if __name__ == "__main__":
    main()
