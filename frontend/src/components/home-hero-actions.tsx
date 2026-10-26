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
           className="btn-primary"
         >
           Open chat
         </Link>
         <Link
           href="/profile"
           className="btn-secondary"
         >
           Profile & settings
         </Link>
         <span className="badge badge-success self-center">
           Signed in
         </span>
       </div>
     );
  }

    return (
      <div className="flex flex-wrap justify-center gap-3 pt-4 sm:justify-start">
        <Link
          href="/login"
          className="btn-primary"
        >
          Sign in
        </Link>
        <Link href="/signup" className="btn-secondary">
          Create account
        </Link>
      </div>
    );
}

 function HeroActionsSkeleton() {
   return (
     <div className="flex flex-wrap justify-center gap-3 pt-4 sm:justify-start">
       <span className="h-10 w-28 animate-pulse rounded-full bg-line" />
       <span className="h-10 w-32 animate-pulse rounded-full bg-line" />
       <span className="h-10 w-24 animate-pulse rounded-full bg-line" />
     </div>
   );
 }
