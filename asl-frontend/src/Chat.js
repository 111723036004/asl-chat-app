import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from './AuthContext';
import { useTheme } from './ThemeContext';
import MiniPlayer from './MiniPlayer';
import EmojiBoard from './EmojiBoard';
import { API_URL, WS_URL } from './config';
import axios from 'axios';
import './App.css';

const Chat = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const [recentChats, setRecentChats] = useState([]);
  const [activeContact, setActiveContact] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [searchPhone, setSearchPhone] = useState("");
  
  const [playQueue, setPlayQueue] = useState([]);
  const [currentVideoIndex, setCurrentVideoIndex] = useState(-1);
  const [isPlayerOpen, setIsPlayerOpen] = useState(false);
  const [showEmojiBoard, setShowEmojiBoard] = useState(false);
  
  const [isTyping, setIsTyping] = useState(false);
  const typingTimeoutRef = useRef(null);

  const socketRef = useRef(null);
  const chatEndRef = useRef(null);

  const fetchRecents = useCallback(async () => {
    try {
      const res = await axios.get(`${API_URL}/recents/${user.phone}`);
      setRecentChats(res.data);
    } catch (err) { 
      console.error("Error fetching recents:", err); 
    }
  }, [user.phone]);

  useEffect(() => {
    fetchRecents();
  }, [fetchRecents]);

  useEffect(() => {
    socketRef.current = new WebSocket(`${WS_URL}/ws/${user.phone}`);
    
    socketRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'typing') {
        if (activeContact && data.sender === activeContact.phone) {
          setIsTyping(true);
          if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
          typingTimeoutRef.current = setTimeout(() => setIsTyping(false), 2000);
        }
        return;
      }

      if (data.type === 'message') {
        setIsTyping(false);
        if (data.sender !== user.phone) fetchRecents();
        
        const isFromActiveContact = activeContact && (data.sender === activeContact.phone);
        if (isFromActiveContact) {
          setMessages(prev => [...prev, { 
              sender: data.sender, text: data.text, isMe: false 
          }]);
        }
      }
    };
    
    return () => {
        if (socketRef.current) socketRef.current.close();
    };
  }, [user.phone, activeContact, fetchRecents]);

  const handleSearch = async () => {
    if (!searchPhone.trim()) return;
    try {
      const res = await axios.get(`${API_URL}/search/${searchPhone}`);
      const found = res.data;
      const exists = recentChats.find(c => c.phone === found.phone);
      if (!exists) setRecentChats(prev => [found, ...prev]);
      handleContactSelect(found);
      setSearchPhone("");
    } catch (err) { 
      alert("User not found"); 
    }
  };

  const handleContactSelect = async (contact) => {
    setActiveContact(contact);
    setIsTyping(false);
    try {
      const res = await axios.get(`${API_URL}/messages/${user.phone}/${contact.phone}`);
      setMessages(res.data.map(m => ({...m, isMe: m.sender === user.phone})));
    } catch (err) { 
      console.error("Error loading messages:", err); 
    }
  };

  useEffect(() => { 
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); 
  }, [messages, isTyping]);

  useEffect(() => {
    if (activeContact) {
      setTimeout(() => { 
        chatEndRef.current?.scrollIntoView({ behavior: "auto" }); 
      }, 100);
    }
  }, [activeContact]);

  const handleTyping = (e) => {
    setInputText(e.target.value);
    if (activeContact && socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({
            type: 'typing',
            receiver: activeContact.phone
        }));
    }
  };

  const handleEmojiSelect = (emoji, word) => {
    const combined = `${emoji} ${word}`;
    setInputText(prev => prev + (prev ? " " : "") + combined);
  };

  const sendMessage = () => {
    if (!inputText.trim() || !activeContact) return;
    const textToSend = inputText;
    setInputText("");
    setShowEmojiBoard(false);

    setMessages(prev => [...prev, { sender: user.phone, text: textToSend, isMe: true }]);
    
    if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ 
            type: 'message',
            receiver: activeContact.phone, 
            text: textToSend 
        }));
    }
  };

  // --- UPDATED TRANSLATION CALL ---
  const playTranslation = async (text) => {
    // 1. Filter out emojis before sending to backend
    const cleanText = text.replace(/([\u2700-\u27BF]|[\uE000-\uF8FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|[\u2011-\u26FF]|\uD83E[\uDD10-\uDDFF])/g, '').trim();
    
    if (!cleanText) {
        alert("No translatable text found.");
        return;
    }

    try {
      // Use encodeURIComponent to handle spaces and special characters
      const res = await axios.get(`${API_URL}/translate?text=${encodeURIComponent(cleanText)}`);
      const seq = res.data.sequence.filter(i => i.type === 'video').map(i => i.url);
      if (seq.length > 0) {
        setPlayQueue(seq); 
        setCurrentVideoIndex(0); 
        setIsPlayerOpen(true);
      } else { 
        alert("No video translation available for: " + cleanText); 
      }
    } catch (err) { 
      console.error("Translation error:", err); 
    }
  };

  const getColorFromName = (name) => {
    const colors = ['#ef4444', '#f97316', '#f59e0b', '#10b981', '#3b82f6', '#6366f1', '#8b5cf6', '#ec4899'];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return colors[Math.abs(hash) % colors.length];
  };

  return (
    <div className="app-layout">
      <div className="sidebar">
        <div className="sidebar-header">
          <div className="user-info">
             <div className="avatar" style={{background: getColorFromName(user.username)}}></div>
             <div>
                <h3 style={{margin:0}}>{user.username}</h3>
                <span style={{fontSize:'0.8rem', opacity:0.7}}>{user.phone}</span>
             </div>
          </div>
          <div style={{display:'flex', gap: '8px'}}>
            <button onClick={toggleTheme} className="icon-btn-small" title="Toggle Theme">
                {theme === 'light' ? '🌙' : '☀️'}
            </button>
          </div>
        </div>

        <div className="search-container">
            <input 
                className="modern-input" 
                type="tel" 
                placeholder="Search Phone #..." 
                value={searchPhone} 
                onChange={e => setSearchPhone(e.target.value)} 
                onKeyPress={e => e.key === 'Enter' && handleSearch()} 
            />
        </div>

        <div className="contact-list">
          {recentChats.map(contact => (
             <div key={contact.phone} className={`contact-card ${activeContact?.phone === contact.phone ? 'active' : ''}`} onClick={() => handleContactSelect(contact)}>
               <div className="avatar" style={{background: getColorFromName(contact.username)}}></div>
               <div>
                 <div style={{fontWeight: 600}}>{contact.username}</div>
                 <div className="user-role" style={{fontSize: '0.85rem', opacity: 0.7}}>{contact.role}</div>
               </div>
             </div>
          ))}
        </div>
        
        <div style={{padding: '15px', borderTop: '1px solid var(--border-color)'}}>
            <button onClick={logout} className="logout-full-btn">Sign Out</button>
        </div>
      </div>

      <div className="chat-area">
        {activeContact ? (
            <>
                <div className="chat-header">
                    <div style={{display:'flex', alignItems:'center', gap:'10px'}}>
                        <div className="avatar" style={{width:'35px', height:'35px', background: getColorFromName(activeContact.username)}}></div>
                        <div>
                            <h2 style={{margin:0, fontSize:'1.1rem'}}>{activeContact.username}</h2>
                            <span style={{fontSize:'0.8rem', opacity: 0.7}}>
                                {isTyping ? <span style={{color:'var(--accent-color)', fontWeight:'bold'}}>typing...</span> : `+1 ${activeContact.phone}`}
                            </span>
                        </div>
                    </div>
                </div>

                <div className="chat-messages">
                    {messages.map((msg, index) => (
                      <div key={index} className={`message ${msg.isMe ? 'me' : 'them'}`}>
                        <div className="message-meta">
                          <span>{msg.text}</span>
                          {user.role === 'deaf' && !msg.isMe && (
                             <button className="play-icon" onClick={() => playTranslation(msg.text)}>▶</button>
                          )}
                        </div>
                      </div>
                    ))}
                    {isTyping && (
                        <div className="message them typing-bubble">
                            <span className="dot"></span><span className="dot"></span><span className="dot"></span>
                        </div>
                    )}
                    <div ref={chatEndRef} />
                </div>

                {showEmojiBoard && <EmojiBoard onSelect={handleEmojiSelect} />}

                <div className="input-section">
                    <button className="icon-btn" onClick={() => setShowEmojiBoard(!showEmojiBoard)}>
                        {showEmojiBoard ? '⌨️' : '🧩'}
                    </button>
                    <input 
                      className="modern-input"
                      value={inputText}
                      onChange={handleTyping}
                      onKeyPress={e => e.key === 'Enter' && sendMessage()}
                      placeholder="Type your message..."
                    />
                    <button className="send-btn" onClick={sendMessage}>Send</button>
                </div>
            </>
        ) : (
            <div style={{display:'flex', flex:1, alignItems:'center', justifyContent:'center', color:'var(--text-secondary)'}}>
                <div style={{textAlign:'center'}}>
                    <div style={{fontSize:'4rem', marginBottom:'20px'}}>👋</div>
                    <h2>Welcome back, {user.username}</h2>
                </div>
            </div>
        )}

        {isPlayerOpen && playQueue.length > 0 && (
          <MiniPlayer 
            src={currentVideoIndex >= 0 ? playQueue[currentVideoIndex] : playQueue[playQueue.length - 1]} 
            onEnded={currentVideoIndex >= 0 && currentVideoIndex < playQueue.length - 1 ? () => setCurrentVideoIndex(p => p+1) : null}
            onClose={() => { setIsPlayerOpen(false); setPlayQueue([]); setCurrentVideoIndex(-1); }}
            onReplay={() => setCurrentVideoIndex(0)}
          />
        )}
      </div>
    </div>
  );
};

export default Chat;