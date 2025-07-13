import os
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest, GetRepliesRequest
from google.oauth2.service_account import Credentials
import gspread
from dotenv import load_dotenv
import datetime
import pytz

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
channel_username = os.getenv("CHANNEL_USERNAME")
sheet_url = os.getenv("SHEET_URL")

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

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

def write_to_sheet(rows):
    creds = Credentials.from_service_account_file("credentials.json", scopes=["https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(sheet_url)
    worksheet = sh.sheet1
    for row in rows:
        worksheet.append_row(row, value_input_option="RAW")

async def collect_questions():
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
        write_to_sheet(questions)
    await client.disconnect()

with client:
    client.loop.run_until_complete(collect_questions())
