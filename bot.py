import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)
async def debug_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    print("CALLBACK DATA:", q.data)
    await q.answer("clicked")

# Load .env from project root (C:\tg-sub-builder\.env)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

BOT_ID = int(os.getenv("BOT_ID", "1"))
TIMEOUT = 15

# Benefits links
BENEFITS_BASIC_URL = os.getenv("BENEFITS_BASIC_URL", "").strip()
BENEFITS_VIP_URL = os.getenv("BENEFITS_VIP_URL", "").strip()

# Stars config (Stars amounts are in Stars, currency XTR)
STARS_BASIC_AMOUNT = int(os.getenv("STARS_BASIC_AMOUNT", "1000"))  # $10 ≈ 1000 stars
STARS_VIP_AMOUNT = int(os.getenv("STARS_VIP_AMOUNT", "2000"))      # $20 ≈ 2000 stars
STARS_TITLE = os.getenv("STARS_TITLE", "Exclusive Content (1 month)")
STARS_DESCRIPTION = os.getenv("STARS_DESCRIPTION", "Access for 30 days")


def _safe_get_json(resp: requests.Response):
    try:
        return resp.json(), None
    except Exception:
        return None, f"HTTP {resp.status_code} (non-JSON): {resp.text[:800]}"


def _fetch_plans():
    r = requests.get(f"{API}/api/bots/{BOT_ID}/plans", timeout=TIMEOUT)
    data, err = _safe_get_json(r)
    if err:
        raise RuntimeError(f"Failed to fetch plans: {err}")
    return data


def _fetch_status(tg_user_id: str):
    r = requests.get(
        f"{API}/api/status",
        params={"bot_id": BOT_ID, "tg_user_id": tg_user_id},
        timeout=TIMEOUT,
    )
    data, err = _safe_get_json(r)
    if err:
        raise RuntimeError(f"Failed to fetch status: {err}")
    return data


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first = user.first_name or "there"

    try:
        plans = _fetch_plans()
        status = _fetch_status(str(user.id))
    except Exception as e:
        await update.message.reply_text(
            "⚠️ Backend isn’t reachable.\n"
            "Start server:\n"
            "`uvicorn app.main:app --reload --port 8000`\n\n"
            f"Error: {e}",
            parse_mode="Markdown",
        )
        return

    is_active = bool(status.get("active"))
    status_text = "Subscribed ✅" if is_active else "Not subscribed"

    by_name = {p["name"].lower(): p for p in plans}
    basic = by_name.get("basic")
    vip = by_name.get("vip")

    lines = [
        f"👋 Welcome, {first}!",
        "",
        f"🔒 Status: {status_text}",
        "",
        "Choose a plan (tap to view benefits):",
        f"• Basic (1 month): {BENEFITS_BASIC_URL or '(set BENEFITS_BASIC_URL in .env)'}",
        f"• VIP (1 month): {BENEFITS_VIP_URL or '(set BENEFITS_VIP_URL in .env)'}",
        "",
        "🍯 You’ll get: One Month of Exclusive Content",
        "⭐ Pay with Telegram Stars or 🅿️ PayPal Subscription",
        "➡️ Buy here: /subscribe",
    ]

    buttons = []
    if basic:
        buttons.append([InlineKeyboardButton("Basic (choose payment)", callback_data=f"plan:{basic['id']}")])
    if vip:
        buttons.append([InlineKeyboardButton("VIP (choose payment)", callback_data=f"plan:{vip['id']}")])

    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        plans = _fetch_plans()
    except Exception as e:
        await update.message.reply_text(f"⚠️ Can't load plans.\nError: {e}")
        return

    by_name = {p["name"].lower(): p for p in plans}
    basic = by_name.get("basic")
    vip = by_name.get("vip")

    buttons = []
    if basic:
        buttons.append([InlineKeyboardButton("Basic (choose payment)", callback_data=f"plan:{basic['id']}")])
    if vip:
        buttons.append([InlineKeyboardButton("VIP (choose payment)", callback_data=f"plan:{vip['id']}")])

    await update.message.reply_text("Select a plan:", reply_markup=InlineKeyboardMarkup(buttons))


