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
# We still keep this for safety, but we won't rely on downloading anymore
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

# Load Spacy
try:
    nlp = spacy.load("en_core_web_sm")
except:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

DB_NAME = "chat_app_v2.db"

# Headers to look like a real browser (Essential for scraping)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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

# --- ROUTES ---
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

# --- REAL SCRAPING LOGIC (HOTLINKING) ---
def get_video_url(word):
    clean_word = word.lower().strip()
    
    # Try scraping SignASL (It aggregates multiple sources)
    search_url = f"https://www.signasl.org/sign/{clean_word}"
    
    try:
        # We request the PAGE (HTML), which usually isn't blocked if we have User-Agent
        r = requests.get(search_url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(r.content, 'lxml')
        
        # Find the video tags
        # We look for the first video that is NOT from 'signingsavvy' (they have strict hotlink protection)
        videos = soup.find_all('video')
        
        for vid in videos:
            source = vid.find('source')
            if source:
                video_url = source['src']
                # Check if it's a valid mp4
                if ".mp4" in video_url:
                    # Return the EXTERNAL URL directly. 
                    # Do not download it. Let the frontend load it.
                    return video_url
                    
            # Fallback for video tags without source children
            if vid.get('src') and ".mp4" in vid.get('src'):
                return vid.get('src')

    except Exception as e:
        print(f"Scraper Error for {clean_word}: {e}")
        return None
    
    return None

@app.get("/translate")
def translate(text: str):
    seq = []
    # Force text to uppercase for spacy processing, then clean individual words
    doc = nlp(text)
    for token in doc:
        if token.is_punct or token.is_space: continue
        word = token.lemma_.lower()
        
        # Get URL
        url = get_video_url(word)
        
        if url: 
            seq.append({"type": "video", "word": word, "url": url})
        else: 
            # Fallback to spelling if no video found
            seq.append({"type": "spelling", "word": word})
            
    return {"sequence": seq}

# --- WEBSOCKETS ---
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
            msg_type = msg_data.get('type', 'message')
            receiver_phone = msg_data['receiver']
            
            if msg_type == 'typing':
                await manager.send_personal_message({
                    "type": "typing",
                    "sender": phone
                }, receiver_phone)
            
            elif msg_type == 'message':
                text = msg_data['text']
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("INSERT INTO messages (sender, receiver, text) VALUES (?, ?, ?)", 
                          (phone, receiver_phone, text))
                conn.commit()
                conn.close()
                await manager.send_personal_message({
                    "type": "message",
                    "sender": phone, 
                    "text": text
                }, receiver_phone)
    except WebSocketDisconnect:
        manager.disconnect(phone)