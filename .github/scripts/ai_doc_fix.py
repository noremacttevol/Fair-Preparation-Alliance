import os, glob, pathlib, openai

# --- config ---------------------------------------------------------------
GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL          = "gpt-4o-mini"
TEMPERATURE    = 0.2
# --------------------------------------------------------------------------

openai.api_key = os.environ["OPENAI_API_KEY"]

def load_glossary() -> str:
    with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
        return f.read()

def rewrite_file(md_path: str, glossary: str) -> None:
    # read file; skip if not UTF-8
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            original = f.read()
    except UnicodeDecodeError:
        print("skip ▶", md_path)
        return

    prompt = f"""You are the FPA style bot.
Glossary below shows approved terms. Enforce them exactly.
Keep Markdown structure; don’t touch code blocks.

--- BEGIN GLOSSARY ---
{glossary}
--- END GLOSSARY ---

--- BEGIN FILE ---
{original}
--- END FILE ---
"""

    resp = openai.chat.completions.create(
        model       = MODEL,
        messages    = [{"role": "user", "content": prompt}],
        temperature = TEMPERATURE,
        max_tokens  = 4000,
    )

    cleaned = resp.choices[0].message.content.strip()
    if cleaned != original:
        print("updated ▶", md_path)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(cleaned)

def main():
    glossary = load_glossary()
    for p in glob.glob("**/*.md", recursive=True):
        if pathlib.Path(p).as_posix() == GLOSSARY_PATH:
            continue
        rewrite_file(p, glossary)

if __name__ == "__main__":
    main()
