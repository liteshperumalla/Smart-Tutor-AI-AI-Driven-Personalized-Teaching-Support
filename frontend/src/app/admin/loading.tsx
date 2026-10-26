import { SkeletonRegion, SkeletonStatGrid, SkeletonTable } from "@/components/skeleton";

// Admin sections are stats and tables; the admin layout (header + tabs)
// stays rendered around this while the section loads.
export default function Loading() {
  return (
    <SkeletonRegion label="Loading admin section" className="space-y-6">
      <SkeletonStatGrid />
      <SkeletonTable rows={6} />
    </SkeletonRegion>
  );
}
