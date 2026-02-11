"use client";

import { Toaster } from "sonner";
import { useTheme } from "@/context/theme-context";

export function ToastProvider() {
  const { theme } = useTheme();
  return (
    <Toaster
      theme={theme as "light" | "dark"}
      position="top-right"
      richColors
      closeButton
    />
  );
}
