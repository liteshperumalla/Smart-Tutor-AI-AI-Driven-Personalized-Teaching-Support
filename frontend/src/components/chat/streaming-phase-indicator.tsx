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
  // Agent identity reuses the chart series colors; the phase line itself is
  // always Neural Teal so "working" reads the same for every agent.
  color: string;
  bgColor: string;
  phases: StreamingPhase[];
}> = {
  tutor_agent: {
    label: "Tutor Agent",
    icon: GraduationCap,
    color: "text-primary",
    bgColor: "bg-primary",
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
    color: "text-warning",
    bgColor: "bg-warning",
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
    color: "text-lavender",
    bgColor: "bg-lavender",
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
    color: "text-success",
    bgColor: "bg-success",
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
    color: "text-info",
    bgColor: "bg-bright",
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

  const agentDot = agentConfig?.bgColor ?? "bg-secondary";

  return (
    <div className="flex w-full max-w-md flex-col py-2 animate-fade-in-up">
      {/* Agent badge when detected */}
      {agentConfig && (
        <div className="mb-1.5 flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${agentDot} animate-pulse`} />
          <span className={`text-[11px] font-semibold ${agentConfig.color}`}>{agentConfig.label}</span>
        </div>
      )}

      {/* Phase line: Neural Teal + spinner */}
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-secondary" role="status">
        <span className="inline-block h-[13px] w-[13px] rounded-full border-2 border-secondary border-t-transparent animate-phase-spin" />
        <IconComponent className="h-3.5 w-3.5" />
        <span>{currentPhase.label}…</span>
      </div>

      {/* Shimmer placeholder for the answer that's on its way */}
      <div className="shimmer-line w-[88%]" />
      <div className="shimmer-line mt-1.5 w-[70%]" />
      <div className="shimmer-line mt-1.5 w-[52%]" />

      {/* Progress indicator showing which phase we're on */}
      <div className="mt-2.5 flex items-center gap-1">
        {phases.map((phase, index) => (
          <div
            key={phase.id}
            className={`h-1 rounded-full transition-all duration-300 ${
              index <= currentPhaseIndex ? "w-4 bg-secondary" : "w-2 bg-line"
            }`}
          />
        ))}
      </div>
    </div>
  );
}

// Simplified thinking indicator for quick responses
export function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-3 py-2">
      <div className="flex items-center gap-1">
        <span className="h-2 w-2 rounded-full bg-secondary animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="h-2 w-2 rounded-full bg-secondary animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="h-2 w-2 rounded-full bg-secondary animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
      <span className="text-sm font-semibold text-secondary">Thinking…</span>
    </div>
  );
}
