"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

type Theme = "light" | "dark";

type ThemeContextValue = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
};

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const STORAGE_KEY = "smart-ai-tutor-theme";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>("light");
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      let initial: Theme = "light";
      const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
      if (stored === "dark" || stored === "light") {
        initial = stored;
      } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
        initial = "dark";
      }
      setThemeState(initial);
      setHasHydrated(true);
    });
    return () => cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!hasHydrated) return;
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("theme-dark");
      root.classList.add("dark");
    } else {
      root.classList.remove("theme-dark");
      root.classList.remove("dark");
    }
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme, hasHydrated]);

  const setTheme = useCallback((value: Theme) => {
    setThemeState(value === "dark" ? "dark" : "light");
  }, []);

  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}
