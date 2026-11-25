"use client";
import { MotionConfig } from "motion/react";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { ToastProvider } from "@/lib/toast";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider><AuthProvider><ToastProvider><MotionConfig reducedMotion="user">{children}</MotionConfig></ToastProvider></AuthProvider></ThemeProvider>
  );
}
