import os, pathlib, subprocess, time, openai

GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL = "gpt-4o-mini"
TEMPERATURE = 0.2
SLEEP_SEC = 1      # light throttle

openai.api_key = os.environ["OPENAI_API_KEY"]
GITHUB_SHA = os.getenv("GITHUB_SHA")  # provided by Actions

def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def changed_md_files():
    """
    Return .md files changed in this commit.
    Falls back to every .md file on shallow clone failure.
    """
    try:
        out = subprocess.check_output(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", GITHUB_SHA],
            text=True,
        )
        paths = [f for f in out.splitlines() if f.endswith(".md")]
        if paths:
            return paths
    except subprocess.CalledProcessError:
        pass  # depth‑1 issue—fallback below

    # fallback ‑ first run or no diff: grab everything
    print("No diff available; processing all Markdown files.")
    out = subprocess.check_output(["git", "ls-files", "*.md"], text=True)
    return out.splitlines()

def rewrite(path, glossary):
    try:
        src = load(path)
    except UnicodeDecodeError:
        print("skip ▶", path)
        return
    prompt = f"""You are the FPA style bot.
Glossary below lists approved terms. Enforce them exactly.

--- BEGIN GLOSSARY ---
{glossary}
--- END GLOSSARY ---

--- BEGIN FILE ---
{src}
--- END FILE ---
"""
    rsp = openai.ChatCompletion.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=TEMPERATURE,
    )
    out = rsp.choices[0].message.content.strip()
    if out != src:
        print("updated ▶", path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(out)
    time.sleep(SLEEP_SEC)

def main():
    glossary = load(GLOSSARY_PATH)
    for md in changed_md_files():
        if pathlib.Path(md).as_posix() == GLOSSARY_PATH:
            continue
        rewrite(md, glossary)

if __name__ == "__main__":
    main()
