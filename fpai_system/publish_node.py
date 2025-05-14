import os
import sys
import json
import datetime
import shutil
import re
from pathlib import Path
from fpai_system.core.term_registry import TermRegistry
from datetime import datetime, timezone

SOURCE_DIRS = ["doctrine", "zettel", "approved"]
DEST_DIR = "published"
CHANGELOG_PATH = Path("logs/publish_changelog.jsonl")

def has_front_matter(content):
    """Check if content starts with a YAML front-matter block."""
    return bool(re.match(r'^---\s*\n', content))

def extract_first_h1(content):
    """Extract the first H1 header from markdown content."""
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None

def inject_front_matter(content, title):
    """Inject minimal MkDocs front-matter with title."""
    front_matter = f"---\ntitle: {title}\n---\n\n"
    return front_matter + content

def relative_path_from_root(path):
    """Get path relative to repo root (current working directory)."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        # If path is not under cwd, return absolute path as fallback
        return str(path.resolve())

def process_file(src_path, term_registry):
    """Process a single markdown file: validate, inject front-matter, copy, and log."""
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file {src_path}: {e}", file=sys.stderr)
        return None

    valid, invalid_terms = term_registry.validate_content(content)

    # Determine title for front-matter injection if needed
    if not has_front_matter(content):
        title = extract_first_h1(content)
        if not title:
            title = src_path.stem
        content = inject_front_matter(content, title)

    # Destination path preserving subfolder structure
    # Find which source directory this file is under by checking absolute paths
    src_path = Path(src_path).resolve()
    for source_dir in SOURCE_DIRS:
        source_dir_path = Path(source_dir).resolve()
        try:
            # Try to get relative path from source directory
            relative_subpath = src_path.relative_to(source_dir_path)
            dest_path = Path(DEST_DIR) / Path(source_dir).name / relative_subpath
            break
        except ValueError:
            # If that fails, try to match just the directory name
            if str(source_dir) in str(src_path):
                parts = str(src_path).split(str(source_dir))
                if len(parts) > 1:
                    relative_subpath = Path(parts[1].lstrip("/\\"))
                    dest_path = Path(DEST_DIR) / source_dir / relative_subpath
                    break
    else:
        print(f"Error: {src_path} not under any source directory", file=sys.stderr)
        return None

    # Ensure destination directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    if valid:
        try:
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"Error writing file {dest_path}: {e}", file=sys.stderr)
            return None

        log_entry = {
            "timestamp": timestamp,
            "source": relative_path_from_root(src_path),
            "dest": relative_path_from_root(dest_path),
            "status": "copied",
            "invalid_terms": []
        }
    else:
        log_entry = {
            "timestamp": timestamp,
            "source": relative_path_from_root(src_path),
            "dest": None,
            "status": "skipped_invalid_terms",
            "invalid_terms": invalid_terms
        }

    return log_entry, valid

def main():
    term_registry = TermRegistry(Path.cwd())
    invalid_files_found = False
    changelog_entries = []

    # Create destination directory
    Path(DEST_DIR).mkdir(parents=True, exist_ok=True)

    for source_dir in SOURCE_DIRS:
        source_path = Path(source_dir)
        if not source_path.exists():
            print(f"Source directory {source_dir} does not exist, skipping.", file=sys.stderr)
            continue

        for root, _, files in os.walk(source_path):
            for file in files:
                if file.endswith(".md"):
                    src_file_path = Path(root) / file
                    # Convert to absolute path for proper relative path calculation
                    abs_src_path = src_file_path.resolve()
                    result = process_file(abs_src_path, term_registry)
                    if result is None:
                        # IO error, treat as failure
                        invalid_files_found = True
                        continue
                    log_entry, valid = result
                    changelog_entries.append(log_entry)
                    if not valid:
                        invalid_files_found = True

    # Write changelog entries
    try:
        CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CHANGELOG_PATH, "w", encoding="utf-8") as log_file:
            for entry in changelog_entries:
                json.dump(entry, log_file)
                log_file.write("\n")
    except Exception as e:
        print(f"Error writing changelog file {CHANGELOG_PATH}: {e}", file=sys.stderr)
        sys.exit(2)

    sys.exit(1 if invalid_files_found else 0)

if __name__ == "__main__":
    main()
