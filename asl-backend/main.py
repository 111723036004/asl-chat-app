import os
import sqlite3
import json
import requests
import logging
import sys
from bs4 import BeautifulSoup
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import spacy

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

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

# Load Spacy
try:
    nlp = spacy.load("en_core_web_sm")
    logger.info("Spacy model loaded successfully.")
except:
    logger.warning("Spacy model not found. Downloading...")
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

DB_NAME = "chat_app_v2.db"

# --- PRODUCTION CACHE (Standard Practice) ---
# Prevents IP blocking for words that are requested frequently.
COMMON_WORD_CACHE = {
    "hello": "https://media.signbsl.com/videos/gn/mp4/hello.mp4",
    "hi": "https://media.signbsl.com/videos/gn/mp4/hello.mp4",
    "goodbye": "https://media.signbsl.com/videos/gn/mp4/goodbye.mp4",
    "bye": "https://media.signbsl.com/videos/gn/mp4/goodbye.mp4",
    "thank": "https://media.signbsl.com/videos/gn/mp4/thankyou.mp4",
    "you": "https://media.signbsl.com/videos/gn/mp4/you.mp4",
    "yes": "https://media.signbsl.com/videos/gn/mp4/yes.mp4",
    "no": "https://media.signbsl.com/videos/gn/mp4/no.mp4",
    "please": "https://media.signbsl.com/videos/gn/mp4/please.mp4",
    "help": "https://media.signbsl.com/videos/gn/mp4/help.mp4"
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

# --- MODELS & ROUTES ---
class UserRegister(BaseModel):
    username: str
    phone: str
    password: str
    role: str

class UserLogin(BaseModel):
    phone: str
    password: str

@app.post("/register")
def register(user: UserRegister):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (user.username, user.phone, user.password, user.role))
        conn.commit()
        logger.info(f"User registered: {user.username}")
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

# --- ENHANCED SCRAPER LOGIC ---
def get_video_url(word):
    clean_word = word.lower().strip()
    
    # 1. CHECK CACHE FIRST (Performance & Safety)
    if clean_word in COMMON_WORD_CACHE:
        logger.info(f"✅ Found cached video for: {clean_word}")
        return COMMON_WORD_CACHE[clean_word]

    logger.info(f"📽️ Scraping video for: '{clean_word}'")
    
    # 2. MIMIC REAL BROWSER (Stealth Mode)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document"
    }

    search_url = f"https://www.signasl.org/sign/{clean_word}"
    
    try:
        # Use a Session to handle cookies automatically
        session = requests.Session()
        response = session.get(search_url, headers=headers, timeout=10)
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # DEBUG: Log the page title to see if we are blocked
        page_title = soup.title.string if soup.title else "No Title"
        logger.info(f"📄 Page Title received: {page_title}")

        videos = soup.find_all('video')
        if not videos:
            logger.warning(f"⚠️ No video tags found for {clean_word}. Content length: {len(response.content)}")
            return None

        for vid in videos:
            # Check source children
            source = vid.find('source')
            if source and source.get('src'):
                url = source['src']
                if url.startswith("http") and ".mp4" in url:
                    return url
            
            # Check src attribute
            if vid.get('src'):
                url = vid['src']
                if url.startswith("http") and ".mp4" in url:
                    return url
                    
    except Exception as e:
        logger.error(f"❌ Scraper Error for {clean_word}: {e}")
        return None
    
    return None

@app.get("/translate")
def translate(text: str):
    logger.info(f"🗣️ Translation request: '{text}'")
    seq = []
    doc = nlp(text)
    for token in doc:
        if token.is_punct or token.is_space: continue
        word = token.lemma_.lower()
        url = get_video_url(word)
        
        if url: 
            seq.append({"type": "video", "word": word, "url": url})
        else: 
            seq.append({"type": "spelling", "word": word})
            
    return {"sequence": seq}

# --- WEBSOCKETS ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, phone: str):
        await websocket.accept()
        self.active_connections[phone] = websocket
        logger.info(f"WebSocket connected: {phone}")

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