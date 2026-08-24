"""One-time helper: prompts for the USAJobs API key interactively and writes
scrapers/usajobs_credentials.json. Run this yourself — nothing here sends
the key anywhere except the local file."""
import json
from pathlib import Path

api_key = input("Paste your USAJobs API key: ").strip()
user_agent = input("Your registered email [simon.delibero@plu.edu]: ").strip() or "simon.delibero@plu.edu"

out = Path(__file__).parent / "usajobs_credentials.json"
out.write_text(json.dumps({"api_key": api_key, "user_agent": user_agent}))
print(f"Saved to {out}")
