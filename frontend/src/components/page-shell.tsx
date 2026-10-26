import { ReactNode } from "react";

type TagName = "div" | "main" | "section";

interface PageShellProps {
  children: ReactNode;
  as?: TagName;
  className?: string;
  contentClassName?: string;
  noCard?: boolean;
}

export function PageShell({
  children,
  as = "section",
  className,
  contentClassName,
  noCard = false,
}: PageShellProps) {
  const outerClassName = [
    "mx-auto h-full w-full px-4 py-8 sm:px-6 lg:px-8",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const frameClassName = "mx-auto flex min-h-full w-full max-w-6xl";

  const containerClassName = noCard
    ? "flex min-h-full w-full flex-col"
    : "flex min-h-full w-full flex-col rounded-[32px] border border-line bg-surface p-6 text-foreground shadow-sm md:p-10";

  const innerClassName = ["flex flex-col gap-8", contentClassName]
    .filter(Boolean)
    .join(" ");

  const Component = as;

  return (
    <Component className={outerClassName}>
      <div className={frameClassName}>
        <div className={containerClassName}>
          <div className={innerClassName}>{children}</div>
        </div>
      </div>
    </Component>
  );
}
