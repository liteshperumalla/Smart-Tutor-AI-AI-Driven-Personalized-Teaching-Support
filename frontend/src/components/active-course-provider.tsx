"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

const ACTIVE_COURSE_STORAGE_KEY = "smart-ai-tutor.active-course";

type ActiveCourseContextValue = {
  activeCourseId?: string;
  setActiveCourseId: (courseId?: string) => void;
};

const ActiveCourseContext = createContext<ActiveCourseContextValue | undefined>(undefined);

/**
 * Keeps the learner's course selection consistent across Home, Chat, and Quiz.
 * Course access is still verified by the API on every request; this only stores
 * a convenience preference in the browser.
 */
export function ActiveCourseProvider({ children }: { children: React.ReactNode }) {
  const [activeCourseId, setStoredCourseId] = useState<string | undefined>(() => {
    if (typeof window === "undefined") return undefined;
    return window.localStorage.getItem(ACTIVE_COURSE_STORAGE_KEY) || undefined;
  });

  const setActiveCourseId = useCallback((courseId?: string) => {
    setStoredCourseId(courseId);
    if (courseId) window.localStorage.setItem(ACTIVE_COURSE_STORAGE_KEY, courseId);
    else window.localStorage.removeItem(ACTIVE_COURSE_STORAGE_KEY);
  }, []);

  const value = useMemo(
    () => ({ activeCourseId, setActiveCourseId }),
    [activeCourseId, setActiveCourseId]
  );

  return <ActiveCourseContext.Provider value={value}>{children}</ActiveCourseContext.Provider>;
}

export function useActiveCourse() {
  const context = useContext(ActiveCourseContext);
  if (!context) throw new Error("useActiveCourse must be used within ActiveCourseProvider");
  return context;
}
