import type { Theme } from "../types";

// A clean status bar drawn over the phone screen (the real one is cropped from the recordings):
// always 9:41, full signal, Wi-Fi and battery.
export const StatusBar: React.FC<{ width: number; height: number; theme: Theme; font: string }> = ({ width, height, theme, font }) => {
  const s = height / 112; // designed for a 1080 px wide screen, then scaled
  return (
    <div
      style={{
        position: "absolute", top: 0, left: 0, width, height, background: theme.screenBg,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: `0 ${60 * s}px`, boxSizing: "border-box", color: theme.text,
        fontFamily: font, fontWeight: 600, fontSize: 40 * s,
      }}
    >
      <span>9:41</span>
      <svg width={170 * s} height={40 * s} viewBox="0 0 170 40">
        <rect x="0" y="26" width="7" height="12" rx="2" fill={theme.text} />
        <rect x="11" y="19" width="7" height="19" rx="2" fill={theme.text} />
        <rect x="22" y="11" width="7" height="27" rx="2" fill={theme.text} />
        <rect x="33" y="3" width="7" height="35" rx="2" fill={theme.text} />
        <path d="M78 37 L60 17 A27 27 0 0 1 96 17 Z" fill={theme.text} />
        <rect x="112" y="8" width="50" height="26" rx="6" fill="none" stroke={theme.text} strokeWidth="3" />
        <rect x="116" y="12" width="42" height="18" rx="3" fill={theme.text} />
        <rect x="164" y="16" width="4" height="10" rx="2" fill={theme.text} />
      </svg>
    </div>
  );
};
