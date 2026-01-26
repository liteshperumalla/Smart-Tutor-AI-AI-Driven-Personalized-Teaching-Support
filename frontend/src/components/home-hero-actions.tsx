"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuthToken } from "@/hooks/useAuthToken";

export function HomeHeroActions() {
  const [hydrated, setHydrated] = useState(false);
  const { token } = useAuthToken({ redirectTo: undefined });

  useEffect(() => {
    const frame = requestAnimationFrame(() => setHydrated(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  if (!hydrated) {
    return <HeroActionsSkeleton />;
  }

  if (token) {
     return (
       <div className="flex flex-wrap justify-center gap-3 pt-4 sm:justify-start">
         <Link
           href="/chat"
           className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-semibold text-white hover:bg-zinc-800"
         >
           Open chat
         </Link>
         <Link
           href="/profile"
           className="rounded-full bg-zinc-100 px-5 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
         >
           Profile & settings
         </Link>
         <span className="rounded-full bg-zinc-100 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
           Signed in
         </span>
       </div>
     );
  }

    return (
      <div className="flex flex-wrap justify-center gap-3 pt-4 sm:justify-start">
        <Link
          href="/login"
          className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-semibold text-white hover:bg-zinc-800"
        >
          Sign in
        </Link>
        <Link href="/signup" className="rounded-full bg-zinc-100 px-5 py-2 text-sm font-semibold text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700">
          Create account
        </Link>
        <span className="rounded-full bg-zinc-100 px-4 py-2 text-xs font-semibold uppercase tracking-[0.3em] text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
          UNT · Fall 2025
        </span>
      </div>
    );
}

 function HeroActionsSkeleton() {
   return (
     <div className="flex flex-wrap justify-center gap-3 pt-4 sm:justify-start">
       <span className="h-10 w-28 animate-pulse rounded-full bg-zinc-200" />
       <span className="h-10 w-32 animate-pulse rounded-full bg-zinc-200" />
       <span className="h-10 w-24 animate-pulse rounded-full bg-zinc-200" />
     </div>
   );
 }
