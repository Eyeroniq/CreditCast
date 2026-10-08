"use client";
// Theme switch (ROADMAP 6.3.2): System → Light → Dark. "System" follows the
// device's light/dark setting; an explicit choice is remembered on this device.
// The saved choice is applied before first paint by THEME_INIT_SCRIPT (layout).
import { useEffect, useState } from "react";

const KEY = "cc-theme";
const MODES = ["system", "light", "dark"];
const LABEL = { system: "◐ Theme: System", light: "☀ Theme: Light", dark: "☾ Theme: Dark" };

export const THEME_INIT_SCRIPT = `try{var t=localStorage.getItem("${KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}catch(e){}`;

function apply(mode) {
  const root = document.documentElement;
  if (mode === "system") delete root.dataset.theme;
  else root.dataset.theme = mode;
  try {
    if (mode === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, mode);
  } catch {
    /* storage blocked (private mode): the choice lasts for this page only */
  }
}

export default function ThemeToggle() {
  const [mode, setMode] = useState("system");
  useEffect(() => {
    const t = document.documentElement.dataset.theme;
    setMode(t === "light" || t === "dark" ? t : "system");
  }, []);

  const next = () => {
    const m = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
    apply(m);
    setMode(m);
  };

  return (
    <button type="button" className="theme-toggle" onClick={next}
      aria-label={`Colour theme: ${mode}. Click to change.`}>
      {LABEL[mode]}
    </button>
  );
}
