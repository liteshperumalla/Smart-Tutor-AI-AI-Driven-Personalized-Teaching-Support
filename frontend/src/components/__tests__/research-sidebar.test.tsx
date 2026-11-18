import { fireEvent, render, screen } from "@testing-library/react";
import { ResearchSidebar, type ResearchSource } from "@/components/chat/research-sidebar";

function renderSidebar(sources: ResearchSource[] = [], overrides: Partial<Parameters<typeof ResearchSidebar>[0]> = {}) {
  const props = {
    isOpen: true,
    onClose: jest.fn(),
    onFilesAdded: jest.fn(),
    onUrlSubmit: jest.fn(),
    onRemoveSource: jest.fn(),
    onToolSelect: jest.fn(),
    sources,
    ...overrides,
  };
  render(<ResearchSidebar {...props} />);
  return props;
}

describe("ResearchSidebar", () => {
  it("submits a link and clears the input", () => {
    const props = renderSidebar();
    const input = screen.getByPlaceholderText("https://example.com/article");
    fireEvent.change(input, { target: { value: "https://example.com/attention" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add" })[0]);
    expect(props.onUrlSubmit).toHaveBeenCalledWith("https://example.com/attention");
    expect(input).toHaveValue("");
  });

  it("counts only ready sources as active and lists each one", () => {
    renderSidebar([
      { key: "a", id: "url_1", name: "Attention Is All You Need", kind: "webpage", status: "ready" },
      { key: "b", name: "https://youtu.be/x", kind: "youtube", status: "adding" },
      { key: "c", name: "notes.pdf", kind: "file", status: "error", error: "Upload failed" },
    ]);
    expect(screen.getByText(/1 active source · 1 adding/)).toBeInTheDocument();
    expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();
    expect(screen.getByLabelText("Upload failed")).toBeInTheDocument();
  });

  it("removes a source", () => {
    const props = renderSidebar([{ key: "a", id: "url_1", name: "Page", kind: "webpage", status: "ready" }]);
    fireEvent.click(screen.getByRole("button", { name: "Remove Page" }));
    expect(props.onRemoveSource).toHaveBeenCalledWith("a");
  });

  it("puts a research tool's prompt in the composer", () => {
    const props = renderSidebar([{ key: "a", id: "url_1", name: "Page", kind: "webpage", status: "ready" }]);
    fireEvent.click(screen.getByRole("button", { name: /Summarize/ }));
    expect(props.onToolSelect).toHaveBeenCalledWith(expect.stringContaining("Summarize the key points"));
  });

  it("disables source-based tools until a source is ready, but not topic tools", () => {
    const props = renderSidebar([{ key: "b", name: "https://x.io", kind: "webpage", status: "adding" }]);
    for (const name of [/Summarize/, /Fact Check/, /Compare/]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
    fireEvent.click(screen.getByRole("button", { name: /Explain/ }));
    expect(props.onToolSelect).toHaveBeenCalledWith("Explain in simple terms: ");
  });
});
