"use client";
import { useState, useCallback } from "react";
import { invoke } from "@/lib/api";
import type { AppId } from "@/types/api";
import type { ChatMessage, ChatState } from "@/types/chat";

function makeId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function useChat() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    error: null,
    selectedApp: "default_llm",
    selectedModel: "gemini-2.5-flash",
  });

  const setSelectedApp = useCallback((app: AppId) => {
    setState((prev) => ({ ...prev, selectedApp: app, error: null }));
  }, []);

  const setSelectedModel = useCallback((model: string) => {
    setState((prev) => ({ ...prev, selectedModel: model, error: null }));
  }, []);

  const sendMessage = useCallback(
    async (userInput: string) => {
      if (!userInput.trim()) return;

      const userMsg: ChatMessage = {
        id: makeId(),
        role: "user",
        content: userInput.trim(),
        timestamp: new Date(),
      };

      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMsg],
        isLoading: true,
        error: null,
      }));

      try {
        const response = await invoke(state.selectedApp, userInput.trim(), state.selectedModel);

        const model =
          typeof response.config?.model === "string"
            ? response.config.model
            : "unknown";

        const assistantMsg: ChatMessage = {
          id: makeId(),
          role: "assistant",
          content: response.output,
          timestamp: new Date(),
          metadata: {
            requestId: response.request_id,
            pipelineExecuted: response.pipeline_executed,
            taskDetection: response.task_detection,
            model,
            latencyMs: response.latency_ms,
            appId: response.app_id,
            usage: response.usage,
          },
        };

        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, assistantMsg],
          isLoading: false,
        }));

        // Save last invoke to localStorage for admin diagnostics
        if (typeof window !== "undefined") {
          localStorage.setItem("llmops_last_invoke", JSON.stringify({
            pipeline_executed: response.pipeline_executed,
            task_detection: response.task_detection,
            latency_ms: response.latency_ms,
            model,
            timestamp: new Date().toISOString(),
          }));
        }
      } catch (err) {
        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: err instanceof Error ? err.message : "Unknown error occurred",
        }));
      }
    },
    [state.selectedApp, state.selectedModel]
  );

  const clearMessages = useCallback(() => {
    setState((prev) => ({ ...prev, messages: [], error: null }));
  }, []);

  return {
    messages: state.messages,
    isLoading: state.isLoading,
    error: state.error,
    selectedApp: state.selectedApp,
    selectedModel: state.selectedModel,
    setSelectedApp,
    setSelectedModel,
    sendMessage,
    clearMessages,
  };
}