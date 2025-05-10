import os, pathlib, subprocess, time, openai, math, random

# ── CONFIG ──────────────────────────────────────────────────────────────────
GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL         = "gpt-4o-mini"
TEMP          = 0.2
SLEEP_SEC     = 1          # base pause → ≈60 req/min  ≪ 200 k TPM
MAX_RETRIES   = 3
openai.api_key               = os.environ["OPENAI_API_KEY"]
openai.api_request_timeout   = 120       # client‑side cut‑off

GITHUB_SHA = os.getenv("GITHUB_SHA")     # set by actions/checkout
# ────────────────────────────────────────────────────────────────────────────

def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def git_list_md():
    """Return changed .md files; fallback to all .md once on shallow clone."""
    try:
        out = subprocess.check_output(
            ["git","-c","core.quotePath=false",
             "diff-tree","--no-commit-id","--name-only","-r",GITHUB_SHA],
            text=True)
        files = [p for p in out.splitlines() if p.endswith(".md")]
        if files:
            return files
    except subprocess.CalledProcessError:
        pass
    print("No diff available; processing all Markdown files.")
    out = subprocess.check_output(
        ["git","-c","core.quotePath=false","ls-files","*.md"], text=True)
    return out.splitlines()

def chat_fix(src, glossary):
    prompt = f"""You are the FPA style bot.
Glossary below lists approved terms. Enforce them exactly.

--- BEGIN GLOSSARY ---
{glossary}
--- END GLOSSARY ---

--- BEGIN FILE ---
{src}
--- END FILE ---
"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            rsp = openai.ChatCompletion.create(
                model=MODEL,
                messages=[{"role":"user","content":prompt}],
                temperature=TEMP,
            )
            return rsp.choices[0].message.content.strip()
        except openai.error.RateLimitError as e:
            wait = SLEEP_SEC * (2 ** (attempt-1))
            print(f"rate‑limit ▶ retry {attempt}/{MAX_RETRIES} in {wait:.1f}s")
            time.sleep(wait)
        except openai.error.Timeout:
            wait = SLEEP_SEC * (2 ** (attempt-1))
            print(f"timeout ▶ retry {attempt}/{MAX_RETRIES} in {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError("Max retries exceeded")

def main():
    glossary = load(GLOSSARY_PATH)
    for md in git_list_md():
        if pathlib.Path(md).as_posix() == GLOSSARY_PATH:
            continue
        try:
            src = load(md)
        except UnicodeDecodeError:
            print("skip ▶", md); continue
        cleaned = chat_fix(src, glossary)
        if cleaned != src:
            print("updated ▶", md)
            with open(md,"w",encoding="utf-8") as f: f.write(cleaned)
        time.sleep(SLEEP_SEC)  # steady‑state throttle

if __name__ == "__main__":
    main()
