import os
import logging
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest, GetRepliesRequest
from telethon import events
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google.oauth2.service_account import Credentials
import gspread
from dotenv import load_dotenv
import datetime
import pytz
import io
from PIL import Image
import pytesseract
import hashlib
import re

load_dotenv()

summary_schedule = os.getenv("SUMMARY_SCHEDULE", "daily").lower()
summaries_enabled = os.getenv("SUMMARY_ENABLED", "false").lower() == "true"
scheduler = AsyncIOScheduler()


def question_signature(text: str) -> str:
    """Return a normalized hash for the given question text."""
    normalized = re.sub(r"\W+", "", text.lower())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def load_existing_signatures(sheet_url):
    """Return a set of signatures already stored in the sheet."""
    creds_path = os.getenv("GOOGLE_CREDENTIALS")
    creds = Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(sheet_url)
    worksheet = sh.sheet1
    try:
        values = worksheet.get_all_values()
    except Exception as exc:  # pragma: no cover - network issues
        logging.exception("Failed to fetch existing rows: %s", exc)
        return set()
    signatures = set()
    for row in values:
        if len(row) >= 8 and row[7]:
            signatures.add(row[7])
    return signatures


def dedupe_rows(rows, existing_signatures):
    """Remove rows with duplicate questions and append their signature."""
    deduped = []
    seen = set()
    for row in rows:
        sig = question_signature(row[4])
        if sig in existing_signatures or sig in seen:
            continue
        seen.add(sig)
        row.append(sig)
        deduped.append(row)
    return deduped


def count_questions_in_range(sheet_url, start, end):
    """Return the number of questions between the given dates inclusive."""
    creds_path = os.getenv("GOOGLE_CREDENTIALS")
    creds = Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(sheet_url)
    worksheet = sh.sheet1
    try:
        values = worksheet.get_all_values()
    except Exception as exc:  # pragma: no cover - network issues
        logging.exception("Failed to fetch rows for summary: %s", exc)
        return 0
    count = 0
    for row in values:
        if len(row) >= 2:
            try:
                row_date = datetime.datetime.strptime(row[1], "%Y-%m-%d").date()
            except ValueError:
                continue
            if start <= row_date <= end:
                count += 1
    return count


async def send_summary(client, channel_username, sheet_url):
    today = datetime.date.today()
    if summary_schedule == "weekly":
        start = today - datetime.timedelta(days=7)
        period = "last 7 days"
    else:
        start = today
        period = "today"
    count = count_questions_in_range(sheet_url, start, today)
    message = f"Summary for {period}: {count} question(s). Sheet: {sheet_url}"
    await client.send_message(channel_username, message)


def schedule_summary_jobs(client, channel_username, sheet_url):
    scheduler.remove_all_jobs()
    if summary_schedule == "weekly":
        scheduler.add_job(
            send_summary,
            "cron",
            day_of_week="sun",
            hour=0,
            args=[client, channel_username, sheet_url],
        )
    else:
        scheduler.add_job(
            send_summary,
            "cron",
            hour=0,
            args=[client, channel_username, sheet_url],
        )


def validate_config():
    """Ensure all required environment variables exist."""
    required = [
        "API_ID",
        "API_HASH",
        "BOT_TOKEN",
        "CHANNEL_USERNAME",
        "SHEET_URL",
        "GOOGLE_CREDENTIALS",
    ]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        logging.error("Missing required environment variables: %s", ", ".join(missing))
        raise SystemExit(1)
    config = {var: os.getenv(var) for var in required}
    config["API_ID"] = int(config["API_ID"])
    return config


def create_client(config):
    return TelegramClient("bot", config["API_ID"], config["API_HASH"]).start(
        bot_token=config["BOT_TOKEN"]
    )


def register_command_handlers(client, channel_username, sheet_url):
    @client.on(events.NewMessage(pattern=r"/summaries(?:\s+(on|off))?"))
    async def _(event):
        global summaries_enabled
        arg = event.pattern_match.group(1)
        if arg == "on":
            summaries_enabled = True
            schedule_summary_jobs(client, channel_username, sheet_url)
            scheduler.start()
            await event.respond("Summaries enabled")
        elif arg == "off":
            summaries_enabled = False
            scheduler.remove_all_jobs()
            await event.respond("Summaries disabled")
        else:
            state = "enabled" if summaries_enabled else "disabled"
            await event.respond(f"Summaries are currently {state}.")

