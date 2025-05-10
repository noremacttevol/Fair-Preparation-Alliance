import os, pathlib, subprocess, time, openai, textwrap, tiktoken

# ── CONFIG ────────────────────────────────────────────────────────────────
GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL         = "gpt-4o-mini"
TOKEN_LIMIT   = 12000           # chunk if file exceeds this
TEMP          = 0.2
SLEEP_SEC     = 1
MAX_RETRIES   = 3
openai.api_key             = os.environ["OPENAI_API_KEY"]
openai.api_request_timeout = 120
ENC = tiktoken.encoding_for_model("gpt-4o-mini")
GITHUB_SHA = os.getenv("GITHUB_SHA")
# ──────────────────────────────────────────────────────────────────────────

def load(path):
    with open(path, encoding="utf-8") as f: return f.read()

# ── git helpers (quotePath-safe) ──────────────────────────────────────────
def git(*args):
    return subprocess.check_output(
        ["git","-c","core.quotePath=false",*args], text=True, stderr=subprocess.DEVNULL
    )

def md_in_commit():
    try:
        out = git("diff-tree","--no-commit-id","--name-only","-r",GITHUB_SHA)
        lst = [p for p in out.splitlines() if p.endswith(".md")]
        if lst: return lst
    except subprocess.CalledProcessError: pass
    print("No diff -> processing all Markdown once")
    return git("ls-files","*.md").splitlines()
# ──────────────────────────────────────────────────────────────────────────

def token_len(txt:str)->int: return len(ENC.encode(txt))

def split_md(text:str)->list[str]:
    """split at headings or every 1k lines"""
    blocks, buf = [], []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("#") and buf:
            blocks.append("".join(buf)); buf=[]
        buf.append(line)
        if len(buf)>1000: blocks.append("".join(buf)); buf=[]
    if buf: blocks.append("".join(buf))
    return blocks

def gpt(prompt:str)->str:
    for attempt in range(1, MAX_RETRIES+1):
        try:
            rsp = openai.ChatCompletion.create(
                model=MODEL,
                messages=[{"role":"user","content":prompt}],
                temperature=TEMP,
            )
            return rsp.choices[0].message.content.strip()
        except (openai.error.Timeout, openai.error.RateLimitError):
            wait=SLEEP_SEC*(2**(attempt-1))
            print(f"timeout ▶ retry {attempt}/{MAX_RETRIES} in {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError("Max retries exceeded")

def rewrite(path, glossary):
    try: src = load(path)
    except UnicodeDecodeError: print("skip ▶",path); return
    chunks = [src] if token_len(src)<=TOKEN_LIMIT else split_md(src)
    outs=[]
    for idx,chunk in enumerate(chunks,1):
        prompt = textwrap.dedent(f"""\
            You are the FPA style bot.
            Glossary below lists approved terms. Enforce them exactly.

            --- BEGIN GLOSSARY ---
            {glossary}
            --- END GLOSSARY ---

            --- BEGIN FILE (part {idx}/{len(chunks)}) ---
            {chunk}
            --- END FILE ---
        """)
        try:
            outs.append(gpt(prompt))
            time.sleep(SLEEP_SEC)
        except RuntimeError:
            print(f"skip ▶ {path} (timeout)"); return
    cleaned="".join(outs)
    if cleaned!=src:
        print("updated ▶",path)
        with open(path,"w",encoding="utf-8") as f: f.write(cleaned)

def main():
    glossary = load(GLOSSARY_PATH)
    for md in md_in_commit():
        if pathlib.Path(md).as_posix()==GLOSSARY_PATH: continue
        rewrite(md, glossary)

if __name__=="__main__": main()
