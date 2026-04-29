import json
import os
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse

import telebot
from dotenv import load_dotenv
from telebot.types import (
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")  # must be https in Telegram (ngrok / hosting)
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

EVENT_TITLE = os.getenv("EVENT_TITLE", "Մեր տոնը")
EVENT_DATETIME_TEXT = os.getenv("EVENT_DATETIME_TEXT", "")
EVENT_PLACE_NAME = os.getenv("EVENT_PLACE_NAME", "")
EVENT_ADDRESS = os.getenv("EVENT_ADDRESS", "")
EVENT_MAP_URL = os.getenv("EVENT_MAP_URL", "")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Yerevan")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set. Create .env with BOT_TOKEN=... (do not commit it).")

if not WEBAPP_URL:
    # We'll still run, but /start will be helpful about next steps.
    WEBAPP_URL = ""

if ADMIN_CHAT_ID:
    try:
        ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
    except Exception:
        ADMIN_CHAT_ID = None
else:
    ADMIN_CHAT_ID = None


bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")


def _db_path() -> str:
    os.makedirs("data", exist_ok=True)
    return os.path.join("data", "bot.db")


def _db_connect():
    import sqlite3

    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _db_init() -> None:
    with _db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              user_id INTEGER PRIMARY KEY,
              chat_id INTEGER NOT NULL,
              username TEXT,
              first_name TEXT,
              last_name TEXT,
              started_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rsvps (
              user_id INTEGER PRIMARY KEY,
              status TEXT NOT NULL, -- yes|no|later
              reason TEXT,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_reason (
              user_id INTEGER PRIMARY KEY,
              chat_id INTEGER NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminder_log (
              user_id INTEGER NOT NULL,
              kind TEXT NOT NULL,
              sent_at TEXT NOT NULL,
              PRIMARY KEY (user_id, kind, sent_at)
            )
            """
        )


def _upsert_user(message: telebot.types.Message) -> None:
    u = message.from_user
    if not u:
        return
    now = datetime.now(timezone.utc).isoformat()
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO users(user_id, chat_id, username, first_name, last_name, started_at)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
              chat_id=excluded.chat_id,
              username=excluded.username,
              first_name=excluded.first_name,
              last_name=excluded.last_name
            """,
            (u.id, message.chat.id, u.username, u.first_name, u.last_name, now),
        )


def _set_rsvp(user_id: int, status: str, reason: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO rsvps(user_id, status, reason, updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
              status=excluded.status,
              reason=excluded.reason,
              updated_at=excluded.updated_at
            """,
            (user_id, status, reason, now),
        )


def _clear_pending_reason(user_id: int) -> None:
    with _db_connect() as conn:
        conn.execute("DELETE FROM pending_reason WHERE user_id=?", (user_id,))


def _set_pending_reason(user_id: int, chat_id: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO pending_reason(user_id, chat_id, created_at)
            VALUES(?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
              chat_id=excluded.chat_id,
              created_at=excluded.created_at
            """,
            (user_id, chat_id, now),
        )


def _is_pending_reason(user_id: int) -> bool:
    with _db_connect() as conn:
        row = conn.execute("SELECT 1 FROM pending_reason WHERE user_id=?", (user_id,)).fetchone()
        return bool(row)


def _event_details_text() -> str:
    parts: list[str] = [f"<b>{EVENT_TITLE}</b>"]
    if EVENT_DATETIME_TEXT:
        parts.append(f"🕒 <b>{EVENT_DATETIME_TEXT}</b>")
    if EVENT_PLACE_NAME:
        parts.append(f"🍽 <b>{EVENT_PLACE_NAME}</b>")
    if EVENT_ADDRESS:
        parts.append(f"📍 {EVENT_ADDRESS}")
    if EVENT_MAP_URL:
        parts.append(f"🗺 {EVENT_MAP_URL}")
    parts.append("")
    parts.append("Փոքրիկ նամակ Ռաֆից․")
    parts.append("«Եթե գաս՝ ես քեզ ցույց կտամ իմ ամենաթանկ գանձը՝ իմ նոր ատամիկը։ Բայց զգույշ՝ ես շատ եմ ծիծաղում»։")
    return "\n".join(parts)


def _admin_notify(text: str) -> None:
    if not ADMIN_CHAT_ID:
        return
    try:
        bot.send_message(ADMIN_CHAT_ID, text, disable_web_page_preview=True)
    except Exception as e:
        print("Failed to notify admin:", e)

def _get_users() -> list[dict]:
    with _db_connect() as conn:
        rows = conn.execute("SELECT user_id, chat_id, username, first_name, last_name FROM users").fetchall()
        return [dict(r) for r in rows]


def _get_rsvp_status(user_id: int) -> str | None:
    with _db_connect() as conn:
        row = conn.execute("SELECT status FROM rsvps WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return None
        return row["status"]


def _log_reminder(user_id: int, kind: str, sent_at: str) -> None:
    with _db_connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO reminder_log(user_id, kind, sent_at) VALUES(?,?,?)",
            (user_id, kind, sent_at),
        )


def _was_reminder_sent(user_id: int, kind: str, sent_at: str) -> bool:
    with _db_connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM reminder_log WHERE user_id=? AND kind=? AND sent_at=?",
            (user_id, kind, sent_at),
        ).fetchone()
        return bool(row)


def _tz_now():
    # Python 3.14: zoneinfo is available
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(TIMEZONE))


