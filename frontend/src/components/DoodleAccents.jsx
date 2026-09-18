import React from "react";
import { DoodleSparkle, DoodlePurse, DoodleFlower, DoodleSkirt, DoodleShoe, DoodleTop } from "./icons";

// Small, low-opacity hand-drawn-style accents scattered around a page.
// Purely decorative: absolutely positioned, non-interactive, never overlaps content.
const LAYOUTS = {
  auth: [
    { Icon: DoodleSparkle, className: "w-4 h-4 text-gold-400", style: { top: "6%", left: "8%", opacity: 0.5 } },
    { Icon: DoodleSparkle, className: "w-3 h-3 text-brand-300", style: { top: "14%", right: "10%", opacity: 0.4 } },
    { Icon: DoodleFlower, className: "w-8 h-8 text-gold-400", style: { bottom: "10%", left: "6%", opacity: 0.35 } },
    { Icon: DoodlePurse, className: "w-9 h-9 text-brand-300", style: { bottom: "14%", right: "7%", opacity: 0.35 } },
    { Icon: DoodleSkirt, className: "w-7 h-7 text-brand-300", style: { top: "42%", right: "4%", opacity: 0.25 } },
  ],
  dashboard: [
    { Icon: DoodleSparkle, className: "w-3.5 h-3.5 text-gold-400", style: { top: "6px", right: "14%", opacity: 0.5 } },
    { Icon: DoodleSkirt, className: "w-6 h-6 text-brand-300", style: { top: "70px", left: "5%", opacity: 0.3 } },
    { Icon: DoodleShoe, className: "w-7 h-7 text-brand-300", style: { top: "140px", right: "3%", opacity: 0.25 } },
    { Icon: DoodleTop, className: "w-6 h-6 text-gold-400", style: { bottom: "18%", left: "3%", opacity: 0.2 } },
  ],
};

const DoodleAccents = ({ variant = "auth" }) => {
  const items = LAYOUTS[variant] || LAYOUTS.auth;
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden select-none" aria-hidden="true">
      {items.map(({ Icon, className, style }, i) => (
        <Icon key={i} className={`absolute ${className}`} style={style} />
      ))}
    </div>
  );
};

export default DoodleAccents;
