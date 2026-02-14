"use client";

import { useState, useEffect } from "react";
import { Search, Brain, Sparkles, Database, GraduationCap, HelpCircle, UserCog, ClipboardCheck, MessageSquareHeart } from "lucide-react";

interface StreamingPhase {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  duration: number | null; // null means infinite (until streaming starts)
}

const DEFAULT_PHASES: StreamingPhase[] = [
  { id: "searching", label: "Searching knowledge base", icon: Search, duration: 2000 },
  { id: "retrieving", label: "Retrieving relevant sources", icon: Database, duration: 1500 },
  { id: "analyzing", label: "Analyzing sources", icon: Brain, duration: 2000 },
  { id: "generating", label: "Generating response", icon: Sparkles, duration: null },
];

// Agent-specific configurations
const AGENT_CONFIG: Record<string, {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  bgColor: string;
  borderColor: string;
  phases: StreamingPhase[];
}> = {
  tutor_agent: {
    label: "Tutor Agent",
    icon: GraduationCap,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-100 dark:bg-blue-900/30",
    borderColor: "border-blue-500/30 border-t-blue-500",
    phases: [
      { id: "searching", label: "Searching course materials", icon: Search, duration: 1500 },
      { id: "retrieving", label: "Retrieving relevant content", icon: Database, duration: 1500 },
      { id: "preparing", label: "Preparing educational response", icon: GraduationCap, duration: 2000 },
      { id: "generating", label: "Generating explanation", icon: Sparkles, duration: null },
    ],
  },
  doubts_agent: {
    label: "Doubt Resolver",
    icon: HelpCircle,
    color: "text-amber-600 dark:text-amber-400",
    bgColor: "bg-amber-100 dark:bg-amber-900/30",
    borderColor: "border-amber-500/30 border-t-amber-500",
    phases: [
      { id: "understanding", label: "Understanding your doubt", icon: HelpCircle, duration: 1500 },
      { id: "searching", label: "Finding clarifying sources", icon: Search, duration: 1500 },
      { id: "analyzing", label: "Analyzing concept gaps", icon: Brain, duration: 2000 },
      { id: "generating", label: "Crafting clarification", icon: Sparkles, duration: null },
    ],
  },
  personalised_agent: {
    label: "Personalized Agent",
    icon: UserCog,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-100 dark:bg-purple-900/30",
    borderColor: "border-purple-500/30 border-t-purple-500",
    phases: [
      { id: "profiling", label: "Loading your learning profile", icon: UserCog, duration: 1500 },
      { id: "searching", label: "Finding personalized content", icon: Search, duration: 1500 },
      { id: "adapting", label: "Adapting to your level", icon: Brain, duration: 2000 },
      { id: "generating", label: "Generating tailored response", icon: Sparkles, duration: null },
    ],
  },
  quiz_helper_agent: {
    label: "Quiz Helper",
    icon: ClipboardCheck,
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-100 dark:bg-green-900/30",
    borderColor: "border-green-500/30 border-t-green-500",
    phases: [
      { id: "searching", label: "Searching quiz-related content", icon: Search, duration: 1500 },
      { id: "analyzing", label: "Analyzing your quiz history", icon: ClipboardCheck, duration: 1500 },
      { id: "preparing", label: "Preparing study guidance", icon: Brain, duration: 2000 },
      { id: "generating", label: "Generating quiz help", icon: Sparkles, duration: null },
    ],
  },
  feedback_agent: {
    label: "Feedback Agent",
    icon: MessageSquareHeart,
    color: "text-teal-600 dark:text-teal-400",
    bgColor: "bg-teal-100 dark:bg-teal-900/30",
    borderColor: "border-teal-500/30 border-t-teal-500",
    phases: [
      { id: "reading", label: "Reading your feedback", icon: MessageSquareHeart, duration: 1500 },
      { id: "processing", label: "Processing feedback", icon: Brain, duration: 2000 },
      { id: "generating", label: "Generating acknowledgment", icon: Sparkles, duration: null },
    ],
  },
};

interface StreamingPhaseIndicatorProps {
  isStreaming: boolean;
  hasContent: boolean;
  agentName?: string | null;
}

export function StreamingPhaseIndicator({ isStreaming, hasContent, agentName }: StreamingPhaseIndicatorProps) {
  const [currentPhaseIndex, setCurrentPhaseIndex] = useState(0);

  const agentConfig = agentName ? AGENT_CONFIG[agentName] : null;
  const phases = agentConfig?.phases ?? DEFAULT_PHASES;

  useEffect(() => {
    if (!isStreaming || hasContent) {
      const timer = setTimeout(() => setCurrentPhaseIndex(0), 0);
      return () => clearTimeout(timer);
    }

    const currentPhase = phases[currentPhaseIndex];

    // If current phase has a duration, move to next after timeout
    if (currentPhase?.duration !== null) {
      const timer = setTimeout(() => {
        setCurrentPhaseIndex((prev) => {
          const next = prev + 1;
          return next < phases.length ? next : prev;
        });
      }, currentPhase?.duration || 2000);

      return () => clearTimeout(timer);
    }
  }, [isStreaming, hasContent, currentPhaseIndex, phases]);

  // Reset when streaming stops
  useEffect(() => {
    if (!isStreaming) {
      const timer = setTimeout(() => setCurrentPhaseIndex(0), 0);
      return () => clearTimeout(timer);
    }
  }, [isStreaming]);

  // Reset phase index when agent is detected (switch to agent-specific phases)
  useEffect(() => {
    if (agentName) {
      const timer = setTimeout(() => setCurrentPhaseIndex(0), 0);
      return () => clearTimeout(timer);
    }
  }, [agentName]);

  if (!isStreaming || hasContent) {
    return null;
  }

  const currentPhase = phases[currentPhaseIndex];
  const IconComponent = currentPhase.icon;

  const iconColor = agentConfig?.color ?? "text-indigo-600 dark:text-indigo-400";
  const iconBg = agentConfig?.bgColor ?? "bg-indigo-100 dark:bg-indigo-900/30";
  const spinnerBorder = agentConfig?.borderColor ?? "border-indigo-500/30 border-t-indigo-500";
  const dotActive = agentConfig ? agentConfig.color.replace("text-", "bg-").split(" ")[0] : "bg-indigo-500";

  return (
    <div className="flex items-center gap-3 py-3 animate-fade-in-up">
      {/* Animated icon container with spinner */}
      <div className="relative">
        <div className={`h-10 w-10 rounded-full ${iconBg} flex items-center justify-center`}>
          <IconComponent className={`h-5 w-5 ${iconColor} animate-pulse`} />
        </div>
        {/* Spinning border */}
        <div className={`absolute inset-0 rounded-full border-2 ${spinnerBorder} animate-phase-spin`} />
      </div>

      {/* Phase label with agent name and progress dots */}
      <div className="flex flex-col gap-1">
        {/* Agent badge when detected */}
        {agentConfig && (
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className={`h-1.5 w-1.5 rounded-full ${dotActive} animate-pulse`} />
            <span className={`text-[11px] font-semibold ${iconColor}`}>
              {agentConfig.label}
            </span>
          </div>
        )}
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          {currentPhase.label}...
        </span>

        {/* Progress indicator showing which phase we're on */}
        <div className="flex items-center gap-1">
          {phases.map((phase, index) => (
            <div
              key={phase.id}
              className={`h-1 rounded-full transition-all duration-300 ${
                index <= currentPhaseIndex
                  ? `w-4 ${dotActive}`
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
