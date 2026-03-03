# n8n Workflows

These JSON files are reference exports for the Stratum data pipeline automation.
Import them into your n8n instance via the UI.

## How to import

1. Start n8n: `docker compose --profile ingestion up -d n8n`
2. Open the n8n UI at http://localhost:5678
3. For each workflow file: Settings (top-right gear) → Import from File → select the JSON

## Workflows

| File | Schedule | Purpose |
|------|----------|---------|
| `weekly-ingestion.json` | Sunday 2:00 AM (Asia/Ho_Chi_Minh) | VN30 OHLCV + fundamentals + gold prices + FRED indicators + structure markers |
| `monthly-wgc.json` | 1st of month 3:00 AM (Asia/Ho_Chi_Minh) | WGC flows (stub, 501) + gold structure markers |
| `error-handler.json` | Triggered by other workflows on error | Sends Telegram alert with workflow name, failed node, and error message |

## Telegram setup (required for alerts)

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env.local`.
Then in n8n: Credentials → Add credential → Telegram API → paste your bot token.
The Telegram nodes reference credential name "Telegram Bot" — match this name when creating.
