import React, { useState } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';
import { useTheme } from './ThemeContext';
import { useNavigate } from 'react-router-dom';
import './App.css';
import { API_URL } from './config';

const Login = () => {
  const [isSignup, setIsSignup] = useState(false);
  const [formData, setFormData] = useState({ username: '', phone: '', password: '', role: 'hearing' });
  const { login } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    const url = isSignup ? `${API_URL}/register` : `${API_URL}/login`;
    try {
      const res = await axios.post(url, formData);
      if (!isSignup) { login(res.data); navigate('/chat'); } 
      else { alert("Success! Login now."); setIsSignup(false); }
    } catch (err) { alert(err.response?.data?.detail || "Error"); }
  };

  return (
    <div style={{height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--bg-app)', color: 'var(--text-primary)'}}>
      <div style={{backgroundColor: 'var(--bg-panel)', padding: '40px', borderRadius: '24px', width: '380px', boxShadow: 'var(--shadow)', border: '1px solid var(--border-color)', textAlign: 'center'}}>
        <div style={{marginBottom: '20px', display:'flex', justifyContent:'space-between'}}>
            <h2 style={{margin:0, color:'var(--accent-color)'}}>Hapto</h2>
            <button onClick={toggleTheme} className="theme-toggle">{theme === 'light' ? '🌙' : '☀️'}</button>
        </div>
        <h3 style={{marginBottom: '30px', fontWeight:'normal', color: 'var(--text-secondary)'}}>{isSignup ? "Create Account" : "Sign In"}</h3>
        <form onSubmit={handleSubmit} style={{display: 'flex', flexDirection: 'column', gap: '15px'}}>
          {isSignup && <input className="modern-input" type="text" placeholder="Full Name" required onChange={e => setFormData({...formData, username: e.target.value})} />}
          <input className="modern-input" type="tel" placeholder="Phone Number" required onChange={e => setFormData({...formData, phone: e.target.value})} />
          <input className="modern-input" type="password" placeholder="Password" required onChange={e => setFormData({...formData, password: e.target.value})} />
          {isSignup && <select className="modern-input" onChange={e => setFormData({...formData, role: e.target.value})}><option value="hearing">Hearing User</option><option value="deaf">Deaf User</option></select>}
          <button type="submit" className="send-btn" style={{marginTop: '10px'}}>{isSignup ? "Create Account" : "Access App"}</button>
        </form>
        <p onClick={() => setIsSignup(!isSignup)} style={{marginTop: '25px', color: 'var(--accent-color)', cursor: 'pointer'}}>{isSignup ? "Login" : "Sign Up"}</p>
      </div>
    </div>
  );
};
export default Login;