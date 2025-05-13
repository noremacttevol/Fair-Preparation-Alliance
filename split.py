site_name: Fair Preparation Alliance
theme:
  name: material
  features:
    - navigation.expand
    - navigation.sections
plugins:
  - search

# Friendly sidebar
nav:
  - Home: index.md          # ← rename or point to your landing page
  - Doctrine:
      - Compass Guide: doctrine/compass_0.md
      - Trust Doctrine: doctrine/trust_0.md
      - Rank Matrix: doctrine/rank_matrix_0.md
  - Plans:
      - ORP Master Plan: plans/orp_master_plan_0.md
      - Offline-First Comms: plans/offline_comms_0.md
  - Gear Lists:
      - National List: gear/national_list_0.md
      - Regional List: gear/regional_list_0.md
  - Appendix:
      - Glossary: appendix/glossary_0.md
"""
FPA multi-folder Markdown chunker
Put this file in:  C:\Obsidian_Main_Vault\FPA\split.py
Run with:          (.venv) PS> python split.py
"""

from pathlib import Path
import shutil
from langchain.text_splitter import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

# ── 1.  Folders that hold your notes  ──────────────────────────────
BASE = Path(__file__).parent           # C:\Obsidian_Main_Vault\FPA
SRC_DIRS = [
    BASE / "New Notes Full",
    BASE / "Zettelkasten",
    BASE / "1.3 Short",
    BASE / "1.3 Full",
]

# ── 2.  Output folder (deleted & rebuilt each run)  ────────────────
OUT = BASE / "chunks"
shutil.rmtree(OUT, ignore_errors=True)
OUT.mkdir()

# ── 3.  Build the two LangChain splitters  ─────────────────────────
header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=True,
)
size_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
)

# ── 4.  Walk every folder → every .md file → write chunks  ─────────
for folder in SRC_DIRS:
    for md in folder.rglob("*.md"):                # <-- 'folder' is defined here
        raw = md.read_text(encoding="utf-8", errors="ignore")

        # 4-A. split by headings  (returns Document objects)
        for i, section in enumerate(header_splitter.split_text(raw)):
            text = section.page_content            # unwrap to plain text

            # 4-B. split each section to ≤1 500-token pieces
            for j, piece in enumerate(size_splitter.split_text(text)):
                safe_name = (
                    md.relative_to(folder)
                      .with_suffix("")
                      .as_posix()
                      .replace("/", "_")
                )
                (OUT / f"{safe_name}_{i}_{j}.md").write_text(
                    piece, encoding="utf-8"
                )

print(f"✅  Finished – {len(list(OUT.glob('*.md')))} chunks written to {OUT}")
