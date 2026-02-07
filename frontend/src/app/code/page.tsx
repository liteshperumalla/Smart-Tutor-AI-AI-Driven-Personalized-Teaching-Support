"use client";

import { useState, FormEvent } from "react";
import Link from "next/link";

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
import { Code2, Play, Sparkles, Bug, BookOpen, Send, Bot, Terminal } from "lucide-react";

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
    } catch (err) {
      setOutput(err instanceof Error ? err.message : "Execution failed");
      setOutputSuccess(false);
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
    } catch (err) {
      setGeneratedCode(`Error: ${err instanceof Error ? err.message : "Generation failed"}`);
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
    } catch (err) {
      setExplanation(`Error: ${err instanceof Error ? err.message : "Explanation failed"}`);
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
    } catch (err) {
      setDebugResult(`Error: ${err instanceof Error ? err.message : "Debugging failed"}`);
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
      const errorMessage: CodeChatMessage = {
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Chat failed"}`,
      };
      setChatHistory((prev) => [...prev, errorMessage]);
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
      <header className="relative overflow-hidden rounded-3xl p-12 animate-fade-in-down">
        <div className="relative z-10">
          <h1 className="font-display text-5xl font-bold text-zinc-900 dark:text-white">
            Coding Agent
          </h1>
          <p className="mt-4 text-lg text-zinc-600 max-w-2xl dark:text-zinc-400">
            Write, run, explain, and debug code with AI assistance powered by Qwen2.5 Coder
          </p>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Code Editor - 2/3 width */}
        <div className="lg:col-span-2 space-y-4">
          {/* Language Selector */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex items-center gap-4">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
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
                        ? "bg-zinc-900 text-white dark:bg-white dark:text-zinc-900"
                        : "border-zinc-200 text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                    }`}
                  >
                    {LANGUAGE_LABELS[lang]}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Code Editor */}
          <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <label className="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
              Write or paste your {LANGUAGE_LABELS[language]} code:
            </label>
            <textarea
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="h-56 w-full rounded-xl border border-zinc-200 bg-zinc-50 p-4 font-mono text-sm text-zinc-900 outline-none focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
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
              className="rounded-full bg-gradient-to-r from-emerald-600 to-green-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-600/30 transition hover:scale-105 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
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
              className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
            >
              {explaining ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent dark:border-white"></span> Explaining...</>
              ) : (
                "Explain Code"
              )}
            </button>
            <button
              type="button"
              onClick={handleDebugCode}
              disabled={debugging || !code.trim()}
              className="btn-secondary disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
            >
              {debugging ? (
                <><span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent dark:border-white"></span> Debugging...</>
              ) : (
                "Debug Code"
              )}
            </button>
          </div>

          {/* Generate Code Input */}
          {showGenerateInput && (
            <form
              onSubmit={handleGenerateCode}
              className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
            >
              <label className="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Describe what you want to code:
              </label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={generatePrompt}
                  onChange={(e) => setGeneratePrompt(e.target.value)}
                  placeholder="e.g., A function to calculate fibonacci numbers"
                  className="flex-1 rounded-xl border border-zinc-200 px-4 py-2 text-sm text-zinc-900 outline-none focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
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
            <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Output:</p>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    outputSuccess
                      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                      : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
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
            <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Generated Code:
                </p>
                {!generatedCode.startsWith("Error:") && (
                  <button
                    type="button"
                    onClick={useGeneratedCode}
                    className="rounded-full bg-blue-600 px-4 py-1 text-xs font-medium text-white transition hover:bg-blue-700"
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
            <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <p className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Explanation:
              </p>
              <div className="prose prose-sm max-w-none rounded-xl bg-zinc-50 p-4 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                <pre className="whitespace-pre-wrap font-sans">{explanation}</pre>
              </div>
            </div>
          )}

          {/* Debug Result Section */}
          {debugResult && (
            <div className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <p className="mb-2 text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Debug Analysis:
              </p>
              <div className="prose prose-sm max-w-none rounded-xl bg-zinc-50 p-4 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                <pre className="whitespace-pre-wrap font-sans">{debugResult}</pre>
              </div>
            </div>
          )}
        </div>

        {/* Chat Sidebar - 1/3 width */}
        <div className="lg:col-span-1">
          <div className="sticky top-4 rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">
              Chat with Coding LLM
            </h2>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              Ask questions about programming, get help with code
            </p>

            {/* Chat History */}
            <div className="mt-4 h-80 overflow-y-auto rounded-xl border border-zinc-100 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-800/50">
              {chatHistory.length === 0 && (
                <p className="text-center text-xs text-zinc-500 dark:text-zinc-400">
                  Start a conversation...
                </p>
              )}
              {chatHistory.slice(-10).map((msg, index) => (
                <div
                  key={index}
                  className={`mb-3 rounded-xl p-3 text-sm ${
                    msg.role === "user"
                      ? "ml-4 bg-blue-100 text-blue-900 dark:bg-blue-900/30 dark:text-blue-100"
                      : "mr-4 bg-zinc-200 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-100"
                  }`}
                >
                  <p className="mb-1 text-xs font-semibold opacity-70">
                    {msg.role === "user" ? "You" : "LLM"}
                  </p>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
              ))}
              {chatLoading && (
                <div className="mr-4 rounded-xl bg-zinc-200 p-3 text-sm dark:bg-zinc-700">
                  <p className="text-xs font-semibold opacity-70">LLM</p>
                  <p className="animate-pulse text-zinc-600 dark:text-zinc-300">Thinking...</p>
                </div>
              )}
            </div>

            {/* Chat Input */}
            <form onSubmit={handleChatSubmit} className="mt-3">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Type your message..."
                className="h-20 w-full rounded-xl border border-zinc-200 p-3 text-sm text-zinc-900 outline-none focus:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
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
