"""
transformer.py
==============
Converts Gemini agent JSON output into Power BI-ready CSV files.

Run this after your agent produces output:
    python transformer.py

Or import and call from agent.py:
    from transformer import transform_and_save
    transform_and_save(agent_json, "meeting.txt")
"""

import json
import hashlib
import pandas as pd
from pathlib import Path
from datetime import datetime, date

# ── Where CSV files will be saved ─────────────────────────────────────────────
# Power BI will point to this folder.
# WHY a dedicated folder? Keep your source data separate from your code.
# Also, if you later tell Power BI to watch this folder, every new CSV
# you drop here is automatically picked up on refresh.
OUTPUT_DIR = Path(__file__).parent / "powerbi_data"


# ── Column definitions ────────────────────────────────────────────────────────
# Defining columns as constants serves two purposes:
# 1. Documentation — you can see the full schema without opening any file
# 2. Consistency — every CSV will have exactly these columns in this order,
#    even if a meeting has zero risks (the risks CSV still has correct headers)

MEETINGS_COLS = [
    "meeting_id",        # Unique ID for this meeting — links all other tables
    "meeting_date",      # When it happened
    "filename",          # Which transcript file this came from
    "summary",           # AI-generated 2-3 sentence overview
    "total_actions",     # Count of action items — useful for quick cards in Power BI
    "total_decisions",   # Count of decisions
    "total_risks",       # Count of risks
    "processed_at",      # When your Python script ran — audit trail
]

ACTION_ITEMS_COLS = [
    "action_id",         # Unique ID for this action item
    "meeting_id",        # Links back to meetings table
    "meeting_date",      # Copied here so you don't need a join for simple visuals
    "owner",             # Who is responsible
    "task",              # What they need to do
    "status",            # "Open" or "Closed" — used for pie charts and filters
    "deadline",          # When it's due
]

DECISIONS_COLS = [
    "decision_id",       # Unique ID
    "meeting_id",        # Links back to meetings
    "meeting_date",      # Denormalized for convenience
    "decision",          # The decision text
]

RISKS_COLS = [
    "risk_id",           # Unique ID
    "meeting_id",        # Links back to meetings
    "meeting_date",      # Denormalized for convenience
    "risk",              # The risk description
    "severity",          # "High", "Medium", or "Low" — used for pie charts
]


# ── ID generation ─────────────────────────────────────────────────────────────

def make_meeting_id(filename: str, meeting_date: str) -> str:
    """
    Generate a stable ID from filename + date.

    WHY not just use random IDs?
    If you process the same transcript twice (e.g. after fixing your prompt),
    a random ID creates a duplicate row. A hash of filename+date always produces
    the same ID for the same meeting — so re-processing just overwrites cleanly.
    """
    raw = f"{filename}_{meeting_date}"
    return "m_" + hashlib.md5(raw.encode()).hexdigest()[:8]


def make_child_id(prefix: str, meeting_id: str, index: int) -> str:
    """
    Make a stable ID for action items, decisions, risks.
    Example: make_child_id("a", "m_abc123", 0) → "a_abc123_0"
    """
    return f"{prefix}_{meeting_id[2:]}_{index}"


# ── Value normalisation ───────────────────────────────────────────────────────
# This is one of the most important steps in data engineering.
# The AI might return "open", "Open", "OPEN", "in progress", "pending" —
# all meaning the same thing. Power BI treats these as DIFFERENT values,
# splitting your pie chart into fragments.
# Normalise at ingestion: enforce a fixed vocabulary.

def normalise_status(raw: str) -> str:
    """Map any status variant to exactly 'Open' or 'Closed'."""
    closed_words = {"closed", "done", "complete", "completed", "resolved", "finished"}
    return "Closed" if str(raw).lower().strip() in closed_words else "Open"


def normalise_severity(raw: str) -> str:
    """Map any severity variant to exactly 'High', 'Medium', 'Low', or 'Unknown'."""
    mapping = {
        "high": "High", "critical": "High", "severe": "High",
        "medium": "Medium", "moderate": "Medium", "med": "Medium",
        "low": "Low", "minor": "Low", "info": "Low",
    }
    return mapping.get(str(raw).lower().strip(), "Unknown")


# ── Row builders ──────────────────────────────────────────────────────────────

