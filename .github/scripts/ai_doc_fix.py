import os, glob, pathlib, time, openai

GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL = "gpt-4o-mini"
TEMPERATURE = 0.2
DELAY_SEC = 1        # <- simple throttle

openai.api_key = os.environ["OPENAI_API_KEY"]

def load_glossary():
    with open(GLOSSARY_PATH, encoding="utf-8") as f:
        return f.read()

def rewrite_file(p, glossary):
    try:
        with open(p, encoding="utf-8") as f:
            original = f.read()
    except UnicodeDecodeError:
        print("skip ▶", p)
        return

    prompt = f"""You are the FPA style bot.
Glossary below lists approved terms. Enforce them exactly.

--- BEGIN GLOSSARY ---
{glossary}
--- END GLOSSARY ---

--- BEGIN FILE ---
{original}
--- END FILE ---
"""

    resp = openai.ChatCompletion.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
    )
    cleaned = resp.choices[0].message.content.strip()
    if cleaned != original:
        print("updated ▶", p)
        with open(p, "w", encoding="utf-8") as f:
            f.write(cleaned)

    time.sleep(DELAY_SEC)        # <- wait before next file

def main():
    gloss = load_glossary()
    for p in glob.glob("**/*.md", recursive=True):
        if pathlib.Path(p).as_posix() == GLOSSARY_PATH:
            continue
        rewrite_file(p, gloss)

if __name__ == "__main__":
    main()
