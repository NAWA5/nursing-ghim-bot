# Nursing Ghim Bot

This bot collects questions from a Telegram channel and writes them to a Google Sheet.

Each question is tagged with zero or more **categories** (e.g. `pediatrics`, `pharmacology`) based on keywords. These tags are stored in a new column in the sheet.

## Environment Variables
Create a `.env` file containing the following keys:

- `API_ID`
- `API_HASH`
- `BOT_TOKEN`
- `SHEET_URL`
- `CHANNEL_USERNAME`
- `GOOGLE_CREDENTIALS` – path to your Google service account JSON file used to access the spreadsheet.
- `SUMMARY_ENABLED` – set to `true` to send periodic summaries (default `false`).
- `SUMMARY_SCHEDULE` – either `daily` or `weekly` (default `daily`).

## Dashboard

A simple FastAPI application is provided in `dashboard/` for browsing and editing questions stored in the spreadsheet.

### Environment Variables

Set `DASHBOARD_TOKEN` to a secret value to require the same token in the `X-Token` HTTP header.

### Running locally

```
uvicorn dashboard.app:app --reload
```

Visit `http://localhost:8000/docs` for interactive API documentation.

### Deploying

This app can be hosted on any platform that supports Python and ASGI applications (e.g. Fly.io, Render, etc.). Ensure all environment variables from the main bot and `DASHBOARD_TOKEN` are configured.
