import os
import sqlite3
import json
import requests
import logging
import sys
from bs4 import BeautifulSoup
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import spacy

# --- LOGGING ---
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
# REPLACE WITH YOUR ACTUAL RENDER URL
BASE_URL = "https://hapto-bakcend.onrender.com" 

# --- EXPANDED CACHE (Direct MP4 Links) ---
# We will wrap these in the proxy automatically later
RAW_CACHE = {
    # Demo Sentence: "What are you doing?"
    "what": "https://media.signbsl.com/videos/gn/mp4/what.mp4",
    "be": "https://media.signbsl.com/videos/gn/mp4/be.mp4",    # Covers "are"
    "you": "https://media.signbsl.com/videos/gn/mp4/you.mp4",
    "do": "https://media.signbsl.com/videos/gn/mp4/do.mp4",     # Covers "doing"

    # Common Greetings
    "hello": "https://media.signbsl.com/videos/gn/mp4/hello.mp4",
    "hi": "https://media.signbsl.com/videos/gn/mp4/hello.mp4",
    "goodbye": "https://media.signbsl.com/videos/gn/mp4/goodbye.mp4",
    "bye": "https://media.signbsl.com/videos/gn/mp4/goodbye.mp4",
    "thank": "https://media.signbsl.com/videos/gn/mp4/thankyou.mp4",
    "please": "https://media.signbsl.com/videos/gn/mp4/please.mp4",
    "yes": "https://media.signbsl.com/videos/gn/mp4/yes.mp4",
    "no": "https://media.signbsl.com/videos/gn/mp4/no.mp4",
    "help": "https://media.signbsl.com/videos/gn/mp4/help.mp4",
    "name": "https://media.signbsl.com/videos/gn/mp4/name.mp4",
    "good": "https://media.signbsl.com/videos/gn/mp4/good.mp4"
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

# --- NEW PROXY ENDPOINT (Fixes Black Screen) ---
@app.get("/video-proxy")
def video_proxy(url: str):
    """
    Fetches the video server-side to bypass CORS blocks.
    The frontend plays THIS endpoint, not the external URL.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # Stream the video content
        r = requests.get(url, headers=headers, stream=True, timeout=10)
        return StreamingResponse(r.iter_content(chunk_size=1024 * 1024), media_type="video/mp4")
    except Exception as e:
        logger.error(f"Proxy failed for {url}: {e}")
        raise HTTPException(status_code=404, detail="Video not found")

# --- STANDARD AUTH ROUTES ---
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

# --- VIDEO LOOKUP LOGIC ---
def get_video_url(word):
    clean_word = word.lower().strip()
    
    # 1. CHECK CACHE + WRAP IN PROXY
    if clean_word in RAW_CACHE:
        real_url = RAW_CACHE[clean_word]
        # Return the PROXY URL so the frontend plays it from our server
        return f"{BASE_URL}/video-proxy?url={real_url}"

    logger.info(f"📽️ Scraping video for: '{clean_word}'")
    
    # 2. ATTEMPT SCRAPE (Fallback)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.google.com/"
    }
    search_url = f"https://www.signasl.org/sign/{clean_word}"
    
    try:
        session = requests.Session()
        response = session.get(search_url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        if soup.title:
            logger.info(f"📄 Page Title: {soup.title.string}")

        videos = soup.find_all('video')
        for vid in videos:
            source = vid.find('source')
            if source and source.get('src') and ".mp4" in source['src']:
                # Wrap scraped URL in proxy too
                return f"{BASE_URL}/video-proxy?url={source['src']}"
            if vid.get('src') and ".mp4" in vid.get('src'):
                return f"{BASE_URL}/video-proxy?url={vid['src']}"
                    
    except Exception as e:
        logger.error(f"❌ Scraper Error: {e}")
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