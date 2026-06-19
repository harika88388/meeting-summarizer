# Meeting Summarizer — Level 1

A Python script that summarizes Microsoft Teams meeting transcripts using the OpenAI API.

## What It Does

Input: A `.txt` Teams transcript file  
Output: A structured, bullet-point summary with decisions, action items, and key topics

---

## Architecture

```
transcript.txt
      ↓
  Python Script (summarizer.py)
      ↓  reads file → builds prompt → calls API
  OpenAI API (gpt-4o-mini)
      ↓  generates summary
  summary_YYYYMMDD_HHMMSS.txt
```

---

## Setup (One-Time)

### 1. Clone / Download the project
```bash
cd your-projects-folder
# Place the project files here
```

### 2. Create a virtual environment
```bash
python -m venv venv

# Activate it:
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

> **WHY a virtual environment?**  
> Python packages installed globally affect every project on your machine.  
> A virtual environment is an isolated Python installation just for this project.  
> This prevents version conflicts between projects and keeps your system Python clean.

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure your API key
```bash
cp .env.example .env
```
Then open `.env` and replace `your_openai_api_key_here` with your actual key.

Get your key from: https://platform.openai.com/api-keys

---

## Usage

```bash
# Place your transcript in the transcripts/ folder, then:
python summarizer.py meeting.txt

# General form:
python summarizer.py <filename.txt>
```

### Example Output (in terminal and saved to summaries/)

```
MEETING SUMMARY
============================================================
Generated:     2024-07-15 11:05:32
Source file:   meeting.txt
Model used:    gpt-4o-mini
Tokens used:   1,847 (prompt: 1,653 | completion: 194)
============================================================

**Meeting Overview**
- Q3 Product Roadmap Review; 5 attendees (Priya, Arjun, Deepa, Rohan, Simran)

**Key Topics Discussed**
- Notification redesign badge behavior on small screens
- CSV export feature scoping and async architecture
- Mobile push notification approval and technical planning
- API rate limit issue with third-party data provider

**Decisions Made**
- Badge count truncated at 99+ for notification redesign
- CSV export to use async background processing for exports over 10,000 rows
- Mobile push notifications approved for Q3, targeting September launch
- Redis caching to be implemented as short-term fix for API rate limits

**Action Items**
- Deepa: Update notification mockup with 99+ badge count → by Wednesday EOD
- Arjun: Add CSV export async processing to sprint backlog → today
- Simran: Write up customer requests for share-via-link feature → end of week
- Arjun: Implement Redis cache for dashboard queries → end of next week
- Priya: Seek budget approval for third-party API enterprise plan upgrade
- Rohan: Start test plan for mobile push notification regression suite → this week
- Simran: Draft go-to-market announcement for push notifications → next month

**Open Questions / Parking Lot**
- Share-via-link option for CSV export (scoped as separate feature)
- Third-party API provider upgrade ($800/month) pending budget approval
```

---

## Project Structure

```
meeting-summarizer/
├── .env                 ← Your API key (NEVER commit this)
├── .env.example         ← Template showing required variables
├── .gitignore           ← Git exclusion rules
├── requirements.txt     ← Python dependencies
├── summarizer.py        ← Main script
├── transcripts/         ← Put your transcript files here
│   └── meeting.txt      ← Sample transcript (provided)
└── summaries/           ← Generated summaries appear here
```

---

## Cost Estimate

Using `gpt-4o-mini` (as of 2024 pricing):
- A typical 90-minute meeting transcript: ~2,000 tokens total
- Estimated cost per summary: **~$0.001 USD** (less than one-tenth of a cent)

---

## Known Limitations (Level 1)

| Limitation | Level Where It's Resolved |
|------------|--------------------------|
| Manual file placement (no Teams integration) | Level 3 |
| One transcript at a time (no batch processing) | Level 2 |
| No cost/usage tracking dashboard | Level 2 |
| Very long transcripts may exceed context window | Level 2 (chunking) |
| No searchable history of past summaries | Level 2 (SQLite) |
| Transcript data sent to OpenAI servers | Use Azure OpenAI for enterprise |

---

## Security Notes

- **Never** commit your `.env` file. It's in `.gitignore` for this reason.
- Review OpenAI's [data usage policy](https://openai.com/policies/privacy-policy) before summarizing confidential meetings.
- For meetings with sensitive content (HR, legal, financial), consider Azure OpenAI — data stays within your Azure tenant.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `OPENAI_API_KEY not found` | Check that `.env` exists and contains the key |
| `AuthenticationError` | Verify your API key is valid and not expired |
| `RateLimitError` | Check billing at platform.openai.com/usage |
| `File not found` | Ensure the transcript is in the `transcripts/` folder |
| `UnicodeDecodeError` | Re-save the transcript as UTF-8 in a text editor |

---

## What to Build Next (Level 2 Ideas)

1. **Batch processing**: Summarize all `.txt` files in a folder in one run
2. **SQLite logging**: Store every summary with metadata (cost, model, timestamp)
3. **Chunking strategy**: Handle very long transcripts using map-reduce summarization
4. **Web interface**: Simple Flask/FastAPI frontend for non-technical users
5. **Cost dashboard**: Track spending over time per user/project

---

## Learning Resources

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Python dotenv Documentation](https://saurabh-kumar.com/python-dotenv/)
- [Tokenizer Tool (see how tokens work)](https://platform.openai.com/tokenizer)
