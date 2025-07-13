from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
import datetime
import os
from google.oauth2.service_account import Credentials
import gspread

app = FastAPI(title="Question Dashboard")

def get_sheet():
    sheet_url = os.getenv("SHEET_URL")
    creds_path = os.getenv("GOOGLE_CREDENTIALS")
    if not sheet_url or not creds_path:
        raise RuntimeError("SHEET_URL and GOOGLE_CREDENTIALS must be set")
    creds = Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_url(sheet_url)
    return sh.sheet1

TOKEN = os.getenv("DASHBOARD_TOKEN")

async def verify_token(x_token: Optional[str] = Header(None)):
    if TOKEN and x_token != TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")

class Question(BaseModel):
    text: str
    categories: Optional[List[str]] = None
    answered: Optional[bool] = False

@app.get("/questions", dependencies=[Depends(verify_token)])
def list_questions(search: Optional[str] = None):
    ws = get_sheet()
    rows = ws.get_all_values()
    result = []
    for idx, row in enumerate(rows, start=1):
        if len(row) < 5:
            continue
        q = {
            "row": idx,
            "timestamp": row[0],
            "date": row[1],
            "message_id": row[2],
            "user_id": row[3],
            "text": row[4],
            "answered": row[5] if len(row) > 5 else "",
            "answer": row[6] if len(row) > 6 else "",
            "categories": row[7].split(",") if len(row) > 7 and row[7] else [],
        }
        if search and search.lower() not in q["text"].lower():
            continue
        result.append(q)
    return result

@app.post("/questions", dependencies=[Depends(verify_token)])
def add_question(question: Question):
    ws = get_sheet()
    row = [
        str(datetime.datetime.utcnow()),  # placeholder for timestamp in UTC
        "",  # date can be filled later
        "",  # message id
        "dashboard",  # user id placeholder
        question.text,
        "Yes" if question.answered else "No",
        "",
        ",".join(question.categories or []),
    ]
    ws.append_row(row, value_input_option="RAW")
    return {"status": "added"}

@app.put("/questions/{row}", dependencies=[Depends(verify_token)])
def update_question(row: int, question: Question):
    ws = get_sheet()
    values = ws.row_values(row)
    if not values:
        raise HTTPException(status_code=404, detail="Row not found")
    while len(values) < 8:
        values.append("")
    values[4] = question.text
    values[5] = "Yes" if question.answered else "No"
    values[7] = ",".join(question.categories or [])
    ws.update(f"A{row}:H{row}", [values[:8]])
    return {"status": "updated"}
