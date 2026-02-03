import React, { useState, useRef, useEffect } from 'react';

const MiniPlayer = ({ src, onEnded, onClose, onReplay }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showReplay, setShowReplay] = useState(false);
  const videoRef = useRef(null);

  // SAFE PLAY HELPER (Fixes the crash)
  const attemptPlay = () => {
    const video = videoRef.current;
    if (!video) return;
    setShowReplay(false);
    
    const playPromise = video.play();
    if (playPromise !== undefined) {
      playPromise.catch((error) => {
        // We ignore AbortError because it happens when skipping tracks quickly
        if (error.name !== "AbortError") {
          console.error("Video play error:", error);
        }
      });
    }
  };

  // Play automatically when SRC changes
  useEffect(() => {
    if (videoRef.current) {
      attemptPlay();
    }
  }, [src]);

  const handleVideoEnded = () => {
    if (onEnded) {
      onEnded();
    } else {
      setShowReplay(true);
    }
  };

  const handleReplayClick = () => {
    setShowReplay(false);
    
    // 1. Reset parent index
    if (onReplay) onReplay();

    // 2. Force rewind safely after a tiny delay
    setTimeout(() => {
        if (videoRef.current) {
            videoRef.current.currentTime = 0;
            attemptPlay();
        }
    }, 50);
  };

  if (!src) return null;

  return (
    <div style={{
      position: 'fixed', bottom: '20px', right: '20px',
      width: isExpanded ? '600px' : '220px', height: isExpanded ? '400px' : '300px',
      backgroundColor: '#000', borderRadius: '15px', overflow: 'hidden',
      boxShadow: '0 10px 40px rgba(0,0,0,0.5)', zIndex: 9999,
      transition: 'all 0.3s ease', display: 'flex', flexDirection: 'column',
      border: '4px solid #008069'
    }}>
      {/* HEADER */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, padding: '10px',
        display: 'flex', justifyContent: 'flex-end', gap: '10px',
        background: 'linear-gradient(to bottom, rgba(0,0,0,0.8), transparent)', zIndex: 20
      }}>
        <button onClick={() => setIsExpanded(!isExpanded)} style={btnStyle} title="Toggle Size">
          {isExpanded ? "↙" : "↗"}
        </button>
        <button onClick={onClose} style={{...btnStyle, background: '#ef4444', borderColor: '#ef4444'}} title="Close">
          ✕
        </button>
      </div>

      {/* VIDEO */}
      <div style={{flex: 1, position: 'relative', background: 'black'}}>
        <video 
          ref={videoRef} 
          src={src} 
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          onEnded={handleVideoEnded} 
          playsInline
        />
        {/* REPLAY OVERLAY */}
        {showReplay && !onEnded && (
            <div style={{
                position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.6)'
            }}>
                <button onClick={handleReplayClick} style={replayBtnStyle}>↻ Replay</button>
            </div>
        )}
      </div>
    </div>
  );
};

// BUTTON STYLES
const btnStyle = {
  background: 'rgba(255,255,255,0.2)', color: 'white', border: '1px solid white', borderRadius: '50%',
  width: '32px', height: '32px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontSize: '1.2rem', fontWeight: 'bold', backdropFilter: 'blur(4px)'
};

const replayBtnStyle = {
    padding: '10px 20px', fontSize: '1.2rem', background: '#008069', color: 'white',
    border: 'none', borderRadius: '25px', cursor: 'pointer', fontWeight: 'bold', boxShadow: '0 4px 15px rgba(0,128,105,0.4)'
};

export default MiniPlayer;