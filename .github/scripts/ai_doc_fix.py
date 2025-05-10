import os, pathlib, openai, subprocess

GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL = "gpt-4o-mini"
TEMPERATURE = 0.2

openai.api_key = os.environ["OPENAI_API_KEY"]

def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def git_changed_md():
    """return list of .md files in the current commit"""
    base = subprocess.check_output(
        ["git", "rev-parse", "HEAD^"], text=True
    ).strip()
    files = subprocess.check_output(
        ["git", "diff", "--name-only", base, "HEAD"], text=True
    ).splitlines()
    return [f for f in files if f.endswith(".md")]

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

def main():
    glossary = load(GLOSSARY_PATH)
    for md in git_changed_md():
        if pathlib.Path(md).as_posix() == GLOSSARY_PATH:
            continue
        rewrite(md, glossary)

if __name__ == "__main__":
    main()
