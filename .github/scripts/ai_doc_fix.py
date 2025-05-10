import os
import sys
import subprocess
import openai
import tiktoken

# Configuration
MODEL = "gpt-4o-mini"
GLOSSARY_FILE = "1.3 Full/13. Dictionary (w_ Q&A + Links).md"
COMMIT_MESSAGE = "[AI fix] Update docs via GPT"

def get_changed_files():
    """Get list of changed files in last commit (only .md). Fallback to all .md if diff fails."""
    try:
        result = subprocess.run(["git", "diff", "HEAD~1", "--name-only"], check=True, capture_output=True, text=True)
        files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        # If git diff fails (e.g., initial commit), include all .md files
        files = []
        for root, dirs, fs in os.walk("."):
            if root.startswith("./.git") or "/.git/" in root:
                continue
            for fname in fs:
                if fname.lower().endswith(".md"):
                    rel_path = os.path.join(root, fname)
                    rel_path = rel_path.lstrip("./")  # normalize to relative path
                    files.append(rel_path)
    md_files = [f for f in files if f.lower().endswith(".md")]
    return md_files

def process_file(filepath, glossary_text):
    """Run GPT-4o-mini to improve a Markdown file's style/terminology. Returns True if file was modified."""
    # Skip the glossary file itself
    if os.path.normpath(filepath) == os.path.normpath(GLOSSARY_FILE) or os.path.basename(filepath) == os.path.basename(GLOSSARY_FILE):
        print(f"Skipping glossary file: {filepath}")
        return False
    # Read file content (skip if not UTF-8 decodable)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"Failed to read {filepath}: {e}")
        return False
    original_text = text
    # Initialize tokenizer for the model
    try:
        enc = tiktoken.encoding_for_model(MODEL)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    # Tokenize content and glossary
    doc_tokens = enc.encode(text)
    glossary_tokens = enc.encode(glossary_text) if glossary_text else []
    # Determine chunk size for document content (to handle large files)
    max_chunk_tokens = 2500  # max tokens per document chunk
    if len(doc_tokens) <= max_chunk_tokens:
        doc_chunks = [text]
    else:
        # Split text by blank lines to keep paragraphs intact
        paragraphs = text.split("\n\n")
        doc_chunks = []
        current_chunk = ""
        current_tokens = 0
        for para in paragraphs:
            para_text = para.strip()
            # Encode paragraph (preserve paragraph break)
            if para_text == "":
                para_tokens = enc.encode("\n\n")
            else:
                para_tokens = enc.encode(para_text + "\n\n")
            # If adding this paragraph exceeds chunk limit, start a new chunk
            if current_chunk and current_tokens + len(para_tokens) > max_chunk_tokens:
                doc_chunks.append(current_chunk)
                current_chunk = ""
                current_tokens = 0
            # If paragraph itself is larger than chunk limit, split it further
            if len(para_tokens) > max_chunk_tokens:
                for i in range(0, len(para_tokens), max_chunk_tokens):
                    part_tokens = para_tokens[i:i+max_chunk_tokens]
                    part_text = enc.decode(part_tokens)
                    doc_chunks.append(part_text)
                current_chunk = ""
                current_tokens = 0
            else:
                # Add paragraph to current chunk
                part_text = enc.decode(para_tokens)
                current_chunk += part_text
                current_tokens += len(para_tokens)
        if current_chunk:
            doc_chunks.append(current_chunk)
    # Process each chunk with OpenAI API
    new_content_parts = []
    for chunk in doc_chunks:
        system_prompt = (
            "You are an expert documentation editor. "
            "Improve the following documentation for clarity, style, and terminology. "
            "Use the provided glossary to ensure consistent terminology. "
            "Preserve all Markdown formatting and content structure."
        )
        user_prompt = f"Glossary:\n{glossary_text}\n\nDocumentation:\n{chunk}\n\nPlease rewrite the documentation content accordingly."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        # Call OpenAI API with retry logic for robustness
        response_text = None
        for attempt in range(3):
            try:
                response = openai.ChatCompletion.create(model=MODEL, messages=messages, temperature=0)
                response_text = response["choices"][0]["message"]["content"]
                break  # success
            except Exception as e:
                print(f"OpenAI API call failed for chunk of {filepath} (attempt {attempt+1}): {e}", file=sys.stderr)
                if attempt < 2:
                    import time
                    time.sleep(5)  # wait before retry
        if response_text is None:
            # All attempts failed for this chunk
            print(f"Skipping file {filepath} due to repeated API failures.", file=sys.stderr)
            return False
        new_content_parts.append(response_text)
    # Combine all chunk responses
    new_content = "".join(new_content_parts)
    if new_content.strip() == original_text.strip():
        # No meaningful change
        print(f"No changes made to {filepath}")
        return False
    # Write the updated content back to the file
    try:
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            f.write(new_content)
    except Exception as e:
        print(f"Failed to write changes to {filepath}: {e}", file=sys.stderr)
        return False
    print(f"File updated: {filepath}")
    return True

def main():
    changed_files = get_changed_files()
    if not changed_files:
        print("No Markdown files to process. Exiting.")
        return
    # Load glossary content if available
    glossary_text = ""
    try:
        with open(GLOSSARY_FILE, "r", encoding="utf-8") as gf:
            glossary_text = gf.read()
    except Exception as e:
        glossary_text = ""
        print("Glossary file not found or not readable, proceeding without glossary.")
    any_changes = False
    for file in changed_files:
        if file.lower().endswith(".md"):
            if process_file(file, glossary_text):
                any_changes = True
    # Commit and push changes if any were made
    if any_changes:
        try:
            subprocess.run(["git", "config", "--local", "user.name", "github-actions[bot]"], check=True)
            subprocess.run(["git", "config", "--local", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        except Exception as e:
            print(f"Git config warning: {e}", file=sys.stderr)
        try:
            subprocess.run(["git", "add", "-A"], check=True)
            subprocess.run(["git", "commit", "-m", COMMIT_MESSAGE], check=True)
        except subprocess.CalledProcessError:
            # Nothing to commit (no changes)
            print("No changes to commit after processing.")
            return
        try:
            subprocess.run(["git", "push"], check=True)
        except Exception as e:
            print(f"Git push failed: {e}", file=sys.stderr)
    else:
        print("No documentation changes to commit.")

if __name__ == "__main__":
    main()
