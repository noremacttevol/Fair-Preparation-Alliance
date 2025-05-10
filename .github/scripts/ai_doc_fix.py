import os, pathlib, subprocess, time, openai, tiktoken

# --- Config -------------------------------------------------------------------
GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL          = "gpt-4o-mini"
FALLBACK_MODEL = "gpt-3.5-turbo-16k"   # optional fallback
TEMPERATURE    = 0.2
MAX_RETRIES    = 3
SLEEP_BASE     = 2          # base for exponential back-off
CHUNK_TOKENS   = 6000       # max tokens per chunk
LARGE_FILE_TOK = 10000      # treat files above this as “large”
# ------------------------------------------------------------------------------

openai.api_key               = os.getenv("OPENAI_API_KEY")
openai.api_request_timeout   = 60
GITHUB_SHA                   = os.getenv("GITHUB_SHA", "")

# ---------- helpers -----------------------------------------------------------
def load(path):  return pathlib.Path(path).read_text(encoding="utf-8")
def save(path, txt): pathlib.Path(path).write_text(txt, encoding="utf-8")

def token_len(txt, model=MODEL):
    try: enc = tiktoken.encoding_for_model(model)
    except Exception: enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(txt))

def chunk(text, max_tok=CHUNK_TOK):
    paras, out, cur, tok = text.split("\n\n"), [], "", 0
    for p in paras:
        ptok = token_len(p)
        if cur and tok + ptok > max_tok:
            out.append(cur.strip()); cur, tok = "", 0
        cur += p + "\n\n"; tok += ptok
    if cur: out.append(cur.strip())
    return out

def git_md_files():
    try:
        diff = subprocess.check_output(
            ["git","-c","core.quotePath=false",
             "diff-tree","--no-commit-id","--name-only","-r",GITHUB_SHA],
            text=True).splitlines()
        files = [f for f in diff if f.endswith(".md")]
        if files: return files
    except subprocess.CalledProcessError:
        pass
    print("No diff; processing all .md files.")
    return subprocess.check_output(
        ["git","-c","core.quotePath=false","ls-files","*.md"],
        text=True).splitlines()

def call_openai(msgs, model):
    for n in range(1, MAX_RETRIES+1):
        try:
            r = openai.ChatCompletion.create(model=model, messages=msgs,
                                             temperature=TEMPERATURE)
            return r.choices[0].message.content.strip()
        except (openai.error.RateLimitError,
                openai.error.Timeout,
                openai.error.APIError) as e:
            if n == MAX_RETRIES: raise
            wait = SLEEP_BASE * 2**(n-1)
            print(f"{e.__class__.__name__} ▶ retry {n}/{MAX_RETRIES} in {wait}s")
            time.sleep(wait)

# ---------- main --------------------------------------------------------------
glossary = load(GLOSSARY_PATH)
system = ("You are an expert docs editor. Use the glossary to enforce terminology, "
          "keep markdown structure, fix grammar, and preserve meaning.")

for md in git_md_files():
    if pathlib.Path(md).as_posix() == GLOSSARY_PATH: continue
    try: src = load(md)
    except Exception as e: print(f"skip ▶ {md}: {e}"); continue
    if not src.strip(): continue

    model = MODEL
    pieces = [src]
    if token_len(src) > LARGE_FILE_TOK:
        print(f"{md} is large; chunking")
        pieces = chunk(src)
    new = ""
    for i, piece in enumerate(pieces, 1):
        msgs = [
            {"role":"system","content":system},
            {"role":"user","content":f"Glossary:\n{glossary}\n\nDocument:\n{piece}"}
        ]
        try:
            out = call_openai(msgs, model)
        except openai.error.Timeout:
            # fallback to smaller model once
            if model != FALLBACK_MODEL:
                model = FALLBACK_MODEL
                out = call_openai(msgs, model)
            else:
                print(f"timeout ▶ skip chunk {i} of {md}")
                out = piece
        new += out.strip()+"\n\n"
        time.sleep(1)

    if new.strip() != src.strip():
        save(md, new); print(f"updated ▶ {md}")

# commit if anything changed
subprocess.run(["git","add","*.md"])
if subprocess.run(["git","diff","--cached","--quiet"]).returncode != 0:
    subprocess.run(["git","config","user.name","github-actions"])
    subprocess.run(["git","config","user.email","github-actions@github.com"])
    subprocess.run(["git","commit","-m","[AI fix] Update docs via GPT"])
    subprocess.run(["git","push"])
else:
    print("No changes to commit.")
