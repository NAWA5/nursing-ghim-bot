import os
import logging
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest, GetRepliesRequest
from google.oauth2.service_account import Credentials
import gspread
from dotenv import load_dotenv
import datetime
import pytz

load_dotenv()


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

    offset_id = 0
    questions = []
    today = datetime.date.today()

    while True:
        history = await client(GetHistoryRequest(
            peer=entity,
            offset_id=offset_id,
            offset_date=None,
            add_offset=0,
            limit=100,
            max_id=0,
            min_id=0,
            hash=0
        ))
        if not history.messages:
            break
        for msg in history.messages:
            post_date = msg.date.date()
            if post_date < datetime.date(2025, 1, 1):
                continue
            if post_date > today:
                continue
            replies = await client(GetRepliesRequest(
                peer=entity,
                msg_id=msg.id,
                offset_id=0,
                offset_date=None,
                add_offset=0,
                limit=100,
                max_id=0,
                min_id=0,
                hash=0
            ))
            for reply in replies.messages:
                if is_question(reply.message):
                    questions.append([
                        str(datetime.datetime.now(pytz.utc)),
                        str(post_date),
                        str(msg.id),
                        str(reply.sender_id),
                        reply.message,
                        "No",
                        ""
                    ])
        offset_id = history.messages[-1].id

    if questions:
        write_to_sheet(questions, sheet_url)
    await client.disconnect()


def main():
    config = validate_config()
    client = create_client(config)
    with client:
        client.loop.run_until_complete(
            collect_questions(client, config["CHANNEL_USERNAME"], config["SHEET_URL"])
        )


if __name__ == "__main__":
    main()
