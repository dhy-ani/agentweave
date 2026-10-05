import React, { useEffect, useRef, useState } from "react";
import { useDrag } from "@use-gesture/react";
import { SparkleIcon } from "./icons";
import { imageUrl } from "../config";
import { swipeDirection, cardTransform, SWIPE_OUT_MS, SWIPE_LABELS } from "../lib/swipe";

export function matchTone(score) {
  if (score >= 70) return "text-sage-700";
  if (score >= 40) return "text-brand-600";
  return "text-muted";
}

// The fly-out is a plain CSS transition plus a timer rather than a spring
// library: the outcome (onSwipe) must fire deterministically even when the
// animation cannot run (reduced motion, background tabs).
const FashionCard = ({ image, result, trendiness_score, match_score, future_projection, onSwipe }) => {
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [swipeDir, setSwipeDir] = useState("");
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const triggerSwipe = (dir) => {
    if (swipeDir) return;
    setSwipeDir(dir);
    setDragging(false);
    timer.current = setTimeout(() => {
      if (onSwipe) onSwipe(dir);
      setSwipeDir("");
      setOffset({ x: 0, y: 0 });
    }, SWIPE_OUT_MS);
  };

  const bind = useDrag(({ down, movement: [mx, my] }) => {
    if (swipeDir) return;
    if (down) {
      setDragging(true);
      setOffset({ x: mx, y: my });
      return;
    }
    setDragging(false);
    const dir = swipeDirection(mx, my);
    if (dir) triggerSwipe(dir);
    else setOffset({ x: 0, y: 0 });
  });

  const raw = typeof match_score === "number" ? match_score : trendiness_score;
  const score = typeof raw === "number" ? raw : 0;
  const stamp = SWIPE_LABELS[swipeDir];

  return (
    <div className="w-full max-w-xs mx-auto space-y-4">
      <div
        {...bind()}
        data-testid="swipe-card"
        style={{ transform: cardTransform(offset, swipeDir), transition: dragging ? "none" : `transform ${SWIPE_OUT_MS}ms ease-out`, touchAction: "none", userSelect: "none" }}
        className="relative w-full bg-surface border border-line rounded-3xl overflow-hidden shadow-soft cursor-grab active:cursor-grabbing motion-reduce:transition-none"
      >
        <div className="relative">
          <img src={imageUrl(image)} alt={result || "Outfit"} className="w-full h-80 object-cover" draggable={false} />
          <div className="absolute top-3 right-3 bg-surface/90 backdrop-blur-sm rounded-full px-3 py-1 text-xs font-semibold border border-line-strong">
            <span className={matchTone(score)}>{score.toFixed(0)}%</span>
            <span className="text-muted ml-1">match</span>
          </div>
        </div>

        <div className="p-4 space-y-2">
          <p className="text-sm text-ink leading-relaxed line-clamp-3">{result}</p>
          {future_projection && <p className="text-xs text-muted">{future_projection}</p>}
        </div>

        {stamp && (
          <div className="absolute inset-0 bg-canvas/40 flex items-center justify-center">
            <span className={`flex items-center gap-2 text-4xl font-black rounded-xl px-4 py-1 tracking-widest border-4 ${
              swipeDir === "right" ? "text-sage-700 border-sage-500 -rotate-12" : "text-ink border-ink rotate-12"
            }`}>
              <span aria-hidden="true">{stamp.emoji}</span> {stamp.text}
            </span>
          </div>
        )}
        {swipeDir === "up" && (
          <div className="absolute inset-0 bg-brand-200/40 flex items-center justify-center">
            <span className="flex items-center gap-2 text-2xl font-black text-brand-600 border-4 border-brand-400 rounded-xl px-4 py-2 tracking-widest">
              SAVED <SparkleIcon className="w-6 h-6" />
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-center gap-6">
        <button onClick={() => triggerSwipe("left")} aria-label="Pass"
          className="w-[52px] h-[52px] rounded-full border border-line-strong bg-surface hover:border-muted transition-colors flex items-center justify-center text-xl">
          <span aria-hidden="true">{SWIPE_LABELS.left.emoji}</span>
        </button>
        <button onClick={() => triggerSwipe("up")} aria-label="Save"
          className="w-[60px] h-[60px] rounded-full bg-brand-500 hover:bg-brand-600 text-canvas shadow-soft transition-colors flex items-center justify-center">
          <SparkleIcon className="w-6 h-6" />
        </button>
        <button onClick={() => triggerSwipe("right")} aria-label="Like"
          className="w-[52px] h-[52px] rounded-full border border-line-strong bg-surface hover:border-sage-600 transition-colors flex items-center justify-center text-xl">
          <span aria-hidden="true">{SWIPE_LABELS.right.emoji}</span>
        </button>
      </div>
      <p className="text-center text-xs text-muted">Tap or swipe: left to pass, up to save, right to like</p>
    </div>
  );
};

export default FashionCard;