def _daily_unanswered_job() -> None:
    # Daily: ask everyone who hasn't made a final decision (no RSVP or "later")
    today_key = _tz_now().date().isoformat()
    kind = "daily_ask"
    users = _get_users()
    for u in users:
        status = _get_rsvp_status(u["user_id"])
        if status in {"yes", "no"}:
            continue
        if _was_reminder_sent(u["user_id"], kind, today_key):
            continue
        try:
            bot.send_message(
                u["chat_id"],
                "Փոքրիկ հիշեցում Ռաֆից․ դու դեռ չես ասել՝ կգա՞ս։ Ես արդեն ատամիկով ժպտում եմ ու սպասում եմ։",
                reply_markup=_reminder_keyboard(),
            )
            _log_reminder(u["user_id"], kind, today_key)
        except Exception as e:
            print("daily reminder failed:", u["user_id"], e)


def _weekly_fun_job() -> None:
    # Weekly: a funny reminder to everyone
    now = _tz_now()
    year, week, _ = now.isocalendar()
    week_key = f"{year}-W{week:02d}"
    kind = "weekly_fun"
    users = _get_users()
    for u in users:
        if _was_reminder_sent(u["user_id"], kind, week_key):
            continue
        try:
            bot.send_message(
                u["chat_id"],
                "Շաբաթական հիշեցում․ Ռաֆը մարզում է իր «ուրախ տոն» մկանները։ "
                "Եթե դեռ չես կողմնորոշվել՝ սեղմիր, ես կգրեմ կազմակերպիչին։",
                reply_markup=_reminder_keyboard(),
            )
            _log_reminder(u["user_id"], kind, week_key)
        except Exception as e:
            print("weekly reminder failed:", u["user_id"], e)


@bot.message_handler(commands=["start"])
def start(message: telebot.types.Message):
    _upsert_user(message)
    if not WEBAPP_URL:
        bot.reply_to(
            message,
            "Бот запущен, но пока не задана ссылка на Web App.\n\n"
            "Сделай файл <code>.env</code> и добавь туда:\n"
            "<code>WEBAPP_URL=https://....</code>\n\n"
            "Потом перезапусти бота.",
        )
        return

    # Cache-bust WebView resources (Telegram WebView can be sticky).
    # Keep it stable during one minute to avoid excessive URL changes.
    v = int(datetime.now(timezone.utc).timestamp() // 60)
    try:
        parsed = urlparse(WEBAPP_URL)
        q = parsed.query
        q = f"{q}&v={v}" if q else f"v={v}"
        webapp_url = urlunparse(parsed._replace(query=q))
    except Exception:
        sep = "&" if "?" in WEBAPP_URL else "?"
        webapp_url = f"{WEBAPP_URL}{sep}v={v}"

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            text="🎉 Открыть приглашение",
            web_app=WebAppInfo(url=webapp_url),
        )
    )

    bot.send_message(
        message.chat.id,
        "Բարև։ Սեղմիր կոճակը, որ բացես Ռաֆի հրավերը Telegram-ի ներսում։",
        reply_markup=kb,
    )


