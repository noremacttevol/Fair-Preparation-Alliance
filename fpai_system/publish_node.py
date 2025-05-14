import os, sys, json, re, shutil
from pathlib import Path
from datetime import datetime, timezone

from fpai_system.core.term_registry import TermRegistry

SOURCE_DIRS   = ["doctrine", "zettel", "approved"]
DEST_DIR      = "published"
CHANGELOG_PATH = Path("logs/publish_changelog.jsonl")

# ───────── helpers ─────────
def has_front_matter(content): return bool(re.match(r'^---\s*\n', content))

def extract_first_h1(content):
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None

def inject_front_matter(content, title):
    return f"---\ntitle: {title}\n---\n\n{content}"

def relative_path_from_root(p):  # Path → str
    try:    return str(p.relative_to(Path.cwd()))
    except ValueError: return str(p.resolve())

# ───── per-file processing ─────
def process_file(src_path: Path, term_registry: TermRegistry):
    try:
        content = src_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {src_path}: {e}", file=sys.stderr)
        return None

    is_valid, invalid = term_registry.validate_content(content)

    if not has_front_matter(content):
        title   = extract_first_h1(content) or src_path.stem
        content = inject_front_matter(content, title)

    # map source→dest
    for source_dir in SOURCE_DIRS:
        try:
            rel_sub = src_path.resolve().relative_to(Path(source_dir).resolve())
            dest    = Path(DEST_DIR) / source_dir / rel_sub
            break
        except ValueError:
            continue
    else:
        print(f"{src_path} not under SOURCE_DIRS", file=sys.stderr)
        return None

    dest.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    if is_valid:
        dest.write_text(content, encoding="utf-8")
        log = {"timestamp": ts, "source": relative_path_from_root(src_path),
               "dest": relative_path_from_root(dest), "status": "copied",
               "invalid_terms": []}
    else:
        log = {"timestamp": ts, "source": relative_path_from_root(src_path),
               "dest": None, "status": "skipped_invalid_terms",
               "invalid_terms": invalid}
    return log, is_valid

# ───────── main CLI ─────────
def main():
    term_registry = TermRegistry(Path.cwd())
    invalid_found = False
    logs = []

    Path(DEST_DIR).mkdir(parents=True, exist_ok=True)

    for sd in SOURCE_DIRS:
        for root, _, files in os.walk(sd):
            for f in files:
                if f.endswith(".md"):
                    res = process_file(Path(root) / f, term_registry)
                    if res is None: invalid_found = True; continue
                    lg, ok = res
                    logs.append(lg)
                    if not ok: invalid_found = True

    CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHANGELOG_PATH.open("w", encoding="utf-8") as fh:
        for entry in logs:
            json.dump(entry, fh); fh.write("\n")

    sys.exit(1 if invalid_found else 0)

if __name__ == "__main__":
    main()
