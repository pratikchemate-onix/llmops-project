import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ChatMessage } from "@/types/chat";

export function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"}`}>
      <div className="max-w-[90%] sm:max-w-[80%]">
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm ${
            isUser
              ? "bg-foreground text-background"
              : "border border-black/10 bg-background"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-2 prose-pre:overflow-auto">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || "..."}</ReactMarkdown>
            </div>
          )}
        </div>

        {!isUser ? (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-foreground/70">
            <span className="rounded-full border border-black/10 bg-foreground/5 px-2 py-1">
              pipeline: {message.metadata?.pipelineExecuted || "unknown"}
            </span>
            <span className="rounded-full border border-black/10 bg-foreground/5 px-2 py-1">
              model: {message.metadata?.model || "unknown"}
            </span>
            <span className="rounded-full border border-black/10 bg-foreground/5 px-2 py-1">
              latency: {typeof message.metadata?.latencyMs === "number" ? `${message.metadata?.latencyMs?.toFixed(0)} ms` : "n/a"}
            </span>
            <span className="rounded-full border border-black/10 bg-foreground/5 px-2 py-1">
              RAG: {message.metadata?.taskDetection?.needs_rag ? "yes" : "no"}
            </span>
            <span className="rounded-full border border-black/10 bg-foreground/5 px-2 py-1">
              Agent: {message.metadata?.taskDetection?.needs_agent ? "yes" : "no"}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
