import json
import os
# Google Sheets
import asyncio
import gspread
from google.oauth2.service_account import Credentials
import warnings

# Path to the JSON key file you downloaded from Google Cloud Console
CREDENTIALS_FILE    = "./cred/event-scraper-prototype-72eb4b0865ae.json"
SERVICE_ACCOUNT_EMAIL = "eventscraper@event-scraper-prototype.iam.gserviceaccount.com"
GOOGLE_SHEET_NAME = "News Intelligence - Data & Dashboard"
GOOGLE_SHEET_TAB = "Data"  
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive", # Google Drive API
]
FILEPATH = r'D:\Portofolio\news-summarizer\scrapers\outputs'

def get_sheet():
    """Authenticate and return the target worksheet."""
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)

    print(f"[*] Authenticating as '{SERVICE_ACCOUNT_EMAIL}' …")

    try:
        sheet = client.open(GOOGLE_SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sheet = client.create(GOOGLE_SHEET_NAME)
        # Share with anyone who has the link (optional — remove if you prefer restricted)
        sheet.share(None, perm_type="anyone", role="writer")
        print(f"[+] Created new Google Sheet: '{GOOGLE_SHEET_NAME}'")

    try:
        ws = sheet.worksheet(GOOGLE_SHEET_TAB)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=GOOGLE_SHEET_TAB, rows="1000", cols="20")
        print(f"[+] Created new tab: '{GOOGLE_SHEET_TAB}'")

    return ws

def write_to_sheet(ws, data: list[dict]):
    """Write event rows to the worksheet, with a header row."""
    if not data:
        print("[!] No data to write.")
        return

    headers = [
        "news_platform",
        "category",
        "title",
        "author",
        "date_publish",
        "content",
        "date_scraped",
        "source_url",
    ]

    rows = [headers]
    for e in data:
        rows.append([
            e.get("news_platform", ""),
            e.get("category", ""),
            e.get("title", ""),
            e.get("author", ""),
            e.get("date_publish", ""),
            e.get("content", ""),
            e.get("date_scraped", ""),
            e.get("source_url", ""),
        ])

    ws.clear()
    ws.update("A1", rows)
    print(f"[+] Written {len(data)} articles to Google Sheet '{GOOGLE_SHEET_NAME}' → tab '{GOOGLE_SHEET_TAB}'")

 
# ── Step 3: Write to Google Sheets ───────────────────────────────────
def main_upload():
    print("\n[*] Loading scraped data from JSON files …")
    all_data = []
    for filename in os.listdir(FILEPATH):
        if filename.endswith(".json"):
            with open(os.path.join(FILEPATH, filename), "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_data.extend(data)
                else:
                    all_data.append(data)

    print(f"[+] Found {len(all_data)} news articles.")

    print("\n[*] Connecting to Google Sheets …")
    ws = get_sheet()
    write_to_sheet(ws, all_data)

    print("\n✅ Done!")

if __name__ == "__main__":
    main_upload()
    # asyncio.run(main_upload())
