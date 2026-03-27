"use client";
import { useEffect, useRef, useState } from "react";
import { useChat } from "@/hooks/useChat";
import { AppId } from "@/types/api";
import { submitFeedback } from "@/lib/api";

const APP_OPTIONS: { id: AppId; label: string }[] = [
  { id: "mock_app", label: "Mock App" },
  { id: "default_llm", label: "General Assistant" },
  { id: "rag_bot", label: "RAG Bot" },
  { id: "code_agent", label: "Code Agent" },
];

const MODEL_OPTIONS = [
  { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
  { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
  { id: "gemini-3-flash-preview", label: "Gemini 3 Flash Preview" },
  { id: "gemini-3-pro-preview", label: "Gemini 3 Pro Preview" },
  { id: "gemini-3.1-flash-preview", label: "Gemini 3.1 Flash Preview" },
  { id: "gemini-3.1-pro-preview", label: "Gemini 3.1 Pro Preview" },
  { id: "gemini-3.1-flash-lite-preview", label: "Gemini 3.1 Flash Lite Preview" },
  { id: "claude-3-5-sonnet", label: "Claude 3.5 Sonnet" },
  { id: "claude-3-opus", label: "Claude 3 Opus" },
  { id: "gpt-4o", label: "GPT-4o" },
  { id: "gpt-4o-mini", label: "GPT-4o Mini" },
  { id: "grok-2-latest", label: "Grok 2 (Latest)" },
  { id: "llama-3.3-70b-versatile", label: "Llama 3.3 (Groq)" },
];

export default function ChatPage() {
  const {
    messages,
    isLoading,
    error,
    selectedApp,
    selectedModel,
    setSelectedApp,
    setSelectedModel,
    sendMessage,
    clearMessages,
  } = useChat();

      const bottomRef = useRef<HTMLDivElement>(null);
      const [inputValue, setInputValue] = useState("");
      const [feedbackStatus, setFeedbackStatus] = useState<Record<string, "up" | "down">>({});
  
      const handleFeedback = async (requestId: string, score: number) => {
        try {
          await submitFeedback(requestId, score);
          setFeedbackStatus((prev) => ({ ...prev, [requestId]: score > 0 ? "up" : "down" }));
        } catch (err) {
          console.error("Failed to submit feedback", err);
        }
      };
  
      // Auto-scroll to bottom  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;
    sendMessage(inputValue);
    setInputValue("");
  };

  return (
    // Main Container - Dark Navy Theme
    <div className="flex flex-col h-screen bg-[#020617] text-gray-100 font-sans">
      
      {/* 1. Header (Fixed Top) */}
      <header className="flex-none bg-[#0f172a] border-b border-gray-800 px-4 py-3 shadow-md z-20">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/20">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h1 className="text-lg font-bold tracking-tight text-white">
              LLMOps <span className="text-blue-500">Chat</span>
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={selectedApp}
              onChange={(e) => setSelectedApp(e.target.value as AppId)}
              className="bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:outline-none transition-shadow"
              disabled={isLoading}
            >
              {APP_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>

            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-gray-800 border border-gray-700 text-sm text-gray-200 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-blue-500 focus:outline-none transition-shadow"
              disabled={isLoading}
            >
              {MODEL_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>
            
            <button
              onClick={clearMessages}
              disabled={messages.length === 0 || isLoading}
              className="p-2 text-gray-400 hover:text-red-400 hover:bg-gray-800 rounded-lg transition-colors disabled:opacity-50"
              title="Clear Conversation"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* 2. Chat Container (Scrollable Middle) */}
      <main className="flex-1 overflow-y-auto scroll-smooth">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
          
          {messages.length === 0 && (
            <div className="h-[60vh] flex flex-col items-center justify-center text-center space-y-4 opacity-50">
              <div className="w-16 h-16 bg-gray-800 rounded-2xl flex items-center justify-center mb-2">
                <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <h3 className="text-xl font-medium text-gray-300">Welcome to LLMOps</h3>
              <p className="text-sm text-gray-500 max-w-sm">
                Select an application from the top right and start a conversation.
              </p>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="bg-red-900/30 border border-red-800 rounded-xl p-4 flex items-start gap-3">
              <svg className="w-5 h-5 text-red-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <h4 className="text-sm font-semibold text-red-400">Error</h4>
                <p className="text-sm text-red-200/80 mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* Message List */}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.role === "user" ? "items-end" : "items-start"
              }`}
            >
              {/* Message Bubble */}
              <div
                className={`max-w-[85%] sm:max-w-[75%] px-5 py-3 shadow-md text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-2xl rounded-br-none"
                    : "bg-gray-800 text-gray-100 rounded-2xl rounded-bl-none border border-gray-700"
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
              </div>

              {/* Assistant Metadata */}
              {msg.role === "assistant" && msg.metadata && (
                <div className="mt-2 ml-2 flex flex-wrap gap-2 items-center">
                  {/* Pipeline Badge */}
                  <span className="px-2 py-0.5 text-[10px] font-semibold tracking-wide uppercase rounded-full bg-purple-600 text-white shadow-sm">
                    {msg.metadata.pipelineExecuted}
                  </span>
                  
                  {/* Model Badge */}
                  <span className="px-2 py-0.5 text-[10px] rounded-full bg-gray-700 text-gray-300 border border-gray-600">
                    {msg.metadata.model}
                  </span>

                                      {/* Latency Badge */}
                                      <span className="px-2 py-0.5 text-[10px] rounded-full bg-green-900/50 text-green-400 border border-green-800">
                                        {msg.metadata.latencyMs.toFixed(0)}ms
                                      </span>
                  
                                      {/* Usage & Cost Badges */}
                                      {msg.metadata.usage && (
                                        <>
                                          <span className="px-2 py-0.5 text-[10px] rounded-full bg-blue-900/50 text-blue-400 border border-blue-800">
                                            {msg.metadata.usage.prompt_tokens + msg.metadata.usage.completion_tokens} tokens
                                          </span>
                                          <span className="px-2 py-0.5 text-[10px] rounded-full bg-amber-900/50 text-amber-400 border border-amber-800">
                                            ${msg.metadata.usage.total_cost.toFixed(6)}
                                          </span>
                                        </>
                                      )}
                  
                                      {/* Task Chips */}                  {msg.metadata.taskDetection.needs_rag && (
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-yellow-600/20 text-yellow-500 border border-yellow-600/40">
                      RAG
                    </span>
                  )}
                                      {msg.metadata.taskDetection.needs_agent && (
                                        <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-red-600/20 text-red-500 border border-red-600/40">
                                          AGENT
                                        </span>
                                      )}
                  
                                      <span className="text-[10px] text-gray-600 ml-1">
                                        {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                      </span>
                  
                                      {/* Feedback Buttons */}
                                      {msg.metadata.requestId && (
                                        <div className="flex items-center gap-1 ml-auto">
                                          <button
                                            onClick={() => handleFeedback(msg.metadata!.requestId!, 1)}
                                            disabled={!!feedbackStatus[msg.metadata.requestId]}
                                            className={`p-1 rounded-md transition-colors ${
                                              feedbackStatus[msg.metadata.requestId] === "up"
                                                ? "text-green-500 bg-green-500/10"
                                                : "text-gray-500 hover:text-green-400 hover:bg-gray-800"
                                            }`}
                                            title="Helpful"
                                          >
                                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                                            </svg>
                                          </button>
                                          <button
                                            onClick={() => handleFeedback(msg.metadata!.requestId!, -1)}
                                            disabled={!!feedbackStatus[msg.metadata.requestId]}
                                            className={`p-1 rounded-md transition-colors ${
                                              feedbackStatus[msg.metadata.requestId] === "down"
                                                ? "text-red-500 bg-red-500/10"
                                                : "text-gray-500 hover:text-red-400 hover:bg-gray-800"
                                            }`}
                                            title="Not helpful"
                                          >
                                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
                                            </svg>
                                          </button>
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              ))}
          {/* Loading Indicator */}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 border border-gray-700 rounded-2xl rounded-bl-none px-4 py-3 shadow-md flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce"></span>
              </div>
            </div>
          )}
          
          <div ref={bottomRef} />
        </div>
      </main>

      {/* 3. Input Area (Fixed Bottom) */}
      <footer className="flex-none bg-[#0f172a] border-t border-gray-800 p-4">
        <div className="max-w-3xl mx-auto">
          <form onSubmit={handleSubmit} className="relative flex items-end gap-2 bg-gray-800/50 rounded-xl border border-gray-700 shadow-inner p-2 focus-within:ring-2 focus-within:ring-blue-600/50 focus-within:border-blue-500 transition-all">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Message ${APP_OPTIONS.find(o => o.id === selectedApp)?.label ?? selectedApp}...`}
              className="w-full bg-transparent text-gray-100 placeholder-gray-500 text-sm px-3 py-2.5 max-h-32 min-h-[44px] focus:outline-none resize-none overflow-y-auto"
              rows={1}
              style={{ minHeight: '44px' }} // fallback
            />
            
            <button
              type="submit"
              disabled={!inputValue.trim() || isLoading}
              className="p-2 mb-0.5 bg-blue-600 text-white rounded-lg hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed transition-all shadow-lg shadow-blue-900/20"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </form>
          <p className="text-center text-[10px] text-gray-500 mt-2">
            LLM can make mistakes. Verify important information.
          </p>
        </div>
      </footer>
    </div>
  );
}
