# Meeting Intelligence Agent

A production-grade AI pipeline that transforms unstructured Microsoft Teams meeting transcripts into structured intelligence — surfaced through a Power BI analytics dashboard.

Built with Google Gemini API (free tier). No LangChain, no vector databases, no unnecessary frameworks.

---

## Overview

Most meeting intelligence tools are black boxes. This project is not.

Every architectural decision is explicit: why an agent instead of a single prompt, why CSV instead of a database, why separate tool functions instead of one monolithic call. The result is a system that is simple enough to understand completely, and structured well enough to extend without rewriting.

**Input:** A `.txt` Microsoft Teams transcript  
**Output:** Structured meeting intelligence + a live Power BI dashboard

---

## Architecture

```
Transcript (.txt)
       │
       ▼
  agent.py  ←─── Entry point and orchestrator
       │
       ├── core/planner.py   ←─── LLM decides which tools to run  [API Call #1]
       │
       ├── tools/summarize.py        [API Call #2]
       ├── tools/action_items.py     [API Call #3]
       ├── tools/decisions.py        [API Call #4]
       ├── tools/risks.py            [API Call #5]
       └── tools/followup_email.py   [API Call #6, conditional]
       │
       ├── core/reporter.py  ←─── Assembles tool outputs into report
       ├── transformer.py    ←─── Normalises JSON → 4 CSV tables
       │
       ▼
  powerbi_data/
  ├── meetings.csv
  ├── action_items.csv
  ├── decisions.csv
  └── risks.csv
       │
       ▼
  Power BI Dashboard
  ├── KPI Cards (meetings, open actions, decisions)
  ├── Bar Chart (tasks by owner)
  ├── Pie Chart (risk by severity)
  ├── Table (action items with owners and deadlines)
  └── Date Slicer (filter all visuals by time range)
```

### Why This Qualifies as an Agent

A plain LLM call has a fixed input-output contract. An agent uses the LLM to decide what actions to take.

In this system, `core/planner.py` sends the transcript to Gemini and receives back a JSON list of tools to execute. The code runs whatever the LLM selected. If a meeting has no risks, the risks tool is skipped. If a meeting has clear outcomes, the follow-up email tool is included. The LLM drives the execution path — not hardcoded logic.

That planning-then-executing loop is the architectural line between "prompt" and "agent."

---

## Project Structure

```
meeting-agent/
│
├── agent.py                # Entry point. Orchestrates the full pipeline.
│
├── core/
│   ├── llm.py              # Gemini client. Single place for all API calls.
│   ├── planner.py          # Agent brain. LLM decides which tools to run.
│   └── reporter.py         # Assembles tool outputs into final report.
│
├── tools/
│   ├── summarize.py        # Tool: 2-3 sentence meeting overview
│   ├── action_items.py     # Tool: extract assigned tasks with owners
│   ├── decisions.py        # Tool: extract finalised decisions
│   ├── risks.py            # Tool: extract blockers and risk severity
│   └── followup_email.py   # Tool: draft post-meeting email (conditional)
│
├── transformer.py          # Converts agent JSON output → 4 normalised CSVs
│
├── transcripts/            # Input folder — place .txt transcripts here
├── reports/                # Output folder — generated text reports
├── powerbi_data/           # Output folder — CSVs consumed by Power BI
│
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Data Model

The transformer normalises the agent's JSON output into a relational schema. Each table has a single responsibility. Tables connect via `meeting_id`.

```
meetings          (1) ──────────────────────────── (*) action_items
meeting_id  PK         │                                action_id   PK
meeting_date           │                                meeting_id  FK
filename               │                                owner
summary                │                                task
total_actions          │                                status
total_decisions        │                                deadline
total_risks            │
processed_at           ├────────────────────────── (*) decisions
                       │                                decision_id PK
                       │                                meeting_id  FK
                       │                                decision
                       │
                       └────────────────────────── (*) risks
                                                        risk_id     PK
                                                        meeting_id  FK
                                                        risk
                                                        severity
```

**Why this structure:**  
Power BI is a relational query engine. It cannot filter, group, or aggregate data that lives in nested JSON or multi-value cells. One row per atomic fact — one action item, one decision, one risk — is what enables every chart and filter in the dashboard.

**Why CSV over SQL at this stage:**  
The bottleneck is not read/write throughput — it is understanding the pipeline. CSV keeps every transformation visible and debuggable. The upgrade path to PostgreSQL or SQLite is a single function swap: `df.to_csv()` → `df.to_sql()`. The data modeling logic is identical.

---

## Setup

### Prerequisites

- Python 3.10+
- Power BI Desktop (free — [download here](https://www.microsoft.com/en-us/power-platform/products/power-bi/desktop))
- Google Gemini API key (free — [get one here](https://aistudio.google.com))

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd meeting-agent

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy the environment template
cp .env.example .env
```

Open `.env` and add your key:

```
GEMINI_API_KEY=your_key_here
```

