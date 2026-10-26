"use client";

import { Toaster } from "sonner";
import { useTheme } from "@/context/theme-context";

export function ToastProvider() {
  const { theme } = useTheme();
  return (
    <Toaster
      theme={theme as "light" | "dark"}
      position="top-right"
      closeButton
      // Design-system toasts: a surface card with a tinted icon well, not
      // sonner's saturated richColors fills.
      toastOptions={{
        classNames: {
          toast:
            "rounded-md! border! border-line! bg-surface! text-foreground! shadow-md! font-sans! text-[13px]! font-semibold! [&_[data-icon]]:size-[22px] [&_[data-icon]]:justify-center [&_[data-icon]]:rounded-full [&_[data-icon]_svg]:size-3.5",
          description: "text-muted! font-normal!",
          success: "[&_[data-icon]]:bg-success-bg [&_[data-icon]]:text-success",
          error: "[&_[data-icon]]:bg-danger-bg [&_[data-icon]]:text-danger",
          warning: "[&_[data-icon]]:bg-warning-bg [&_[data-icon]]:text-warning",
          info: "[&_[data-icon]]:bg-info-bg [&_[data-icon]]:text-info",
          actionButton: "rounded-full! bg-primary-solid! text-white!",
          cancelButton: "rounded-full! bg-surface-2! text-foreground!",
          closeButton: "border-line! bg-surface! text-muted!",
        },
      }}
    />
  );
}
