import React from "react";

// ── Functional UI icons (replace emoji glyphs used as icons) ──────────────────

export const SparkleIcon = ({ className = "w-4 h-4" }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M12 2l1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8L12 2z" />
  </svg>
);

export const ClosetIcon = ({ className = "w-4 h-4" }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M12 3l9 5.5-9 3-9-3L12 3z" />
    <path d="M3 8.5V19a1 1 0 001 1h16a1 1 0 001-1V8.5" />
    <path d="M12 11.5V20" />
  </svg>
);

export const BagIcon = ({ className = "w-4 h-4" }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M6 8h12l1 12.5a1 1 0 01-1 1.1H6a1 1 0 01-1-1.1L6 8z" />
    <path d="M9 8V6.5a3 3 0 016 0V8" />
  </svg>
);

export const SpinnerIcon = ({ className = "w-4 h-4" }) => (
  <svg viewBox="0 0 24 24" fill="none" className={`animate-spin ${className}`}>
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.25" />
    <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
  </svg>
);

export const CameraIcon = ({ className = "w-6 h-6" }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 011 1v10a1 1 0 01-1 1H4a1 1 0 01-1-1V9a1 1 0 011-1z" />
    <circle cx="12" cy="13.5" r="3.5" />
  </svg>
);

export const HangerIcon = ({ className = "w-6 h-6" }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M12 4a1.5 1.5 0 10-1.5 1.5" />
    <path d="M12 5.5V8" />
    <path d="M12 8l9 6.5a1.5 1.5 0 01-.9 2.7H3.9A1.5 1.5 0 013 14.5L12 8z" />
    <path d="M6 17h12" />
  </svg>
);

export const ProfileIcon = ({ className = "w-4 h-4" }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M4.5 20a7.5 7.5 0 0115 0" />
  </svg>
);

export const HeartIcon = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M12 21s-7.5-4.6-10-9.3C.4 8.1 2.2 4.5 5.7 4c2-.3 3.9.6 5 2.2C11.8 4.6 13.7 3.7 15.7 4c3.5.5 5.3 4.1 3.7 7.7C19.5 16.4 12 21 12 21z" />
  </svg>
);

export const XIcon = ({ className = "w-5 h-5" }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className={className}>
    <path d="M6 6l12 12M18 6L6 18" />
  </svg>
);

// ── Decorative hand-drawn-style doodles (purses, tops, sparkles, flowers, skirts, shoes) ──
// Scattered as small, low-opacity accents. Never interactive.

export const DoodleSparkle = ({ className = "w-4 h-4", style }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className} style={style}>
    <path d="M12 1l2 8 8 2-8 2-2 8-2-8-8-2 8-2 2-8z" />
  </svg>
);

export const DoodlePurse = ({ className = "w-8 h-8", style }) => (
  <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
    <path d="M9 9c0-3 2.5-5 5-5s5 2 5 5" />
    <rect x="5" y="9" width="18" height="15" rx="3" />
    <path d="M5 15h18" />
  </svg>
);

export const DoodleTop = ({ className = "w-8 h-8", style }) => (
  <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
    <path d="M12 4h8l7 5-4 4-3-2v17H12V11l-3 2-4-4 7-5z" />
  </svg>
);

export const DoodleSkirt = ({ className = "w-8 h-8", style }) => (
  <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
    <path d="M10 4h12l3 24H7l3-24z" />
    <path d="M10 4c0 3 2.7 5 6 5s6-2 6-5" />
  </svg>
);

export const DoodleFlower = ({ className = "w-8 h-8", style }) => (
  <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
    <circle cx="16" cy="10" r="5" />
    <circle cx="23" cy="15" r="5" />
    <circle cx="20" cy="23" r="5" />
    <circle cx="12" cy="23" r="5" />
    <circle cx="9" cy="15" r="5" />
    <circle cx="16" cy="16" r="2.5" fill="currentColor" stroke="none" />
  </svg>
);

export const DoodleShoe = ({ className = "w-8 h-8", style }) => (
  <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" className={className} style={style}>
    <path d="M4 20c3-1 5-3 7-6 1.5-2.2 3-3 5-3 1 2 2.5 3 5 3.5 3 .6 7 1.5 7 5.5v2H4v-2z" />
    <path d="M4 20c0 0 2 1.5 6 1.5" />
  </svg>
);

export const DOODLES = [DoodlePurse, DoodleTop, DoodleSkirt, DoodleFlower, DoodleShoe, DoodleSparkle];
