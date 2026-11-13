import os
import sqlite3
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

DB_PATH = os.environ.get("DB_PATH", "data.db")
BASE_URL = os.environ.get("BASE_URL", "https://sizning-domen.uz").rstrip("/")

app = FastAPI()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            bot_token TEXT,
            admin_id TEXT,
            bot_kind TEXT,
            bot_username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

class CreateBotRequest(BaseModel):
    user_id: int
    bot_token: str
    admin_id: str
    bot_kind: str

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return "index.html topilmadi!"

@app.post("/api/create-bot")
async def create_bot(data: CreateBotRequest):
    async with httpx.AsyncClient() as client:
        # 1. Telegram tokenini tekshirish
        res = await client.get(f"https://api.telegram.org/bot{data.bot_token}/getMe")
        bot_info = res.json()
        if not bot_info.get("ok"):
            raise HTTPException(status_code=400, detail="Noto'g'ri Bot Token! BotFather'dan tekshirib qayta kiriting.")
        
        bot_username = bot_info["result"].get("username", "bot")

        # 2. Webhook ulash
        webhook_url = f"{BASE_URL}/webhook/{data.bot_token}"
        wh_res = await client.get(f"https://api.telegram.org/bot{data.bot_token}/setWebhook?url={webhook_url}")
        if not wh_res.json().get("ok"):
            raise HTTPException(status_code=400, detail="Telegramga webhook ulab bo'lmadi!")

    # 3. Bazaga saqlash
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM bots WHERE bot_token = ?", (data.bot_token,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Bu bot allaqachon ulangan!")

    cursor.execute(
        "INSERT INTO bots (user_id, bot_token, admin_id, bot_kind, bot_username) VALUES (?, ?, ?, ?, ?)",
        (data.user_id, data.bot_token, data.admin_id, data.bot_kind, bot_username)
    )
    conn.commit()
    conn.close()

    return {"status": "success", "message": f"@{bot_username} muvaffaqiyatli yaratildi va ishga tushirildi!"}

@app.get("/api/bots/{user_id}")
async def get_user_bots(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bots WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.post("/webhook/{bot_token}")
async def telegram_webhook(bot_token: str, request: Request):
    update = await request.json()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bots WHERE bot_token = ?", (bot_token,))
    bot_data = cursor.fetchone()
    conn.close()

    if not bot_data:
        return {"status": "bot not found"}

    message = update.get("message")
    if not message:
        return {"status": "ok"}

    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    bot_kind = bot_data["bot_kind"]
    admin_id = int(bot_data["admin_id"])

    async with httpx.AsyncClient() as client:
        if text.startswith("/start"):
            if bot_kind == "kino":
                msg = "🎬 **Black Hole Kino Bot**ga xush kelibsiz!\n\nKino kodini yuboring va kinoni yuklab oling."
            else:
                msg = "🎧 **Black Hole Support Bot**ga xush kelibsiz!\n\nMurojaatingizni yuboring, adminga yetkazamiz."
            await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={
                "chat_id": chat_id, "text": msg, "parse_mode": "Markdown"
            })
        else:
            if bot_kind == "kino":
                await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": f"🔍 Siz kiritgan kod: *{text}*\n🎬 Afsuski, bu kod bo'yicha kino topilmadi.",
                    "parse_mode": "Markdown"
                })
            elif bot_kind == "support":
                if chat_id != admin_id:
                    await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={
                        "chat_id": admin_id,
                        "text": f"📩 **Yangi murojaat!**\nFoydalanuvchi ID: `{chat_id}`\nXabar: {text}",
                        "parse_mode": "Markdown"
                    })
                    await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={
                        "chat_id": chat_id, "text": "✅ Murojaatingiz adminga yuborildi."
                    })

    return {"status": "ok"}
