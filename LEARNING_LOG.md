# Document Intelligence Pipeline — Revision Log

Keep entries brief. Add each completed step after reviewing the code or output.

## Goal and approach

- Extract document name, parties, agreement date, effective date, and governing law from CUAD contracts, with validated evidence.
- Start with supplied text; add PDF parsing later to separate extraction errors from parsing errors.
- Build in small steps: implement, run, review, then continue.

## Day 1 — Setup and Python foundations

### 1. Check local tools — verified
- Workspace: `C:\Users\Anita\Documents\AI\document-intelligence`.
- Python: `3.14.4`; use `python` because the `py` launcher did not find it.
- Git: `2.41.0`; Docker CLI: `25.0.3` (engine not checked).
- Check AI/parser dependency compatibility before installing packages.

### 2. Create virtual environment — verified
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip --version
```
- `.venv` isolates project packages; pip `26.0.1` points inside it.
- Run its interpreter directly; activation and execution-policy changes are unnecessary.
- Keep application code outside `.venv`; the environment can be recreated.
- VS Code interpreter selection was instructed but not independently verified.

### 3. Save a synthetic contract as JSON — verified
- File: `scripts/create_sample.py`.
- `dict` ≈ JS object / PHP associative array; `None` ≈ `null`.
- `def` declares functions; indentation defines their bodies; type hints describe expected types.
- `Path(__file__).resolve().parent.parent` finds the project root.
- `Path / "folder"` joins paths; `mkdir(parents=True, exist_ok=True)` creates missing folders.
- `with` closes the file automatically; `json.dump` writes UTF-8 JSON with indentation.
- The `__name__ == "__main__"` guard calls `main()` when executed directly.
```powershell
.\.venv\Scripts\python.exe scripts\create_sample.py
```
- Result: `outputs/sample_contract.json`; Python `None` becomes JSON `null`.

### 4. Practice lists, loops, and missing values — verified
- Added a third party; `len(contract["parties"])` returns `3`.
- `for party in contract["parties"]` ≈ JS `for...of` / PHP `foreach`.
- `if contract["effective_date"] is None` checks a missing date.
- Run confirmed all three names and `Effective date is missing`.

### 5. Protect files and create project structure — verified
- Added `.gitignore` for environments, secrets, caches, data, and outputs; `.env.example` remains allowed.
- Created `app/__init__.py`, `tests/`, `data/raw/`, and `data/processed/`; initialized Git.
- Agent Git checks require a command-scoped `safe.directory` because the sandbox user differs from the folder owner; no global setting changed.

## Next steps — pending

- Review initial Git changes and commit.
- Inspect a real CUAD record and annotation conventions before defining schemas or scoring.
- Build contract-level development/test manifests with field coverage and leakage checks.