def build_meeting_row(data: dict, meeting_id: str, filename: str) -> dict:
    """Build one row for the meetings table."""
    return {
        "meeting_id":     meeting_id,
        "meeting_date":   data.get("meeting_date", "Unknown"),
        "filename":       filename,
        "summary":        data.get("summary", "").replace("\n", " ").strip(),
        "total_actions":  len(data.get("action_items", [])),
        "total_decisions":len(data.get("decisions", [])),
        "total_risks":    len(data.get("risks", [])),
        "processed_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_action_rows(data: dict, meeting_id: str, meeting_date: str) -> list[dict]:
    """Build one row per action item."""
    rows = []
    for i, item in enumerate(data.get("action_items", [])):
        rows.append({
            "action_id":   make_child_id("a", meeting_id, i),
            "meeting_id":  meeting_id,
            "meeting_date":meeting_date,
            "owner":       str(item.get("owner", "Unassigned")).strip(),
            "task":        str(item.get("task", "")).strip(),
            "status":      normalise_status(item.get("status", "Open")),
            "deadline":    str(item.get("deadline", "None")),
        })
    return rows


def build_decision_rows(data: dict, meeting_id: str, meeting_date: str) -> list[dict]:
    """Build one row per decision."""
    rows = []
    for i, item in enumerate(data.get("decisions", [])):
        text = item.get("decision", "") if isinstance(item, dict) else str(item)
        rows.append({
            "decision_id": make_child_id("d", meeting_id, i),
            "meeting_id":  meeting_id,
            "meeting_date":meeting_date,
            "decision":    text.strip(),
        })
    return rows


def build_risk_rows(data: dict, meeting_id: str, meeting_date: str) -> list[dict]:
    """Build one row per risk."""
    rows = []
    for i, item in enumerate(data.get("risks", [])):
        text = item.get("risk", "") if isinstance(item, dict) else str(item)
        rows.append({
            "risk_id":     make_child_id("r", meeting_id, i),
            "meeting_id":  meeting_id,
            "meeting_date":meeting_date,
            "risk":        text.strip(),
            "severity":    normalise_severity(
                               item.get("severity", "Unknown") if isinstance(item, dict) else "Unknown"
                           ),
        })
    return rows


# ── CSV writer ────────────────────────────────────────────────────────────────

def append_to_csv(new_rows: list[dict], filepath: Path, columns: list[str], id_col: str) -> int:
    """
    Append new rows to a CSV file, creating it if it doesn't exist.
    Deduplicates on primary key so re-processing is safe.

    Returns the number of new rows actually written.

    WHY append instead of overwrite?
    You want to accumulate data across many meetings over weeks/months.
    Overwriting would erase all your history every time you process a new meeting.
    Appending means each new meeting ADDS rows — your dataset grows over time.

    WHY deduplicate?
    If you re-process a meeting after fixing your prompt, you don't want
    duplicate rows. We check the primary key and skip rows that already exist.
    This makes the function "idempotent" — safe to run multiple times.

    WHY utf-8-sig encoding?
    Power BI and Excel on Windows can misread plain UTF-8 and corrupt special
    characters (names with accents, non-Latin scripts, em dashes).
    utf-8-sig adds a hidden 3-byte marker at the start of the file that tells
    Windows "this is UTF-8". It costs nothing and prevents encoding headaches.
    """
    filepath.parent.mkdir(exist_ok=True)

    if not new_rows:
        # No data — just make sure the file exists with correct headers
        if not filepath.exists():
            pd.DataFrame(columns=columns).to_csv(
                filepath, index=False, encoding="utf-8-sig"
            )
        return 0

    new_df = pd.DataFrame(new_rows)[columns]

    if filepath.exists():
        existing = pd.read_csv(filepath, encoding="utf-8-sig", dtype=str)
        # Drop rows that share a primary key with incoming rows (dedup)
        existing = existing[~existing[id_col].isin(new_df[id_col])]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined[columns].to_csv(filepath, index=False, encoding="utf-8-sig")
    return len(new_rows)


# ── Public entry point ────────────────────────────────────────────────────────

def transform_and_save(agent_output: "dict | str", source_filename: str) -> dict:
    """
    Main function. Takes the agent's JSON output, builds 4 CSV files.

    Call this from agent.py after getting the AI response:
        result = transform_and_save(agent_json_dict, "meeting.txt")
        print(result)

    Args:
        agent_output    : The dict or JSON string from your Gemini agent.
        source_filename : Name of the transcript file (for traceability).

    Returns:
        dict with meeting_id and row counts per table.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Parse JSON string if needed (handle ```json ... ``` wrapping too)
    if isinstance(agent_output, str):
        cleaned = (agent_output.strip()
                   .removeprefix("```json").removeprefix("```")
                   .removesuffix("```").strip())
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Agent output is not valid JSON.\nError: {e}\n"
                             f"First 300 chars: {agent_output[:300]}")
    else:
        data = agent_output

    meeting_date = data.get("meeting_date", date.today().isoformat())
    meeting_id   = make_meeting_id(source_filename, meeting_date)

    meeting_row   = build_meeting_row(data, meeting_id, source_filename)
    action_rows   = build_action_rows(data, meeting_id, meeting_date)
    decision_rows = build_decision_rows(data, meeting_id, meeting_date)
    risk_rows     = build_risk_rows(data, meeting_id, meeting_date)

    paths = {
        "meetings":     OUTPUT_DIR / "meetings.csv",
        "action_items": OUTPUT_DIR / "action_items.csv",
        "decisions":    OUTPUT_DIR / "decisions.csv",
        "risks":        OUTPUT_DIR / "risks.csv",
    }

    counts = {
        "meetings":     append_to_csv([meeting_row], paths["meetings"],     MEETINGS_COLS,     "meeting_id"),
        "action_items": append_to_csv(action_rows,   paths["action_items"], ACTION_ITEMS_COLS, "action_id"),
        "decisions":    append_to_csv(decision_rows, paths["decisions"],    DECISIONS_COLS,    "decision_id"),
        "risks":        append_to_csv(risk_rows,     paths["risks"],        RISKS_COLS,        "risk_id"),
    }

    return {"meeting_id": meeting_id, "rows_written": counts,
            "output_dir": str(OUTPUT_DIR.resolve())}


# ── Test with sample data ─────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run: python transformer.py
    # This tests the full pipeline with sample data so you can check
    # the CSV output before connecting Power BI.

    sample = {
        "meeting_date": "2026-06-16",
        "summary": (
            "The Q3 roadmap review covered three key features: notification redesign, "
            "CSV export, and mobile push notifications. Decisions were made on all three, "
            "and multiple action items were assigned with deadlines."
        ),
        "action_items": [
            {"owner": "John",  "task": "Fix API authentication bug",  "status": "Open",   "deadline": "2026-06-20"},
            {"owner": "Priya", "task": "Update API documentation",    "status": "Open",   "deadline": "2026-06-22"},
            {"owner": "Arjun", "task": "Review pull request #142",    "status": "Closed", "deadline": "2026-06-17"},
            {"owner": "John",  "task": "Set up Redis cache",          "status": "Open",   "deadline": "2026-06-25"},
        ],
        "decisions": [
            {"decision": "Move product demo to Friday 2026-06-19"},
            {"decision": "Use Redis for session caching"},
            {"decision": "Badge count truncated at 99+ on mobile"},
        ],
        "risks": [
            {"risk": "Backend integration delay may push the demo",       "severity": "High"},
            {"risk": "Third-party API rate limits not yet confirmed",      "severity": "Medium"},
            {"risk": "QA regression suite not started for push features", "severity": "Low"},
        ],
    }

    print("\nRunning transformer with sample data...")
    result = transform_and_save(sample, "sample_meeting.txt")

    print(f"\n✓ Meeting ID : {result['meeting_id']}")
    print(f"✓ Rows written: {result['rows_written']}")
    print(f"✓ Files saved to: {result['output_dir']}")

    # Preview each file
    print("\n" + "="*60)
    for name in ["meetings", "action_items", "decisions", "risks"]:
        path = Path(result["output_dir"]) / f"{name}.csv"
        df   = pd.read_csv(path, encoding="utf-8-sig")
        print(f"\n{name.upper()} ({len(df)} rows):")
        print(df.to_string(index=False, max_colwidth=45))
    print("="*60)
    print("\n✅ Open the powerbi_data/ folder to see your CSV files.")
