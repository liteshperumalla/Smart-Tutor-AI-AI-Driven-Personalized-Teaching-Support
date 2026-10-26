import { Skeleton, SkeletonDashboard, SkeletonRegion } from "@/components/skeleton";

export default function Loading() {
  return (
    <SkeletonRegion label="Loading evaluation dashboard" className="mx-auto w-full max-w-6xl space-y-6">
      <Skeleton className="h-8 w-64" />
      <SkeletonDashboard />
    </SkeletonRegion>
  );
}
