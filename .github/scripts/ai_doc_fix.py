import os, pathlib, subprocess, time, openai, tiktoken

# --- Config -------------------------------------------------------------------
GLOSSARY_PATH = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
MODEL        = "gpt-4o-mini"         # primary model for AI fixes (e.g., GPT-4 variant)
FALLBACK_MODEL = "gpt-3.5-turbo-16k" # fallback for large files if needed
TEMPERATURE  = 0.2
SLEEP_BASE   = 2    # base seconds for exponential backoff
MAX_RETRIES  = 3
# ------------------------------------------------------------------------------

openai.api_key = os.environ.get("OPENAI_API_KEY")
GITHUB_SHA = os.getenv("GITHUB_SHA", "")  # provided by GitHub Actions

# Utility: read file content with utf-8
def load_file(path):
    return pathlib.Path(path).read_text(encoding="utf-8")

# Utility: write file content with utf-8
def save_file(path, content):
    pathlib.Path(path).write_text(content, encoding="utf-8")

# Utility: count tokens using tiktoken (to decide on chunking)
def count_tokens(text, model=MODEL):
    try:
        enc = tiktoken.encoding_for_model(model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")  # default to a base encoding
    return len(enc.encode(text))

# Split a large text into chunks under a token limit
def chunk_text(text, max_tokens=6000, model=MODEL):
    """Split text into chunks with at most max_tokens tokens (approximate)."""
    paragraphs = text.split("\n\n")  # split by blank line for logical chunks
    chunks = []
    current_chunk = ""
    current_tokens = 0
    for para in paragraphs:
        para_tokens = count_tokens(para, model=model)
        # If adding this paragraph would exceed the limit, start a new chunk
        if current_chunk and current_tokens + para_tokens > max_tokens:
            chunks.append(current_chunk.strip())
            current_chunk = ""
            current_tokens = 0
        current_chunk += para + "\n\n"
        current_tokens += para_tokens
        # If paragraph itself is larger than max_tokens, force split it smaller
        if para_tokens > max_tokens:
            # naive split for extremely large paragraph (split in half)
            # (In practice, large paragraphs could be further split by sentence etc.)
            chunks.append(current_chunk.strip())
            current_chunk = ""
            current_tokens = 0
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

# Call OpenAI with retries and backoff
def call_openai(messages, model=MODEL, temperature=TEMPERATURE):
    for attempt in range(1, MAX_RETRIES+1):
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,
                request_timeout=60  # set a higher timeout (60s) for response
            )
            # Success: return the assistant's message content
            content = response['choices'][0]['message']['content']
            return content
        except openai.error.RateLimitError as e:
            wait = SLEEP_BASE * (2 ** (attempt-1))
            print(f"Rate limit hit. Retrying in {wait:.1f}s...")
            time.sleep(wait)
            continue
        except openai.error.Timeout as e:
            # If it's the last attempt, re-raise the error to be handled outside
            if attempt == MAX_RETRIES:
                raise
            print(f"Request timed out on attempt {attempt}. Will retry...")
            time.sleep(SLEEP_BASE * (2 ** (attempt-1)))
            continue
        except openai.error.APIError as e:
            # Handle other API errors similarly (could also include openai.error.APIConnectionError, etc.)
            if attempt == MAX_RETRIES:
                raise
            print(f"API error: {e}. Retrying in 2s...")
            time.sleep(2)
            continue
    # If we exit loop without return, raise a generic exception
    raise RuntimeError("OpenAI API call failed after retries")

# Process a single markdown file content with the AI model
def process_content(markdown_text):
    # Prepare system & user prompt with glossary context
    try:
        glossary = load_file(GLOSSARY_PATH)
    except Exception as e:
        glossary = ""
        print(f"Warning: Glossary file not found or unreadable: {e}")
    system_prompt = (
        "You are an expert documentation editor AI. "
        "You will receive a Markdown document and a glossary of terms. "
        "Improve the document for clarity, fix grammar/style, and enforce terminology from the glossary. "
        "Do NOT change the meaning, and preserve all Markdown formatting (links, headings, etc.)."
    )
    user_prompt = f"Glossary:\n{glossary}\n\nDocument:\n{markdown_text}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    # Call OpenAI to get the improved content
    return call_openai(messages, model=current_model, temperature=TEMPERATURE)