@bot.message_handler(content_types=["web_app_data"])
def web_app_data_handler(message: telebot.types.Message):
    _upsert_user(message)
    raw = message.web_app_data.data
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {"_raw": raw}

    user = message.from_user
    status = payload.get("status") or ("yes" if payload.get("coming") else None)
    reason = payload.get("reason")
    if status not in {"yes", "no", "later"}:
        bot.send_message(message.chat.id, "Չհասկացա պատասխանը։ Փորձիր նորից բացել հրավերը։")
        return

    _clear_pending_reason(user.id)
    _set_rsvp(user.id, status, reason if isinstance(reason, str) else None)

    who = f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.username or str(user.id))
    admin_text = f"RSVP: <b>{status}</b>\n👤 {who} (id={user.id}, @{user.username})"
    if status == "no" and reason:
        admin_text += f"\n📝 Պատճառ: {reason}"
    _admin_notify(admin_text)

    # Reply user with full event info + small humorous note
    bot.send_message(message.chat.id, _event_details_text(), disable_web_page_preview=True)

    if status == "yes":
        bot.send_message(message.chat.id, "Շնորհակալ եմ, սպասում ենք քեզ։")
    elif status == "no":
        bot.send_message(message.chat.id, "Լավ, կհասկանամ։ Եթե մի բան փոխվի՝ գրիր ինձ։")
    else:
        bot.send_message(message.chat.id, "Լավ, ես քեզ հետո էլ կհիշեցնեմ։")


def _reminder_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("Կգամ", callback_data="rsvp_yes"),
        InlineKeyboardButton("Չեմ գա", callback_data="rsvp_no"),
    )
    kb.row(InlineKeyboardButton("Կպատասխանեմ հետո", callback_data="rsvp_later"))
    return kb


@bot.callback_query_handler(func=lambda call: call.data in {"rsvp_yes", "rsvp_no", "rsvp_later"})
def rsvp_callback(call: telebot.types.CallbackQuery):
    user = call.from_user
    chat_id = call.message.chat.id if call.message else call.from_user.id
    _upsert_user(call.message) if call.message else None

    if call.data == "rsvp_yes":
        _clear_pending_reason(user.id)
        _set_rsvp(user.id, "yes", None)
        bot.answer_callback_query(call.id, "Գրանցեցի՝ կգաս")
        _admin_notify(f"RSVP: <b>yes</b>\n👤 {user.first_name} (id={user.id}, @{user.username})")
        bot.send_message(chat_id, _event_details_text(), disable_web_page_preview=True)
        bot.send_message(chat_id, "Շնորհակալ եմ, սպասում ենք քեզ։")
        return

    if call.data == "rsvp_later":
        _clear_pending_reason(user.id)
        _set_rsvp(user.id, "later", None)
        bot.answer_callback_query(call.id, "Լավ, հետո")
        _admin_notify(f"RSVP: <b>later</b>\n👤 {user.first_name} (id={user.id}, @{user.username})")
        bot.send_message(chat_id, "Լավ, ես դեռ կհիշեցնեմ։")
        return

    # rsvp_no -> ask reason
    _set_pending_reason(user.id, chat_id)
    bot.answer_callback_query(call.id, "Լավ, իսկ ինչո՞ւ չես գա")
    bot.send_message(
        chat_id,
        "Կարո՞ղ ես գրել կարճ պատճառը, թե ինչու չես կարող գալ։",
        reply_markup=ForceReply(selective=True),
    )


@bot.message_handler(func=lambda m: bool(m.from_user) and _is_pending_reason(m.from_user.id), content_types=["text"])
def reason_reply_handler(message: telebot.types.Message):
    _upsert_user(message)
    user = message.from_user
    reason = (message.text or "").strip()
    _clear_pending_reason(user.id)
    _set_rsvp(user.id, "no", reason or None)
    _admin_notify(
        f"RSVP: <b>no</b>\n👤 {user.first_name} (id={user.id}, @{user.username})\n📝 Պատճառ: {reason or '(չգրեց)'}"
    )
    bot.send_message(message.chat.id, "Շնորհակալ եմ։ Կփոխանցեմ կազմակերպիչին։")


if __name__ == "__main__":
    _db_init()
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from zoneinfo import ZoneInfo

        scheduler = BackgroundScheduler(timezone=ZoneInfo(TIMEZONE))
        # Daily at 11:00 local time
        scheduler.add_job(_daily_unanswered_job, CronTrigger(hour=11, minute=0), id="daily_ask")
        # Weekly on Monday at 12:00 local time
        scheduler.add_job(_weekly_fun_job, CronTrigger(day_of_week="mon", hour=12, minute=0), id="weekly_fun")
        scheduler.start()
    except Exception as e:
        print("Scheduler failed to start:", e)

    print("Bot is running...")
    bot.infinity_polling(skip_pending=True, timeout=30)
