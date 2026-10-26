import { Skeleton, SkeletonCard, SkeletonRegion } from "@/components/skeleton";

// Route-level fallback while a page's code and data stream in: a page hero
// followed by a card grid, the shape most pages share.
export default function Loading() {
  return (
    <SkeletonRegion label="Loading page" className="mx-auto w-full max-w-6xl space-y-8">
      <div className="rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8 lg:p-10">
        <Skeleton className="h-6 w-28 rounded-full" />
        <Skeleton className="mt-5 h-10 w-80 max-w-full" />
        <Skeleton className="mt-4 h-4 w-[32rem] max-w-full" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    </SkeletonRegion>
  );
}
