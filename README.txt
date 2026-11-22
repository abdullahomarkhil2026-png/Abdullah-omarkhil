# PUBG UC Store Telegram Bot

## Included
- UC package menu
- PUBG Player ID collection
- Manual payment instructions
- Payment screenshot collection
- Admin approve/reject buttons
- SQLite order records

## Before deployment
1. Open `main.py`.
2. Replace the sample package names/prices in `PACKAGES`.
3. Replace `PAYMENT_INSTRUCTIONS` with your real payment instructions.
4. Never put your Telegram bot token in this file or in GitHub.

## GitHub files
Upload `main.py` and `requirements.txt` to the root of your GitHub repository.

## Render setup
Create a **Web Service** connected to this repository.

- Runtime: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `python main.py`
- Instance: Free (for testing only)

Add these Environment Variables in Render:
- `BOT_TOKEN` = your NEW Telegram bot token from BotFather
- `ADMIN_ID` = your Telegram numeric user ID. For the first deploy, you may leave this as `0`; start the bot and send `/myid` to it. Then replace `0` with the numeric ID it replies with and redeploy.
- `WEBHOOK_SECRET` = a long random string containing only A-Z, a-z, 0-9, underscore, or hyphen
- `WEBHOOK_PATH` = a long random URL-safe string

Important: The bot can start with `ADMIN_ID=0` for initial setup. Send `/myid` to your bot, copy the numeric ID it returns, then set `ADMIN_ID` to that number in Render and redeploy. Do not accept customer orders until this is configured.

## Important limitations
- Render Free Web Services sleep after 15 minutes without inbound traffic and can take about a minute to wake.
- Free Render filesystems are ephemeral. SQLite order history and uploaded data can be lost after restart, redeploy, or sleep. Do not use this free SQLite setup for real customer payments or important order records until persistent database storage is configured.
- This bot only records payment screenshots for manual review. It does not verify payments automatically or deliver UC automatically.
- Verify every payment yourself before approving an order.
