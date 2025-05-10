import os, pathlib, subprocess, time, openai

# -------------------------------------------------------------------
GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL         = "gpt-4o-mini"
TEMPERATURE   = 0.2
SLEEP_SEC     = 1              # stay under rate limits
# -------------------------------------------------------------------

openai.api_key = os.environ["OPENAI_API_KEY"]
GITHUB_SHA     = os.getenv("GITHUB_SHA")  # provided by GitHub Actions

def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def git_cmd(*args) -> str:
    """run git with quotePath disabled, return stdout as str"""
    return subprocess.check_output(
        ["git", "-c", "core.quotePath=false", *args], text=True, stderr=subprocess.DEVNULL
    )

def changed_md_files():
    """
    Return .md files in this commit.
    Works on depth-1 checkouts; falls back to every .md once.
    """
    try:
        out = git_cmd("diff-tree", "--no-commit-id", "--name-only", "-r", GITHUB_SHA)
        files = [p for p in out.splitlines() if p.endswith(".md")]
        if files:
            return files
    except subprocess.CalledProcessError:
        pass  # first run on shallow clone

    print("No diff available; processing all Markdown files.")
    out = git_cmd("ls-files", "*.md")
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
        model       = MODEL,
        messages    = [{"role": "user", "content": prompt}],
        temperature = TEMPERATURE,
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
