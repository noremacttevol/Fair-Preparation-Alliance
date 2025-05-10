import os, sys, glob, json, openai, textwrap, pathlib

# --- config ---
GLOSSARY_PATH = "FPA Mk1Mod3/13. Dictionary (w_ Q&A + Links).md"
MODEL = "gpt-4o-mini"               # cheap + good; change if you like
TEMPERATURE = 0.2                   # keep it deterministic
# --------------

openai.api_key = os.environ["OPENAI_API_KEY"]

def load_glossary():
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        return f.read()

def rewrite_file(md_path, glossary):
    with open(md_path, "r", encoding="utf-8") as f:
        original = f.read()

    prompt = f"""
You are the FPA style bot.
Glossary below delimits the approved terms. Enforce them exactly (case-insensitive).
Keep Markdown structure. Do not change code blocks.
If wording is already correct, return the input unchanged.

--- BEGIN GLOSSARY ---
{glossary}
--- END GLOSSARY ---

--- BEGIN FILE ---
{original}
--- END FILE ---
"""

    resp = openai.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
        max_tokens=4000,
    )

    cleaned = resp.choices[0].message.content.strip()
    if cleaned != original:
        print(f"updated ▶ {md_path}")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(cleaned)

def main():
    glossary = load_glossary()
    paths = glob.glob("**/*.md", recursive=True)
    for p in paths:
        # skip the glossary itself
        if pathlib.Path(p).as_posix() == GLOSSARY_PATH:
            continue
        rewrite_file(p, glossary)

if __name__ == "__main__":
    main()
