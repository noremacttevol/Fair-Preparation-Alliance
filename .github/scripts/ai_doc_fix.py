import os, pathlib, subprocess, time, textwrap, openai, tiktoken

# ── CONFIG ────────────────────────────────────────────────────────────────
GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL         = "gpt-4o-mini"
TEMP          = 0.2
TOKEN_LIMIT   = 12000          # chunk if file exceeds this many tokens
SLEEP_SEC     = 1              # global throttle
MAX_RETRIES   = 3
openai.api_key             = os.environ["OPENAI_API_KEY"]
openai.api_request_timeout = 120        # seconds
ENC = tiktoken.encoding_for_model("gpt-4o-mini")
GITHUB_SHA = os.getenv("GITHUB_SHA")    # set by GitHub Actions
# ──────────────────────────────────────────────────────────────────────────

# ---------- helpers -------------------------------------------------------
def git(*args) -> str:
    return subprocess.check_output(
        ["git", "-c", "core.quotePath=false", *args],
        text=True, stderr=subprocess.DEVNULL
    )

def md_in_commit():
    """Markdown files in this commit; fallback to all .md on first run."""
    try:
        out = git("diff-tree", "--no-commit-id", "--name-only", "-r", GITHUB_SHA)
        lst = [p for p in out.splitlines() if p.endswith(".md")]
        if lst:
            return lst
    except subprocess.CalledProcessError:
        pass
    print("No diff available; processing all Markdown files.")
    return git("ls-files", "*.md").splitlines()

def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def token_len(txt: str) -> int:
    return len(ENC.encode(txt))

def hard_split_md(txt: str) -> list[str]:
    blocks, buf = [], []
    for ln in txt.splitlines(keepends=True):
        if ln.lstrip().startswith("#") and buf:
            blocks.append("".join(buf)); buf = []
        buf.append(ln)
        if len(buf) > 1000: blocks.append("".join(buf)); buf = []
    if buf: blocks.append("".join(buf))
    return blocks

def gpt(prompt: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            rsp = openai.ChatCompletion.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=TEMP,
            )
            return rsp.choices[0].message.content.strip()
        except (openai.error.Timeout, openai.error.RateLimitError):
            wait = SLEEP_SEC * (2 ** (attempt - 1))
            print(f"timeout ▶ retry {attempt}/{MAX_RETRIES} in {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError("Max retries exceeded")

# ---------- main work -----------------------------------------------------
def rewrite(path, glossary):
    try:
        src = load(path)
    except UnicodeDecodeError:
        print("skip ▶", path)
        return

    parts = [src] if token_len(src) <= TOKEN_LIMIT else hard_split_md(src)
    cleaned_parts = []

    for idx, chunk in enumerate(parts, 1):
        prompt = textwrap.dedent(f"""\
            You are the FPA style bot.
            Glossary below lists approved terms. Enforce them exactly.

            --- BEGIN GLOSSARY ---
            {glossary}
            --- END GLOSSARY ---

            --- BEGIN FILE (part {idx}/{len(parts)}) ---
            {chunk}
            --- END FILE ---
        """)
        try:
            cleaned_parts.append(gpt(prompt))
            time.sleep(SLEEP_SEC)
        except RuntimeError:
            print(f"skip ▶ {path} (timeout)")
            return

    cleaned = "".join(cleaned_parts)
    if cleaned != src:
        print("updated ▶", path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(cleaned)

def main():
    glossary = load(GLOSSARY_PATH)
    for md in md_in_commit():
        if pathlib.Path(md).as_posix() == GLOSSARY_PATH:
            continue
        rewrite(md, glossary)

if __name__ == "__main__":
    main()
