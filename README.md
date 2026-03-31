# Career Engine

Backend script to append resume sections to a Google Docs template using the Google Docs API.

## What It Inserts

Running the script appends these blocks to the end of the configured document:

1. Education section
2. Technical Projects section
3. Sample project entry in Technical Projects
4. Skills section

Section headers are inserted with bold styling and larger font size. Body lines are inserted with standard body styling.

## Prerequisites

- Python 3.11+
- OAuth client file at `credentials.json`
- Existing token file `token.json` (or complete OAuth flow on first run)
- Valid Google Doc id in `DOCUMENT_ID` inside `main.py`

## Run

Use your project environment, then run:

python main.py

The script uses append-only behavior. Re-running it appends a new copy of all sections.