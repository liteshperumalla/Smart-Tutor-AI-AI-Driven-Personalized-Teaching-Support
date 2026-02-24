import { redirect } from "next/navigation";

/**
 * /research is deprecated — research tools live in the chat sidebar.
 * Redirect seamlessly so any bookmarked or linked URLs still work.
 */
export default function ResearchPage() {
  redirect("/chat");
}
