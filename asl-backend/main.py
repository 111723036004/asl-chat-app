import os
import sqlite3
import json
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import spacy

app = FastAPI()

# --- CONFIGURATION ---
VIDEO_DIR = "downloaded_videos"
if not os.path.exists(VIDEO_DIR):
    os.makedirs(VIDEO_DIR)

app.mount("/videos", StaticFiles(directory=VIDEO_DIR), name="videos")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

nlp = spacy.load("en_core_web_sm")
DB_NAME = "chat_app_v2.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT, phone TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, receiver TEXT, text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# --- MODELS ---
class UserRegister(BaseModel):
    username: str
    phone: str
    password: str
    role: str

class UserLogin(BaseModel):
    phone: str
    password: str

# --- AUTH ---
@app.post("/register")
def register(user: UserRegister):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user.username, user.phone, user.password, user.role))
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Phone already registered")
    finally:
        conn.close()
    return {"message": "User created"}

@app.post("/login")
def login(creds: UserLogin):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT username, role, phone FROM users WHERE phone=? AND password=?", (creds.phone, creds.password))
    row = c.fetchone()
    conn.close()
    if row:
        return {"username": row[0], "role": row[1], "phone": row[2]}
    raise HTTPException(status_code=401, detail="Invalid credentials")

# --- DATA ENDPOINTS ---
@app.get("/search/{phone}")
def search_user(phone: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT username, phone, role FROM users WHERE phone=?", (phone,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"username": row[0], "phone": row[1], "role": row[2]}
    raise HTTPException(status_code=404, detail="User not found")

@app.get("/recents/{my_phone}")
def get_recent_chats(my_phone: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    query = '''
        SELECT DISTINCT u.username, u.phone, u.role
        FROM users u
        JOIN messages m ON (u.phone = m.sender OR u.phone = m.receiver)
        WHERE (m.sender = ? OR m.receiver = ?)
        AND u.phone != ?
    '''
    c.execute(query, (my_phone, my_phone, my_phone))
    users = [{"username": r[0], "phone": r[1], "role": r[2]} for r in c.fetchall()]
    conn.close()
    return users

@app.get("/messages/{my_phone}/{other_phone}")
def get_chat_history(my_phone: str, other_phone: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''SELECT sender, text FROM messages 
                 WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)
                 ORDER BY timestamp ASC''', (my_phone, other_phone, other_phone, my_phone))
    msgs = [{"sender": r[0], "text": r[1]} for r in c.fetchall()]
    conn.close()
    return msgs

# --- TRANSLATION ---
def get_video_url(word):
    clean_word = word.upper().strip()
    filename = f"{clean_word}.mp4"
    path = os.path.join(VIDEO_DIR, filename)
    if os.path.exists(path):
        return f"http://localhost:8000/videos/{filename}"
    try:
        r = requests.get(f"https://www.signasl.org/sign/{word}")
        soup = BeautifulSoup(r.content, 'lxml')
        vid = soup.find('video')
        if vid:
            src = vid.find('source')['src']
            with open(path, 'wb') as f:
                f.write(requests.get(src).content)
            return f"http://localhost:8000/videos/{filename}"
    except:
        return None
    return None

@app.get("/translate")
def translate(text: str):
    seq = []
    doc = nlp(text.upper())
    for token in doc:
        if token.is_punct or token.is_space or not token.is_alpha: continue
        word = token.lemma_.upper()
        url = get_video_url(word)
        if url: seq.append({"type": "video", "word": word, "url": url})
        else: seq.append({"type": "spelling", "word": word})
    return {"sequence": seq}

# --- WEBSOCKETS (UPDATED FOR TYPING) ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, phone: str):
        await websocket.accept()
        self.active_connections[phone] = websocket

    def disconnect(self, phone: str):
        if phone in self.active_connections:
            del self.active_connections[phone]

    async def send_personal_message(self, message: dict, receiver_phone: str):
        if receiver_phone in self.active_connections:
            await self.active_connections[receiver_phone].send_text(json.dumps(message))

manager = ConnectionManager()

@app.websocket("/ws/{phone}")
async def websocket_endpoint(websocket: WebSocket, phone: str):
    await manager.connect(websocket, phone)
    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data) 
            
            # Check Message Type
            msg_type = msg_data.get('type', 'message') # 'message' or 'typing'
            receiver_phone = msg_data['receiver']
            
            if msg_type == 'typing':
                # Just pass the signal through, don't save to DB
                await manager.send_personal_message({
                    "type": "typing",
                    "sender": phone
                }, receiver_phone)
            
            elif msg_type == 'message':
                text = msg_data['text']
                # Save to DB
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("INSERT INTO messages (sender, receiver, text) VALUES (?, ?, ?)", 
                          (phone, receiver_phone, text))
                conn.commit()
                conn.close()

                # Send to Receiver
                await manager.send_personal_message({
                    "type": "message",
                    "sender": phone, 
                    "text": text
                }, receiver_phone)

    except WebSocketDisconnect:
        manager.disconnect(phone)