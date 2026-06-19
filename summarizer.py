"""
Meeting Summarizer — Level 1 (Gemini Free Tier)
=================================================
Uses the NEW google-genai package (google-generativeai is deprecated).
Free tier: 1,500 requests/day, no credit card required.
Get your key at: https://aistudio.google.com
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types


# =============================================================================
# CONSTANTS
# =============================================================================

MODEL_NAME = "gemini-2.5-flash"   # Free tier, fast, excellent quality
MAX_TOKENS  = 2048
TEMPERATURE = 0.3

BASE_DIR        = Path(__file__).parent
TRANSCRIPTS_DIR = BASE_DIR / "transcripts"
SUMMARIES_DIR   = BASE_DIR / "summaries"


# =============================================================================
# SYSTEM PROMPT
# =============================================================================
SYSTEM_PROMPT = """You are a meeting analysis agent.

Analyze the transcript and return your response as a single valid JSON object.
No explanation before or after. Only the JSON object.

Use exactly this structure:
{
  "meeting_date": "YYYY-MM-DD or Unknown",
  "summary": "2-3 sentence overview",
  "action_items": [
    {"owner": "Name", "task": "Description", "status": "Open or Closed", "deadline": "Date or None"}
  ],
  "decisions": [
    {"decision": "Description"}
  ],
  "risks": [
    {"risk": "Description", "severity": "High, Medium, or Low"}
  ]
}
"""


def setup_directories() -> None:
    TRANSCRIPTS_DIR.mkdir(exist_ok=True)
    SUMMARIES_DIR.mkdir(exist_ok=True)


def load_api_key() -> str:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in your .env file.")
        print("  1. Go to https://aistudio.google.com")
        print("  2. Click 'Get API key' → 'Create API key'")
        print("  3. Add to .env:  GEMINI_API_KEY=your_key_here")
        sys.exit(1)
    return api_key


def read_transcript(filepath: Path) -> str:
    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}")
        print(f"  Place your transcript inside: {TRANSCRIPTS_DIR}/")
        sys.exit(1)
    if filepath.stat().st_size == 0:
        print(f"ERROR: File is empty: {filepath}")
        sys.exit(1)
    text = filepath.read_text(encoding="utf-8", errors="replace")
    print(f"✓ Transcript loaded: {len(text):,} characters")
    return text


def build_prompt(transcript_text: str) -> str:
    word_count = len(transcript_text.split())
    return (
        
        f"Please summarize the following Microsoft Teams meeting transcript.\n"
        f"Transcript length: approximately {word_count:,} words.\n\n"
        f"--- TRANSCRIPT START ---\n"
        f"{transcript_text}\n"
        f"--- TRANSCRIPT END ---"
    )


def call_llm(client: genai.Client, prompt: str) -> str:
    print("⏳ Calling Gemini API... (this may take 5–15 seconds)")
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    max_output_tokens=MAX_TOKENS,
    temperature=0.3,
    thinking_config=types.ThinkingConfig(
        thinking_budget=0
    )
),
        )
        print("✓ API call successful.")
        return response.text.strip()

    except Exception as e:
        err = str(e).lower()
        if "429" in err or "quota" in err or "rate" in err or "resource_exhausted" in err:
            print("ERROR: Rate limit hit. Wait 60 seconds and try again.")
            print("  Free tier: 15 requests/min, 1,500 requests/day.")
        elif "401" in err or "403" in err or "api_key" in err or "permission" in err:
            print("ERROR: Invalid API key.")
            print("  Check GEMINI_API_KEY in your .env file.")
        elif "404" in err or "not found" in err:
            print(f"ERROR: Model '{MODEL_NAME}' not found.")
            print("  Your key may not have access to this model yet.")
            print("  Wait a few minutes after creating a new key, then retry.")
        else:
            print(f"ERROR: API call failed.\n  {type(e).__name__}: {e}")
        sys.exit(1)


def save_summary(summary_text: str, source_filename: str) -> Path:
    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path  = SUMMARIES_DIR / f"summary_{timestamp}.txt"
    output_content = (
        f"MEETING SUMMARY\n"
        f"{'=' * 60}\n"
        f"Generated:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Source file: {source_filename}\n"
        f"Model used:  {MODEL_NAME}\n"
        f"{'=' * 60}\n\n"
        f"{summary_text}\n"
    )
    output_path.write_text(output_content, encoding="utf-8")
    return output_path


def main() -> None:
    print("\n" + "=" * 50)
    print("  Microsoft Teams Meeting Summarizer — Level 1")
    print("  Powered by Google Gemini (Free Tier)")
    print("=" * 50 + "\n")

    setup_directories()

    if len(sys.argv) < 2:
        print("Usage:   python summarizer.py <filename.txt>")
        print("Example: python summarizer.py meeting.txt")
        print(f"\nPlace transcript files in: {TRANSCRIPTS_DIR}/")
        existing = list(TRANSCRIPTS_DIR.glob("*.txt"))
        if existing:
            print("\nTranscripts found:")
            for f in existing:
                print(f"  → {f.name}")
        sys.exit(1)

    transcript_path = TRANSCRIPTS_DIR / sys.argv[1]

    api_key = load_api_key()
    client  = genai.Client(api_key=api_key)
    print("✓ Gemini client initialized.\n")

    transcript_text = read_transcript(transcript_path)
    prompt          = build_prompt(transcript_text)
    print(f"✓ Prompt built ({len(prompt.split()):,} words).\n")

    summary_text = call_llm(client, prompt)
    output_path  = save_summary(summary_text, sys.argv[1])

    print(f"\n✓ Summary saved to: {output_path}\n")
    print("=" * 50)
    print("SUMMARY PREVIEW")
    print("=" * 50)
    print(summary_text)
    print("=" * 50 + "\n")
    print("✅ Done!")


if __name__ == "__main__":
    main()