import React, { useEffect, useState } from "react";

const confettiEmojis = ["🎉", "✨", "🎊", "🥳", "🌟", "🎈"];

export default function WelcomeBanner({ name = "Teacher" }) {
  const [showConfetti, setShowConfetti] = useState(false);

  useEffect(() => {
    setShowConfetti(true);
    const timer = setTimeout(() => setShowConfetti(false), 2500);
    return () => clearTimeout(timer);
  }, [name]);

  return (
    <div
      style={{
        background: "linear-gradient(90deg, #ffecd2 0%, #fcb69f 100%)",
        borderRadius: "24px",
        boxShadow: "0 8px 32px 0 rgba(255, 107, 107, 0.18)",
        padding: "2rem",
        margin: "2rem auto",
        maxWidth: 600,
        textAlign: "center",
        position: "relative",
        overflow: "hidden",
        fontFamily: "Poppins, Baloo 2, Comic Sans MS, cursive, sans-serif",
      }}
    >
      <h1
        style={{
          fontSize: "2.5rem",
          fontWeight: 700,
          color: "#ff6b6b",
          marginBottom: "0.5rem",
          animation: "bounceIn 1s",
          display: "inline-block",
        }}
      >
        Welcome, {name}!{" "}
        <span role="img" aria-label="wave">
          👋
        </span>
      </h1>
      <p
        style={{
          fontSize: "1.3rem",
          color: "#2c3e50",
          marginBottom: 0,
          fontWeight: 500,
          letterSpacing: "0.5px",
        }}
      >
        Ready for a great day?
      </p>
      {showConfetti && (
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
            zIndex: 1,
          }}
        >
          {[...Array(18)].map((_, i) => (
            <span
              key={i}
              style={{
                position: "absolute",
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 80}%`,
                fontSize: `${Math.random() * 1.5 + 1.2}rem`,
                opacity: 0.85,
                animation: `confetti-fall 1.8s ${Math.random()}s ease-out`,
                userSelect: "none",
              }}
            >
              {
                confettiEmojis[
                  Math.floor(Math.random() * confettiEmojis.length)
                ]
              }
            </span>
          ))}
        </div>
      )}
      <style>{`
        @keyframes bounceIn {
          0% { transform: scale(0.7); opacity: 0; }
          60% { transform: scale(1.1); opacity: 1; }
          80% { transform: scale(0.95); }
          100% { transform: scale(1); }
        }
        @keyframes confetti-fall {
          0% { transform: translateY(-40px) rotate(-10deg); opacity: 0.7; }
          80% { opacity: 1; }
          100% { transform: translateY(120px) rotate(10deg); opacity: 0; }
        }
      `}</style>
    </div>
  );
}

