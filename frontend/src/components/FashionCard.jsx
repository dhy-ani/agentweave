import React, { useState } from "react";
import { useSpring, animated } from "@react-spring/web";
import { useDrag } from "@use-gesture/react";

const API = "http://localhost:8001";

const FashionCard = ({ image, result, trendiness_score, future_projection, onSwipe }) => {
  const [{ x, y, rotate }, api] = useSpring(() => ({ x: 0, y: 0, rotate: 0 }));
  const [swipeDir, setSwipeDir] = useState("");

  const bind = useDrag(({ down, movement: [mx, my], direction: [dx, dy], last }) => {
    if (last && !down) {
      const absX = Math.abs(mx);
      const absY = Math.abs(my);
      let dir = "";
      if (absX > absY) dir = dx > 0 ? "right" : "left";
      else if (dy < 0) dir = "up";

      if (dir) {
        setSwipeDir(dir);
        api.start({
          x: dx * 800, y: dy * -800, rotate: dx * 25,
          config: { tension: 280, friction: 28 },
          onRest: () => {
            if (onSwipe) onSwipe(dir);
            setSwipeDir("");
            api.set({ x: 0, y: 0, rotate: 0 });
          },
        });
        return;
      }
    }
    api.start({ x: down ? mx : 0, y: down ? my : 0, rotate: mx / 12 });
  });

  const score = typeof trendiness_score === "number" ? trendiness_score : 0;
  const scoreColor = score > 70 ? "text-green-400" : score > 40 ? "text-yellow-400" : "text-red-400";

  return (
    <animated.div
      {...bind()}
      style={{ x, y, rotate, touchAction: "none", userSelect: "none" }}
      className="relative w-full max-w-xs mx-auto bg-neutral-900 border border-neutral-800 rounded-3xl overflow-hidden shadow-2xl cursor-grab active:cursor-grabbing"
    >
      {/* Image */}
      <div className="relative">
        <img
          src={`${API}/images/${image}`}
          alt="Outfit"
          className="w-full h-72 object-cover"
          draggable={false}
        />
        {/* Trendiness badge */}
        <div className="absolute top-3 right-3 bg-neutral-900/80 backdrop-blur-sm rounded-full px-3 py-1 text-xs font-semibold border border-neutral-700">
          <span className={scoreColor}>{score.toFixed(0)}%</span>
          <span className="text-neutral-400 ml-1">trend</span>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-2">
        <p className="text-sm text-neutral-200 leading-relaxed line-clamp-3">{result}</p>
        <p className="text-xs text-neutral-500 italic">{future_projection}</p>
      </div>

      {/* Swipe hint strip */}
      <div className="px-4 pb-4 flex justify-between text-xs text-neutral-600">
        <span>← pass</span>
        <span>↑ save</span>
        <span>like →</span>
      </div>

      {/* Swipe overlays */}
      {swipeDir === "right" && (
        <div className="absolute inset-0 bg-green-500/10 flex items-center justify-center">
          <span className="text-5xl font-black text-green-400 rotate-[-12deg] border-4 border-green-400 rounded-xl px-4 py-1 tracking-widest">LIKE</span>
        </div>
      )}
      {swipeDir === "left" && (
        <div className="absolute inset-0 bg-red-500/10 flex items-center justify-center">
          <span className="text-5xl font-black text-red-400 rotate-[12deg] border-4 border-red-400 rounded-xl px-4 py-1 tracking-widest">PASS</span>
        </div>
      )}
      {swipeDir === "up" && (
        <div className="absolute inset-0 bg-brand-500/10 flex items-center justify-center">
          <span className="text-3xl font-black text-brand-400 border-4 border-brand-400 rounded-xl px-4 py-2 tracking-widest">SAVED ✦</span>
        </div>
      )}
    </animated.div>
  );
};

export default FashionCard;
