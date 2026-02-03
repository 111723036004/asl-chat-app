import React, { createContext, useState, useContext, useEffect } from 'react';
const AuthContext = createContext(null);
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const saved = localStorage.getItem('asl_user');
    if (saved) setUser(JSON.parse(saved));
    setLoading(false);
  }, []);
  const login = (data) => { setUser(data); localStorage.setItem('asl_user', JSON.stringify(data)); };
  const logout = () => { setUser(null); localStorage.removeItem('asl_user'); };
  if (loading) return null;
  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>;
};
export const useAuth = () => useContext(AuthContext);