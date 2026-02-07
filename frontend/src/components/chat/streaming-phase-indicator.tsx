"use client";

import { useState, useEffect } from "react";
import { Search, Brain, Sparkles, BookOpen, Database } from "lucide-react";

interface StreamingPhase {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  duration: number | null; // null means infinite (until streaming starts)
}

const STREAMING_PHASES: StreamingPhase[] = [
  { id: "searching", label: "Searching knowledge base", icon: Search, duration: 2000 },
  { id: "retrieving", label: "Retrieving relevant sources", icon: Database, duration: 1500 },
  { id: "analyzing", label: "Analyzing sources", icon: Brain, duration: 2000 },
  { id: "generating", label: "Generating response", icon: Sparkles, duration: null },
];

interface StreamingPhaseIndicatorProps {
  isStreaming: boolean;
  hasContent: boolean;
}

export function StreamingPhaseIndicator({ isStreaming, hasContent }: StreamingPhaseIndicatorProps) {
  const [currentPhaseIndex, setCurrentPhaseIndex] = useState(0);

  useEffect(() => {
    if (!isStreaming || hasContent) {
      setCurrentPhaseIndex(0);
      return;
    }

    const currentPhase = STREAMING_PHASES[currentPhaseIndex];

    // If current phase has a duration, move to next after timeout
    if (currentPhase?.duration !== null) {
      const timer = setTimeout(() => {
        setCurrentPhaseIndex((prev) => {
          const next = prev + 1;
          return next < STREAMING_PHASES.length ? next : prev;
        });
      }, currentPhase?.duration || 2000);

      return () => clearTimeout(timer);
    }
  }, [isStreaming, hasContent, currentPhaseIndex]);

  // Reset when streaming stops
  useEffect(() => {
    if (!isStreaming) {
      setCurrentPhaseIndex(0);
    }
  }, [isStreaming]);

  if (!isStreaming || hasContent) {
    return null;
  }

  const currentPhase = STREAMING_PHASES[currentPhaseIndex];
  const IconComponent = currentPhase.icon;

  return (
    <div className="flex items-center gap-3 py-3 animate-fade-in-up">
      {/* Animated icon container with spinner */}
      <div className="relative">
        <div className="h-10 w-10 rounded-full bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
          <IconComponent className="h-5 w-5 text-indigo-600 dark:text-indigo-400 animate-pulse" />
        </div>
        {/* Spinning border */}
        <div className="absolute inset-0 rounded-full border-2 border-indigo-500/30 border-t-indigo-500 animate-phase-spin" />
      </div>

      {/* Phase label with progress dots */}
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {currentPhase.label}...
        </span>

        {/* Progress indicator showing which phase we're on */}
        <div className="flex items-center gap-1">
          {STREAMING_PHASES.map((phase, index) => (
            <div
              key={phase.id}
              className={`h-1 rounded-full transition-all duration-300 ${
                index <= currentPhaseIndex
                  ? "w-4 bg-indigo-500"
                  : "w-2 bg-zinc-300 dark:bg-zinc-600"
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// Simplified thinking indicator for quick responses
export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-3 py-2">
      <div className="flex items-center gap-1">
        <span className="h-2 w-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="h-2 w-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="h-2 w-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
      <span className="text-sm text-zinc-500 dark:text-zinc-400">Thinking...</span>
    </div>
  );
}
