## 1. What the script does – “process_markdown”

````text
for every .md file in <src>:
    1. read text
    2. walk line‑by‑line
    3. detect pseudo‑headers:
          • **bold**  → header
          • Text:     → header
          • 2025 07 15 → header
          • 1. Section  → header
          • ALL CAPS  (filtered) → header
          • normal # headings → keep
    4. compute the correct header level (1–6) based on breadcrumb context
    5. replace the line with a proper `#` header
    6. immediately after the header inject a metadata block:
          ```
          [DocTitle: <file‑title or H1>]
          [Path: <relative/path.md>]
          [Section: <H1> > <H2> > …]
          [Aliases: <keyword list>]
          ```
    7. write the augmented file to <dst> preserving directory layout
````

### Header‑to‑header mapping

| Input                                    | Output                 | Example                                               |
| ---------------------------------------- | ---------------------- | ----------------------------------------------------- |
| `**Installation Guide**`                 | `# Installation Guide` | bold → level‑1 (or level‑2 if inside another section) |
| `Meeting:`                               | `# Meeting`            | colon → level‑1 or 2                                  |
| `2025 07 15`                             | `# 2025 07 15`         | date → level‑1 or 2                                   |
| `1. John Smith`                          | `## 1. John Smith`     | numbered → level‑2 or deeper                          |
| `ALL CAPS TEXT` (no “NOTE”, “TODO” etc.) | `# All Caps Text`      | all‑caps → level‑1 or 2                               |

> **Why these styles?**  
> Many docs (notes, meeting minutes, docs in non‑markdown tools) use the patterns above. Normalising them makes each section uniquely addressable for vector DBs.

### Metadata block

```
[DocTitle: <title>]
[Path: <rel/path.md>]
[Section: <breadcrumb>]
[Aliases: <k1, k2, …>]
```

- `DocTitle` – H1 of the file (or filename if missing).
- `Path` – file path relative to the input root.
- `Section` – concatenated breadcrumbs (`H1 > H2 > H3`).
- `Aliases` – up to 5 keyword terms extracted from the heading.

> **Why?**  
> Embedding engines treat the block as part of the chunk, giving downstream models explicit context and easy search‑by‑field capabilities.

---

## 2. Core Functions & How They Work

| Function                                                            | Purpose                                                             | Key logic                                                                           |
| ------------------------------------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `check_header_patterns(line)`                                       | Classify a line into a header pattern.                              | Regex checks in order: markdown, bold, colon, date, numbered, all‑caps.             |
| `determine_header_level_by_context(breadcrumb, pattern_type, text)` | Guess header level when the pattern isn’t a normal markdown header. | Rules: dates → level 1/2, colon → 2–3, numbered → 2–4, all‑caps → 1/2, default → 2. |
| `determine_bold_header_level(breadcrumb, lines, idx)`               | More context‑aware level for `**bold**` headers.                    | Looks ahead for list/indentation to decide between level‑1 and 2.                   |
| `convert_to_proper_header(text, level, pattern_type)`               | Build a clean markdown header string.                               | Prefixes `#` repeated `level` times.                                                |
| `guess_aliases_from_heading(text)`                                  | Simple heuristics to pull up to 5 keywords.                         | Strips punctuation, removes short words (<3 chars), caps to 120 chars total.        |
| `build_header_block(doc_title, rel_path, breadcrumb, aliases)`      | Formats the 4‑line metadata block.                                  | Handles empty aliases and trims output.                                             |
| `process_markdown(md_text, rel_path, file_stem)`                    | Orchestrates the whole line‑by‑line walk.                           | Maintains `breadcrumb`, avoids duplicate blocks, outputs final string.              |
| `main()`                                                            | CLI wrapper                                                         | Parses `--in` and `--out`, walks the file tree, writes outputs.                     |

> **Notice** – no third‑party libs, just `argparse`, `re`, `pathlib`.  
> Makes it safe to copy‑paste into other projects or container images.

---

## 3. Running the Tool

### 3‑1. From the command line (Python)

```bash
python augment_markdown.py --in ./docs --out ./docs_augmented
```

_Creates an `docs_augmented` folder that mirrors the source tree and contains the augmented markdown files._

### 3‑2. Windows batch

```cmd
augment_markdown.bat "C:\MyDocs" "C:\MyDocs_Augmented"
```

### 3‑3. Windows PowerShell

```powershell
.\augment_markdown.ps1 -InputPath "C:\MyDocs" -OutputPath "C:\MyDocs_Augmented"
```

---

## 4. Replicating the Process in Other Software

1. **Copy the core logic**
   - If you’re writing a plugin or integration, import the `augment_markdown.py` module and call `process_markdown(md_text, rel_path, file_stem)` directly.

2. **Replace the input source**
   - The script reads plain text from disk; you can feed it strings from an API, a cloud bucket, or a database.

3. **Adjust the header heuristics**
   - Open `augment_markdown.py` → modify the regexes or the `determine_header_level_by_context` rules to match your own document conventions.

4. **Use the metadata block**
   - If your downstream system expects JSON instead of the square‑bracket format, replace `build_header_block` with a JSON serializer.
   - Example:

   ```python
   import json
   def build_header_block(doc_title, rel_path, breadcrumb, aliases):
       return json.dumps({
           "DocTitle": doc_title,
           "Path": rel_path,
           "Section": breadcrumb,
           "Aliases": aliases,
       }) + "\n\n"
   ```

5. **Ingest into a vector store**
   - Split the augmented text into chunks (e.g., 512‑token windows).
   - Store each chunk with its metadata fields; retrieval will then be able to query by `Section` or `Aliases`.

6. **Automate**
   - Add the script to a CI pipeline or a scheduled Lambda that watches your docs repo, runs the augmentation, and pushes the processed files to your RAG data lake.

---

## 5. Quick‑Start Checklist for Your New Software

- [ ] **Add `augment_markdown.py`** to your codebase.
- [ ] **Expose a wrapper** (CLI or API endpoint) that accepts a directory or string.
- [ ] **Validate header patterns** by running the bundled tests (you can write a few `pytest` cases).
- [ ] **Integrate metadata extraction** into your chunk‑creation pipeline.
- [ ] **Deploy** – e.g., Docker image with `python:3.11-slim`, copy the script, run `python augment_markdown.py`.

---

## 6. Key Take‑aways

| What you get         | How to use it                                                                 |
| -------------------- | ----------------------------------------------------------------------------- |
| _Normalized headers_ | Run once on all docs; downstream tools no longer need to handle messy styles. |
| _Metadata block_     | Auto‑generated breadcrumbs, aliases, and file paths.                          |
| _Zero deps_          | Drop‑in for any Python‑enabled environment.                                   |
| _Extensible regexes_ | Edit the patterns if your docs use different pseudo‑header conventions.       |
| _Portable CLI_       | Works on Windows (batch/ps1) and \*nix (plain Python).                        |

Feel free to copy the script into your own project, tweak the regexes, and use the `process_markdown` function directly wherever you need to enrich markdown for RAG or any other knowledge‑base use‑case.
