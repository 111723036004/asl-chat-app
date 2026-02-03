import React from 'react';

const AAC_DICTIONARY = {
  '👤': 'I', '🫵': 'You', '👥': 'We', '❓': 'Who',
  '🔙': 'did', '✅': 'finished', '📅': 'yesterday', '🔜': 'will', '⏰': 'now',
  '🍽️': 'eat', '😋': 'ate', '🥤': 'drink', '🚶': 'go', '🏃': 'ran',
  '👀': 'see', '👁️': 'saw', '🛑': 'stop', '❤️': 'love', '🗣️': 'said',
  '👋': 'Hello', '👍': 'Yes', '👎': 'No', '🙏': 'Please', '🤝': 'Thanks',
  '🍗': 'chicken', '🍕': 'pizza', '🏠': 'home', '🏫': 'school', '🕐': 'time'
};

const EmojiBoard = ({ onSelect }) => {
  return (
    <div style={styles.board}>
      <div style={styles.grid}>
        {Object.entries(AAC_DICTIONARY).map(([emoji, word]) => (
          <button key={emoji} onClick={() => onSelect(emoji, word)} style={styles.button} title={word}>
            <span style={{fontSize: '2rem', lineHeight: '1'}}>{emoji}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

const styles = {
  board: {
    height: '220px', background: 'var(--bg-app)', borderTop: '1px solid var(--border-color)',
    padding: '15px', overflowY: 'auto'
  },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(55px, 1fr))', gap: '10px' },
  button: {
    background: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '12px',
    padding: '10px', display: 'flex', justifyContent: 'center', alignItems: 'center', cursor: 'pointer',
    boxShadow: '0 2px 0 var(--border-color)'
  }
};

export default EmojiBoard;