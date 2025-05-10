import os, time, glob, pathlib, openai, subprocess

GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL = "gpt-4o-mini"
TEMPERATURE = 0.2
SLEEP_SEC = 2  # wait after every call to stay under 200k TPM

openai.api_key = os.environ["OPENAI_API_KEY"]

def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def rewrite(p, glossary):
    try:
        src = load(p)
    except UnicodeDecodeError:
        print("skip ▶", p)
        return
    prompt = f"""You are FPA style bot…
--- BEGIN GLOSSARY ---
{glossary}
--- END GLOSSARY ---
--- BEGIN FILE ---
{src}
--- END FILE ---
"""
    rsp = openai.ChatCompletion.create(
        model=MODEL, messages=[{"role":"user","content":prompt}], temperature=TEMPERATURE
    )
    out = rsp.choices[0].message.content.strip()
    if out != src:
        print("updated ▶", p)
        with open(p, "w", encoding="utf-8") as f:
            f.write(out)
    time.sleep(SLEEP_SEC)

def main():
    glossary = load(GLOSSARY_PATH)
    for md in glob.glob("**/*.md", recursive=True):
        if pathlib.Path(md).as_posix() == GLOSSARY_PATH:
            continue
        rewrite(md, glossary)

if __name__ == "__main__":
    main()
