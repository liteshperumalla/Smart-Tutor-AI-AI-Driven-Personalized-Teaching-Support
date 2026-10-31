"use client";

import { useState, FormEvent } from "react";

import {
  CodeLanguage,
  CodeChatMessage,
  executeCode,
  generateCode,
  explainCode,
  debugCode,
  chatWithCodeLLM,
} from "@/lib/api";
import { useAuthToken } from "@/hooks/useAuthToken";
import { PageShell } from "@/components/page-shell";
import { toast } from "sonner";

const SUPPORTED_LANGUAGES: CodeLanguage[] = ["python", "javascript", "java"];

const LANGUAGE_LABELS: Record<CodeLanguage, string> = {
  python: "Python",
  javascript: "JavaScript",
  java: "Java",
};

const PLACEHOLDER_CODE: Record<CodeLanguage, string> = {
  python: `# Write your Python code here
def greet(name):
    return f"Hello, {name}!"

print(greet("World"))`,
  javascript: `// Write your JavaScript code here
function greet(name) {
    return \`Hello, \${name}!\`;
}

console.log(greet("World"));`,
  java: `// Write your Java code here
// Note: Code will be wrapped in Main class if needed
System.out.println("Hello, World!");`,
};

export default function CodeSandboxPage() {
  const { token } = useAuthToken();
  const [language, setLanguage] = useState<CodeLanguage>("python");
  const [code, setCode] = useState(PLACEHOLDER_CODE.python);
  const [output, setOutput] = useState("");
  const [outputSuccess, setOutputSuccess] = useState(true);
  const [generatedCode, setGeneratedCode] = useState("");
  const [explanation, setExplanation] = useState("");
  const [debugResult, setDebugResult] = useState("");
  const [generatePrompt, setGeneratePrompt] = useState("");
  const [showGenerateInput, setShowGenerateInput] = useState(false);

  // Loading states
  const [runningCode, setRunningCode] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [explaining, setExplaining] = useState(false);
  const [debugging, setDebugging] = useState(false);

  // Chat state
  const [chatHistory, setChatHistory] = useState<CodeChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  const handleLanguageChange = (newLanguage: CodeLanguage) => {
    setLanguage(newLanguage);
    setCode(PLACEHOLDER_CODE[newLanguage]);
    setOutput("");
    setGeneratedCode("");
    setExplanation("");
    setDebugResult("");
  };

  const handleRunCode = async () => {
    if (!token || !code.trim()) return;
    setRunningCode(true);
    setOutput("");
    setOutputSuccess(true);
    try {
      const result = await executeCode({ token, code, language });
      setOutput(result.output);
      setOutputSuccess(result.success);
      if (result.success) toast.success("Code executed");
      else toast.error("Execution failed");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Execution failed";
      setOutput(msg);
      setOutputSuccess(false);
      toast.error(msg);
    } finally {
      setRunningCode(false);
    }
  };

  const handleGenerateCode = async (e: FormEvent) => {
    e.preventDefault();
    if (!token || !generatePrompt.trim()) return;
    setGenerating(true);
    setGeneratedCode("");
    try {
      const result = await generateCode({ token, prompt: generatePrompt, language });
      setGeneratedCode(result.code);
      toast.success("Code generated");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Generation failed";
      setGeneratedCode(`Error: ${msg}`);
      toast.error(msg);
    } finally {
      setGenerating(false);
    }
  };

  const handleExplainCode = async () => {
    if (!token || !code.trim()) return;
    setExplaining(true);
    setExplanation("");
    try {
      const result = await explainCode({ token, code, language });
      setExplanation(result.explanation);
      toast.success("Explanation ready");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Explanation failed";
      setExplanation(`Error: ${msg}`);
      toast.error(msg);
    } finally {
      setExplaining(false);
    }
  };

  const handleDebugCode = async () => {
    if (!token || !code.trim()) return;
    setDebugging(true);
    setDebugResult("");
    try {
      const result = await debugCode({ token, code, language });
      let debugOutput = result.analysis;
      if (result.fixed_code) {
        debugOutput += `\n\n--- Fixed Code ---\n${result.fixed_code}`;
      }
      setDebugResult(debugOutput);
      toast.success("Debug analysis complete");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Debugging failed";
      setDebugResult(`Error: ${msg}`);
      toast.error(msg);
    } finally {
      setDebugging(false);
    }
  };

  const handleChatSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!token || !chatInput.trim()) return;

    const userMessage: CodeChatMessage = { role: "user", content: chatInput };
    setChatHistory((prev) => [...prev, userMessage]);
    setChatInput("");
    setChatLoading(true);

    try {
      const result = await chatWithCodeLLM({
        token,
        message: chatInput,
        history: chatHistory,
      });
      const assistantMessage: CodeChatMessage = {
        role: "assistant",
        content: result.response,
      };
      setChatHistory((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Chat failed";
      const errorMessage: CodeChatMessage = {
        role: "assistant",
        content: `Error: ${msg}`,
      };
      setChatHistory((prev) => [...prev, errorMessage]);
      toast.error(msg);
    } finally {
      setChatLoading(false);
    }
  };

  const useGeneratedCode = () => {
    if (generatedCode && !generatedCode.startsWith("Error:")) {
      setCode(generatedCode);
      setGeneratedCode("");
      setShowGenerateInput(false);
      setGeneratePrompt("");
    }
  };

  return (
    <PageShell contentClassName="gap-6" noCard>
      <header className="relative overflow-hidden rounded-3xl p-6 sm:p-8 lg:p-12 animate-fade-in-down">
        <div className="relative z-10">
          <h1 className="font-display text-3xl sm:text-5xl font-bold text-foreground">
            Coding Agent
          </h1>
          <p className="mt-3 text-base sm:mt-4 sm:text-lg text-muted max-w-2xl">
            Write, run, explain, and debug code with an AI coding assistant.
          </p>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Code Editor - 2/3 width */}
        <div className="lg:col-span-2 space-y-4">
          {/* Language Selector */}
          <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
            <div className="flex items-center gap-4">
              <label className="text-sm font-medium text-foreground">
                Language:
              </label>
              <div className="flex gap-2">
                {SUPPORTED_LANGUAGES.map((lang) => (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => handleLanguageChange(lang)}
                    className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                      language === lang
                        ? "bg-primary-solid text-white"
                        : "border-line text-foreground hover:bg-surface-2"
                    }`}
                  >
                    {LANGUAGE_LABELS[lang]}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Code Editor */}
          <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
            <label className="mb-2 block text-sm font-medium text-foreground">
              Write or paste your {LANGUAGE_LABELS[language]} code:
            </label>
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="h-56 w-full rounded-xl border border-line bg-surface-2 p-4 font-mono text-sm text-foreground outline-none focus:border-muted"
              placeholder={`Enter ${LANGUAGE_LABELS[language]} code here...`}
              spellCheck={false}
            />
          </div>

          {/* Action Buttons */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 animate-fade-in-up">
            <button
              type="button"
              onClick={handleRunCode}
              disabled={runningCode || !code.trim()}
              className="rounded-full gradient-primary px-4 py-2.5 text-sm font-semibold text-white shadow-brand transition hover:scale-105 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
            >
              {runningCode ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Running...</>
              ) : (
                "Run Code"
              )}
            </button>
            <button
              type="button"
              onClick={() => setShowGenerateInput(!showGenerateInput)}
              className="btn-secondary"
            >
              Generate Code
            </button>
            <button
              type="button"
              onClick={handleExplainCode}
              disabled={explaining || !code.trim()}
              className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {explaining ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-foreground border-t-transparent"></span> Explaining...</>
              ) : (
                "Explain Code"
              )}
            </button>
            <button
              type="button"
              onClick={handleDebugCode}
              disabled={debugging || !code.trim()}
              className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {debugging ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-foreground border-t-transparent"></span> Debugging...</>
              ) : (
                "Debug Code"
              )}
            </button>
          </div>

          {/* Generate Code Input */}
          {showGenerateInput && (
            <form
              onSubmit={handleGenerateCode}
              className="rounded-2xl border border-line bg-surface p-4 shadow-sm"
            >
              <label className="mb-2 block text-sm font-medium text-foreground">
                Describe what you want to code:
              </label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={generatePrompt}
                  onChange={(e) => setGeneratePrompt(e.target.value)}
                  placeholder="e.g., A function to calculate fibonacci numbers"
                  className="input flex-1 py-2"
                />
                <button
                  type="submit"
                  disabled={generating || !generatePrompt.trim()}
                  className="btn-primary disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
                >
                  {generating ? (
                    <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Generating...</>
                  ) : (
                    "Generate"
                  )}
                </button>
              </div>
            </form>
          )}

          {/* Output Section */}
          {output && (
            <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-medium text-foreground">Output:</p>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    outputSuccess
                      ? "bg-success-bg text-success"
                      : "bg-danger-bg text-danger"
                  }`}
                >
                  {outputSuccess ? "Success" : "Error"}
                </span>
              </div>
              <pre className="max-h-48 overflow-auto rounded-xl bg-zinc-900 p-4 text-sm text-zinc-100 dark:bg-zinc-950">
                {output || "(no output)"}
              </pre>
            </div>
          )}

          {/* Generated Code Section */}
          {generatedCode && (
            <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-medium text-foreground">
                  Generated Code:
                </p>
                {!generatedCode.startsWith("Error:") && (
                  <button
                    type="button"
                    onClick={useGeneratedCode}
                    className="rounded-full bg-primary-solid px-4 py-1 text-xs font-medium text-white transition hover:brightness-110"
                  >
                    Use This Code
                  </button>
                )}
              </div>
              <pre className="max-h-64 overflow-auto rounded-xl bg-zinc-900 p-4 text-sm text-zinc-100 dark:bg-zinc-950">
                {generatedCode}
              </pre>
            </div>
          )}

          {/* Explanation Section */}
          {explanation && (
            <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
              <p className="mb-2 text-sm font-medium text-foreground">
                Explanation:
              </p>
              <div className="prose prose-sm max-w-none rounded-xl bg-surface-2 p-4 text-foreground">
                <pre className="whitespace-pre-wrap font-sans">{explanation}</pre>
              </div>
            </div>
          )}

          {/* Debug Result Section */}
          {debugResult && (
            <div className="rounded-2xl border border-line bg-surface p-4 shadow-sm">
              <p className="mb-2 text-sm font-medium text-foreground">
                Debug Analysis:
              </p>
              <div className="prose prose-sm max-w-none rounded-xl bg-surface-2 p-4 text-foreground">
                <pre className="whitespace-pre-wrap font-sans">{debugResult}</pre>
              </div>
            </div>
          )}
        </div>

        {/* Chat Sidebar - 1/3 width */}
        <div className="lg:col-span-1">
          <div className="sticky top-4 rounded-2xl border border-line bg-surface p-4 shadow-sm">
            <h2 className="text-lg font-semibold text-foreground">
              Chat with Coding LLM
            </h2>
            <p className="mt-1 text-xs text-muted">
              Ask questions about programming, get help with code
            </p>

            {/* Chat History */}
            <div className="mt-4 h-80 overflow-y-auto rounded-xl border border-line bg-surface-2 p-3">
              {chatHistory.length === 0 && (
                <p className="text-center text-xs text-muted">
                  Start a conversation...
                </p>
              )}
              {chatHistory.slice(-10).map((msg, index) => (
                <div
                  key={index}
                  className={`mb-3 rounded-xl p-3 text-sm ${
                    msg.role === "user"
                      ? "ml-4 bg-primary-bg text-foreground"
                      : "mr-4 bg-line text-foreground"
                  }`}
                >
                  <p className="mb-1 text-xs font-semibold opacity-70">
                    {msg.role === "user" ? "You" : "LLM"}
                  </p>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
              ))}
              {chatLoading && (
                <div className="mr-4 rounded-xl bg-line p-3 text-sm">
                  <p className="text-xs font-semibold opacity-70">LLM</p>
                  <p className="animate-pulse text-muted">Thinking...</p>
                </div>
              )}
            </div>

            {/* Chat Input */}
            <form onSubmit={handleChatSubmit} className="mt-3">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Type your message..."
                className="input h-20 p-3"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleChatSubmit(e);
                  }
                }}
              />
              <button
                type="submit"
                disabled={chatLoading || !chatInput.trim()}
                className="mt-2 w-full btn-primary disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
              >
                {chatLoading ? (
                  <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span> Sending...</>
                ) : (
                  "Send"
                )}
              </button>
            </form>

            {chatHistory.length > 0 && (
              <button
                type="button"
                onClick={() => setChatHistory([])}
                className="mt-2 w-full btn-ghost text-sm"
              >
                Clear Chat
              </button>
            )}
          </div>
        </div>
      </div>
    </PageShell>
  );
}