# Determine which files to process:
files_to_process = []
if GITHUB_SHA:
    # If we have a commit SHA, try diff with the previous commit
    try:
        result = subprocess.run(
            ["git", "diff", f"{GITHUB_SHA}~1", GITHUB_SHA, "--name-only", "--diff-filter=AM", "*.md"],
            check=True, text=True, capture_output=True
        )
        changed_files = [f.strip() for f in result.stdout.splitlines() if f.strip().endswith(".md")]
        files_to_process = changed_files if changed_files else []
    except subprocess.CalledProcessError as e:
        print("Diff failed or no previous commit – will process all Markdown files.")
        # Fallback to processing all .md files
        # (glob all .md in repo excluding .github directory to avoid editing workflow or similar)
        for path in pathlib.Path(".").rglob("*.md"):
            # skip files in .github or node_modules etc. if any
            if ".github" in str(path.parts):
                continue
            files_to_process.append(str(path))
else:
    # No SHA given (manual run), default to all Markdown files
    for path in pathlib.Path(".").rglob("*.md"):
        if ".github" in str(path.parts):
            continue
        files_to_process.append(str(path))

files_to_process = sorted(set(files_to_process))
print(f"Files to process: {files_to_process}")

# Iterate and fix files
for file_path in files_to_process:
    try:
        content = load_file(file_path)
    except Exception as e:
        print(f"Skipping {file_path}: cannot read file. ({e})")
        continue

    if not content.strip():
        print(f"Skipping {file_path}: file is empty.")
        continue

    # Decide model and chunking based on content size
    content_tokens = count_tokens(content, model=MODEL)
    current_model = MODEL
    if content_tokens > 10000:  # if >10k tokens (rough heuristic for extremely large file)
        print(f"File {file_path} is very large ({content_tokens} tokens). Will process in chunks.")
        # Optionally switch to fallback model if desired:
        # current_model = FALLBACK_MODEL  # (uncomment to use GPT-3.5 for large files)
        chunks = chunk_text(content, max_tokens=6000, model=current_model)
    else:
        chunks = [content]

    new_content = ""
    try:
        if len(chunks) > 1:
            # Process each chunk independently
            for idx, chunk in enumerate(chunks, start=1):
                print(f"Sending chunk {idx}/{len(chunks)} of {file_path} to OpenAI...")
                chunk_result = process_content(chunk)
                # Remove any extra leading/trailing whitespace/newlines to stitch cleanly
                new_content += chunk_result.strip() + "\n\n"
        else:
            # Just one chunk (no need to split)
            new_content = process_content(chunks[0])
    except openai.error.Timeout:
        print(f"Timeout processing {file_path} even after chunking. Skipping this file.")
        continue  # skip committing this file if it consistently times out
    except Exception as e:
        print(f"Error processing {file_path}: {e}. Skipping.")
        continue

    # Only save/overwrite if changes were made (to avoid noise commits)
    if new_content and new_content.strip() != content.strip():
        save_file(file_path, new_content)
        print(f"Updated {file_path}")
    else:
        print(f"No significant changes for {file_path}")
        
# After processing all files, commit changes if any
try:
    # Stage all modified .md files
    subprocess.run(["git", "add", "*.md"], check=True)
    # If there are no changes staged, git commit will fail
    commit_msg = "[AI fix] Update documentation via GPT"
    subprocess.run(["git", "commit", "-m", commit_msg], check=True)
    subprocess.run(["git", "push"], check=True)
    print("Changes committed and pushed.")
except subprocess.CalledProcessError as e:
    print(f"No changes to commit or git push failed: {e}")
