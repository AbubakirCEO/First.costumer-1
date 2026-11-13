import os
import sqlite3
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

BASE_URL = os.environ.get("BASE_URL", "https://sizning-domen.uz").rstrip("/")
PLATFORM_TOKEN = "9094748021:AAHrx5bJB6wmdXJqF9Q4pDuYv_KB15zjiCw"
DB_PATH = os.environ.get("DB_PATH", "data.db")

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            deposited INTEGER DEFAULT 0
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
    return "Frontend index.html topilmadi!"

@app.post("/api/create-bot")
async def create_bot(data: CreateBotRequest):
    async with httpx.AsyncClient() as client:
        res = await client.get(f"https://api.telegram.org/bot{data.bot_token}/getMe")
        if not res.json().get("ok"):
            raise HTTPException(status_code=400, detail="Noto'g'ri Bot Token!")

        webhook_url = f"{BASE_URL}/webhook/{data.bot_token}"
        wh_res = await client.get(f"https://api.telegram.org/bot{data.bot_token}/setWebhook?url={webhook_url}")
        if not wh_res.json().get("ok"):
            raise HTTPException(status_code=400, detail="Telegramga webhook ulab bo'lmadi!")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO bots (user_id, bot_token, admin_id, bot_kind) VALUES (?, ?, ?, ?)",
        (data.user_id, data.bot_token, data.admin_id, data.bot_kind)
    )
    conn.commit()
    conn.close()

    return {"status": "success", "message": "Bot Black Hole orqali muvaffaqiyatli ishga tushirildi!"}

@app.post("/webhook/{bot_token}")
async def telegram_webhook(bot_token: str, request: Request):
    update = await request.json()
    return {"status": "ok"}
