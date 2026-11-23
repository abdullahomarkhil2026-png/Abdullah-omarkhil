import os
import sqlite3
import logging
from datetime import datetime, timezone

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# -------------------- STORE SETTINGS --------------------
# Replace these sample package names/prices with YOUR real prices.
# Until you set prices, the bot will show "Contact admin for price".
PACKAGES = [
    ("60 UC", "Contact admin for price"),
    ("325 UC", "Contact admin for price"),
    ("660 UC", "Contact admin for price"),
    ("1800 UC", "Contact admin for price"),
    ("3850 UC", "Contact admin for price"),
    ("8100 UC", "Contact admin for price"),
]

STORE_NAME = "PUBG UC Store"
PAYMENT_INSTRUCTIONS = (
    "Please contact the store admin for payment details.\n"
    "After paying, send a clear screenshot of your payment here."
)
WELCOME_TEXT = (
    "Welcome to PUBG UC Store!\n\n"
    "Choose a UC package below to place an order."
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DATABASE_PATH = os.environ.get("DATABASE_PATH", "orders.db")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "change-this-secret-12345")
WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH", "telegram-webhook")
PORT = int(os.environ.get("PORT", "10000"))

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                package TEXT NOT NULL,
                price TEXT NOT NULL,
                player_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_at TEXT NOT NULL
            )
        """)


def get_order(order_id):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton(f"{name} — {price}", callback_data=f"pkg:{i}")]
        for i, (name, price) in enumerate(PACKAGES)
    ]
    await update.message.reply_text(
        f"{WELCOME_TEXT}\n\nSelect a package:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def package_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        index = int(query.data.split(":", 1)[1])
        package, price = PACKAGES[index]
    except (ValueError, IndexError):
        await query.edit_message_text("That package is unavailable. Please use /start.")
        return

    context.user_data["package"] = package
    context.user_data["price"] = price
    context.user_data["state"] = "player_id"
    await query.message.reply_text(
        f"You selected: {package}\nPrice: {price}\n\n"
        "Please send your PUBG Player ID (数字/ID only)."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    text = (update.message.text or "").strip()

    if state == "player_id":
        if not text.isdigit() or not (6 <= len(text) <= 20):
            await update.message.reply_text(
                "Please send a valid numeric PUBG Player ID (6–20 digits)."
            )
            return
        context.user_data["player_id"] = text
        context.user_data["state"] = "payment"
        await update.message.reply_text(
            f"Order details:\n"
            f"Package: {context.user_data['package']}\n"
            f"Price: {context.user_data['price']}\n"
            f"PUBG Player ID: {text}\n\n"
            f"{PAYMENT_INSTRUCTIONS}"
        )
        return

    await update.message.reply_text(
        "To start an order, send /start and choose a UC package."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") != "payment":
        await update.message.reply_text(
            "First choose a package with /start and enter your PUBG Player ID."
        )
        return

    user = update.effective_user
    package = context.user_data["package"]
    price = context.user_data["price"]
    player_id = context.user_data["player_id"]

    with db() as conn:
        cursor = conn.execute(
            """INSERT INTO orders
               (user_id, username, package, price, player_id, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'PENDING', ?)""",
            (
                user.id, user.username or "", package, price, player_id,
                datetime.now(timezone.utc).isoformat()
            )
        )
        order_id = cursor.lastrowid

    context.user_data.clear()
    await update.message.reply_text(
        f"Your payment screenshot has been received.\n"
        f"Order number: #{order_id}\n"
        "Your order is waiting for admin verification. Please don't send payment again."
    )

    username = f"@{user.username}" if user.username else "(no username)"
    admin_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Approve", callback_data=f"approve:{order_id}"),
        InlineKeyboardButton("Reject", callback_data=f"reject:{order_id}")
    ]])
    caption = (
        f"NEW PUBG UC ORDER #{order_id}\n"
        f"Customer: {user.full_name} {username}\n"
        f"Telegram ID: {user.id}\n"
        f"Package: {package}\nPrice: {price}\n"
        f"PUBG Player ID: {player_id}\nStatus: PENDING"
    )
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=update.message.photo[-1].file_id,
        caption=caption,
        reply_markup=admin_keyboard
    )


async def admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("You are not authorized.", show_alert=True)
        return

    await query.answer()
    action, order_text = query.data.split(":", 1)
    order_id = int(order_text)
    order = get_order(order_id)

    if not order:
        await query.edit_message_caption("Order not found.")
        return
    if order["status"] != "PENDING":
        await query.answer("This order has already been processed.", show_alert=True)
        return

    new_status = "APPROVED" if action == "approve" else "REJECTED"
    with db() as conn:
        conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (new_status, order_id)
        )

    customer_message = (
        f"Good news! Your PUBG UC order #{order_id} has been approved."
        if action == "approve"
        else f"Your PUBG UC order #{order_id} was rejected. Please contact the store admin."
    )
    try:
        await context.bot.send_message(order["user_id"], customer_message)
    except Exception:
        logger.exception("Could not message customer for order %s", order_id)

    await query.edit_message_caption(
        caption=(query.message.caption or "") + f"\n\nADMIN DECISION: {new_status}"
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram user ID is: {update.effective_user.id}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Order cancelled. Send /start to begin again.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n/start - Browse UC packages\n/cancel - Cancel current order\n/myid - Show your Telegram ID"
    )


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(package_selected, pattern=r"^pkg:"))
    app.add_handler(CallbackQueryHandler(admin_decision, pattern=r"^(approve|reject):"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Render Web Service uses a webhook so it can receive Telegram updates over HTTPS.
    base_url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError("RENDER_EXTERNAL_URL is missing. Deploy this project as a Render Web Service.")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=f"{base_url}/{WEBHOOK_PATH}",
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
