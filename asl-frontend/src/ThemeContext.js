import React, { createContext, useContext, useState, useEffect } from 'react';
const ThemeContext = createContext();
export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => localStorage.getItem('app_theme') || 'light');
  useEffect(() => { document.body.setAttribute('data-theme', theme); localStorage.setItem('app_theme', theme); }, [theme]);
  const toggleTheme = () => setTheme(p => (p === 'light' ? 'dark' : 'light'));
  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>;
};
export const useTheme = () => useContext(ThemeContext);