async def plan_clicked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_id = int(query.data.split(":")[1])
    context.user_data["pending_plan_id"] = plan_id

    buttons = [
        [InlineKeyboardButton("⭐ Pay with Telegram Stars", callback_data="pay:stars")],
        [InlineKeyboardButton("🅿️ Pay with PayPal Subscription", callback_data="pay:paypal")],
    ]
    await query.message.reply_text("Choose a payment method:", reply_markup=InlineKeyboardMarkup(buttons))


async def pay_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_id = context.user_data.get("pending_plan_id")
    if not plan_id:
        await query.message.reply_text("⚠️ No plan selected. Use /subscribe.")
        return

    plans = _fetch_plans()
    plan = next((p for p in plans if p["id"] == plan_id), None)
    if not plan:
        await query.message.reply_text("⚠️ Plan not found. Use /subscribe again.")
        return

    plan_name = (plan.get("name") or "").lower()
    stars_amount = STARS_VIP_AMOUNT if plan_name == "vip" else STARS_BASIC_AMOUNT

    payload = f"stars:{BOT_ID}:{plan_id}:{query.from_user.id}"

    # Stars invoices use currency XTR (Telegram Stars). Provider token can be "".
    await context.bot.send_invoice(
        chat_id=query.from_user.id,
        title=STARS_TITLE,
        description=STARS_DESCRIPTION,
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=plan["name"], amount=stars_amount)],
        
    )


async def pay_paypal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_id = context.user_data.get("pending_plan_id")
    if not plan_id:
        await query.message.reply_text("⚠️ No plan selected. Use /subscribe.")
        return

    payload = {
        "bot_id": BOT_ID,
        "plan_id": plan_id,
        "tg_user_id": str(query.from_user.id),
        "tg_username": query.from_user.username or "",
    }

    r = requests.post(f"{API}/api/paypal/create-subscription", json=payload, timeout=TIMEOUT)
    data, err = _safe_get_json(r)
    if err:
        await query.message.reply_text(f"⚠️ PayPal error:\n{err}")
        return

    approve_url = data.get("approve_url")
    if not approve_url:
        await query.message.reply_text(f"⚠️ Missing approve_url.\nResponse: {data}")
        return

    await query.message.reply_text(f"🅿️ Complete PayPal subscription here:\n{approve_url}")


async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Telegram requires you to answer pre-checkout queries
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sp = update.message.successful_payment
    payload = sp.invoice_payload or ""

    # payload format: stars:BOT_ID:plan_id:tg_user_id
    try:
        kind, bot_id_s, plan_id_s, tg_user_id_s = payload.split(":")
        if kind != "stars":
            return
        bot_id = int(bot_id_s)
        plan_id = int(plan_id_s)
        tg_user_id = str(tg_user_id_s)
    except Exception:
        await update.message.reply_text("✅ Payment received, but payload parse failed.")
        return

    activate_payload = {
        "bot_id": bot_id,
        "plan_id": plan_id,
        "tg_user_id": tg_user_id,
        "provider": "stars",
        "provider_ref": sp.telegram_payment_charge_id,
    }

    r = requests.post(f"{API}/api/activate", json=activate_payload, timeout=TIMEOUT)
    if r.status_code >= 400:
        await update.message.reply_text("✅ Payment received, but activation failed. Check server logs.")
        return

    await update.message.reply_text("✅ Payment received! Subscription activated.")


def main():
    if not TOKEN or "PASTE_YOUR_TOKEN_HERE" in TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing/placeholder. Fix .env and restart.")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))

    app.add_handler(CallbackQueryHandler(plan_clicked, pattern=r"^plan:\d+$"))
    app.add_handler(CallbackQueryHandler(pay_stars, pattern=r"^pay:stars$"))
    app.add_handler(CallbackQueryHandler(pay_paypal, pattern=r"^pay:paypal$"))
    app.add_handler(CallbackQueryHandler(debug_callbacks))



    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    app.run_polling()


if __name__ == "__main__":
    main()