def is_question(text):
    if not text:
        return False
    keywords = [
        "؟",
        "?",
        "جاني سؤال",
        "جاءني",
        "Question",
        "اختر",
        "ما هو",
        "which",
        "what",
        "A.",
        "B.",
        "C.",
        "D."
    ]
    return any(keyword.lower() in text.lower() for keyword in keywords)


async def ocr_if_image(message):
    """Extract text from an image message using Tesseract."""
    media = None
    if getattr(message, "photo", None):
        media = message.photo
    elif getattr(message, "document", None) and getattr(message.document, "mime_type", "").startswith("image/"):
        media = message.document
    if not media:
        return None
    try:
        data = await message.download_media(bytes)
        if not data:
            return None
        img = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as exc:
        logging.exception("OCR failed for message %s: %s", message.id, exc)
        return None

def write_to_sheet(rows, sheet_url):
    creds_path = os.getenv("GOOGLE_CREDENTIALS")
    creds = Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(sheet_url)
    worksheet = sh.sheet1
    for row in rows:
        worksheet.append_row(row, value_input_option="RAW")

async def collect_questions(client, channel_username, sheet_url):
    await client.connect()
    entity = await client.get_entity(channel_username)

    existing_signatures = load_existing_signatures(sheet_url)

    offset_id = 0
    questions = []
    today = datetime.date.today()

    while True:
        history = await client(
            GetHistoryRequest(
                peer=entity,
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=100,
                max_id=0,
                min_id=0,
                hash=0,
            )
        )
        if not history.messages:
            break
        for msg in history.messages:
            post_date = msg.date.date()
            if post_date < datetime.date(2025, 1, 1):
                continue
            if post_date > today:
                continue

            # Check the main message for text or images
            for text_candidate in [msg.message] if msg.message else []:
                if is_question(text_candidate):
                    questions.append([
                        str(datetime.datetime.now(pytz.utc)),
                        str(post_date),
                        str(msg.id),
                        str(getattr(msg, "sender_id", "")),
                        text_candidate,
                        "No",
                        "",
                    ])
            ocr_text = await ocr_if_image(msg)
            if ocr_text and is_question(ocr_text):
                questions.append([
                    str(datetime.datetime.now(pytz.utc)),
                    str(post_date),
                    str(msg.id),
                    str(getattr(msg, "sender_id", "")),
                    ocr_text,
                    "No",
                    "",
                ])

            replies = await client(
                GetRepliesRequest(
                    peer=entity,
                    msg_id=msg.id,
                    offset_id=0,
                    offset_date=None,
                    add_offset=0,
                    limit=100,
                    max_id=0,
                    min_id=0,
                    hash=0,
                )
            )
            for reply in replies.messages:
                if reply.message and is_question(reply.message):
                    questions.append([
                        str(datetime.datetime.now(pytz.utc)),
                        str(post_date),
                        str(msg.id),
                        str(reply.sender_id),
                        reply.message,
                        "No",
                        "",
                    ])
                ocr_r = await ocr_if_image(reply)
                if ocr_r and is_question(ocr_r):
                    questions.append([
                        str(datetime.datetime.now(pytz.utc)),
                        str(post_date),
                        str(msg.id),
                        str(reply.sender_id),
                        ocr_r,
                        "No",
                        "",
                    ])
        offset_id = history.messages[-1].id

    if questions:
        rows_to_write = dedupe_rows(questions, existing_signatures)
        if rows_to_write:
            write_to_sheet(rows_to_write, sheet_url)


def main():
    config = validate_config()
    client = create_client(config)
    register_command_handlers(client, config["CHANNEL_USERNAME"], config["SHEET_URL"])
    if summaries_enabled:
        schedule_summary_jobs(client, config["CHANNEL_USERNAME"], config["SHEET_URL"])
    with client:
        scheduler.start()
        client.loop.run_until_complete(
            collect_questions(client, config["CHANNEL_USERNAME"], config["SHEET_URL"])
        )
        client.run_until_disconnected()


if __name__ == "__main__":
    main()