Your key never touches your code. It is loaded at runtime via `python-dotenv` and excluded from version control via `.gitignore`.

---

## Usage

### Run the agent on a transcript

```bash
python agent.py meeting.txt
```

Place your `.txt` transcript files in the `transcripts/` folder. The agent will:

1. Plan which tools to run based on the transcript content
2. Execute each selected tool (separate focused API call per tool)
3. Assemble a structured text report in `reports/`
4. Write normalised rows to all four CSVs in `powerbi_data/`

### Refresh the Power BI dashboard

After processing one or more new transcripts:

```
Power BI Desktop → Home → Refresh
```

All visuals update automatically. No reconnection needed.

### Test the transformer independently

```bash
python transformer.py
```

Runs the data transformation with sample data and prints a preview of all four CSVs. Use this to verify your data model before connecting Power BI.

---

## Design Decisions

### One API call per tool, not one call for everything

Each tool (`summarize.py`, `action_items.py`, etc.) makes its own API call with its own focused system prompt. The alternative — asking one call to produce everything — yields a single blob of text that must be parsed, fails unpredictably when the model deviates from the expected format, and cannot be tested or improved in isolation.

Focused calls produce focused outputs. The latency cost (5 calls vs 1) is irrelevant at this scale. The quality and maintainability gains are not.

### Deterministic IDs over random UUIDs

Meeting IDs are derived from `md5(filename + date)`. Action, decision, and risk IDs are derived from `meeting_id + index`. This makes the pipeline idempotent: re-processing the same transcript produces the same IDs, and the CSV deduplication logic silently overwrites rather than appending duplicate rows. Random UUIDs would accumulate duplicates on every rerun.

### Value normalisation at ingestion

The agent may return `"open"`, `"Open"`, `"in progress"`, or `"pending"` for the same concept. Power BI treats these as distinct values — splitting bar charts and pie charts incorrectly. The transformer enforces a fixed vocabulary (`Open`/`Closed`, `High`/`Medium`/`Low`) before writing to CSV. Normalise at the boundary between AI output and structured data, always.

### No LangChain, LangGraph, or orchestration frameworks

Each tool is a Python function with a single prompt. The agent loop is 15 lines of code in `agent.py`. Adding an orchestration framework here would mean learning a framework's abstractions, debugging framework-level errors, and reading framework documentation — in exchange for capabilities (cycles, state, memory, tool-calling protocols) that this use case does not need. Complexity is a liability. Every dependency added must justify itself against the problem it solves.

---

## Power BI Dashboard

The dashboard connects directly to the `powerbi_data/` folder. Four tables, three relationships, seven visuals.

| Visual | Source table | Business question answered |
|---|---|---|
| Card: Total Meetings | meetings | How many meetings have we analyzed? |
| Card: Open Action Items | action_items | How much unfinished work exists? |
| Card: Total Decisions | decisions | Are our meetings producing outcomes? |
| Bar chart: Tasks by owner | action_items | Who is overloaded? Who is idle? |
| Pie chart: Risk severity | risks | What is the health of the project? |
| Table: Action items | action_items | What exactly needs to be done, by whom, by when? |
| Date slicer | meetings | How do all metrics look for a given time range? |

**Refreshing:** Home → Refresh in Power BI Desktop after running `agent.py` on new transcripts.

---

## Limitations

| Limitation | Resolution path |
|---|---|
| Manual pipeline trigger | Schedule via Task Scheduler (Windows) or cron (Linux/macOS) |
| Local CSV files | Migrate to SQLite → PostgreSQL as data volume grows |
| Manual Power BI refresh | Publish to Power BI Service for scheduled cloud refresh |
| Transcript must be exported manually | Microsoft Graph API integration for automatic transcript retrieval |
| Single-user local setup | FastAPI wrapper + shared Power BI Service workspace for team access |

---

## Tech Stack

| Component | Technology | Reason |
|---|---|---|
| LLM | Google Gemini 2.5 Flash | Best free-tier model available. Zero cost for internship scale. |
| AI SDK | `google-genai` | Official current SDK. `google-generativeai` is deprecated. |
| Language | Python 3.10+ | Industry standard for AI pipelines. Fastest iteration speed. |
| Data transformation | `pandas` | Handles CSV I/O, deduplication, and schema enforcement cleanly. |
| Secret management | `python-dotenv` | Keeps API keys out of source code. Industry standard for local dev. |
| BI layer | Power BI Desktop | Free. Connects natively to CSV. No configuration needed. |

---

## Security

- API keys are stored in `.env` — never committed to version control
- `.env` is listed in `.gitignore`
- `.env.example` documents required variables without exposing values
- Meeting transcripts may contain confidential information — review your organisation's data policy before processing sensitive content
- For enterprise use, consider Azure OpenAI or a local model to keep transcript data on-premise

---

## License

MIT License. See `LICENSE` for details.

---

## Author

PUPPALA RATNA HARIKA
