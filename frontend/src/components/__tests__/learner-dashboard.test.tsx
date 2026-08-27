import { render, screen, waitFor } from "@testing-library/react";
import { LearnerDashboard } from "@/components/learner-dashboard";
import { ActiveCourseProvider } from "@/components/active-course-provider";
import { fetchCourseCatalog, fetchCourses, fetchLearningDashboard } from "@/lib/api";

jest.mock("@/hooks/useAuthToken", () => ({
  useAuthToken: () => ({ token: "authenticated" }),
}));

jest.mock("@/lib/api", () => ({
  fetchCourses: jest.fn(),
  fetchCourseCatalog: jest.fn(),
  fetchLearningDashboard: jest.fn(),
}));

const mockedCourses = fetchCourses as jest.MockedFunction<typeof fetchCourses>;
const mockedCatalog = fetchCourseCatalog as jest.MockedFunction<typeof fetchCourseCatalog>;
const mockedDashboard = fetchLearningDashboard as jest.MockedFunction<typeof fetchLearningDashboard>;

describe("LearnerDashboard", () => {
  it("shows the recommended practice action and objective progress", async () => {
    mockedCourses.mockResolvedValue([{ id: "info-5731", code: "INFO 5731", title: "Computational Methods", description: "", membership_role: "student" }]);
    mockedCatalog.mockResolvedValue([]);
    mockedDashboard.mockResolvedValue({
      course: { id: "info-5731", code: "INFO 5731", title: "Computational Methods" },
      weekly_goal: { completed: 1, target: 3 },
      recommendation: { objective_id: "ie-foundations", title: "Explain information extraction concepts", module_id: "information-extraction", mastery: 0, reason: "Start a diagnostic practice set", difficulty: "easy" },
      mastery: [{ objective_id: "ie-foundations", title: "Explain information extraction concepts", module_id: "information-extraction", score: 0.12, attempts: 1, correct: 0 }],
      recent_activity: [],
    });

    render(<ActiveCourseProvider><LearnerDashboard /></ActiveCourseProvider>);

    await waitFor(() => expect(screen.getByText("Next best action")).toBeInTheDocument());
    expect(screen.getByText("Practice: Explain information extraction concepts")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /start practice/i })).toHaveAttribute("href", expect.stringContaining("objective=ie-foundations"));
  });
});
