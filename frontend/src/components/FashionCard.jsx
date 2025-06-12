import React, { useState } from "react";
import { useSpring, animated } from "@react-spring/web";
import { useDrag } from "@use-gesture/react";

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
          x: dx * 1000,
          y: dy * -1000,
          rotate: dx * 30,
          config: { tension: 300, friction: 30 },
          onRest: () => {
            if (onSwipe) onSwipe(dir);
            setSwipeDir("");
            api.set({ x: 0, y: 0, rotate: 0 });
          }
        });
        return;
      }
    }

    api.start({ x: down ? mx : 0, y: down ? my : 0, rotate: mx / 10 });
  });

  return (
    <animated.div
      {...bind()}
      className="relative p-4"
      style={{
        x,
        y,
        rotate,
        touchAction: "none",
        width: 320,
        background: "white",
        borderRadius: 20,
        boxShadow: "0 15px 30px rgba(0,0,0,0.2)",
        overflow: "hidden",
        userSelect: "none"
      }}
    >
      {/* Image */}
      <img
        src={`http://localhost:8001/images/${image}`}
        alt="Outfit"
        className="block mx-auto w-full h-[75%] object-cover rounded-t-lg"
      />

      {/* Text Content */}
      <div className="p-4 text-center">
        <h2 className="text-lg font-bold">🌟 {result}</h2>
        <p><strong>Trendiness:</strong> {trendiness_score.toFixed(1)}%</p>
        <p className="italic text-gray-600">{future_projection}</p>
      </div>

      {/* Tinder-like Reaction Overlays */}
      {swipeDir === "right" && (
        <div className="absolute top-10 left-10 text-green-500 text-4xl font-bold animate-fade-in">
          👍 LIKE
        </div>
      )}
      {swipeDir === "left" && (
        <div className="absolute top-10 right-10 text-red-500 text-4xl font-bold animate-fade-in">
          👎 NOPE
        </div>
      )}
      {swipeDir === "up" && (
        <div className="absolute bottom-10 left-1/2 transform -translate-x-1/2 text-blue-500 text-3xl font-semibold animate-fade-in">
          🔼 SAVED
        </div>
      )}
    </animated.div>
  );
};

export default FashionCard;
