import type { AppId, PipelineType, TaskDetection, UsageMetrics } from "./api";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  // Only present on assistant messages (populated from InvokeResponse)
  metadata?: {
    requestId?: string;
    pipelineExecuted: PipelineType;
    taskDetection: TaskDetection;
    model: string;
    latencyMs: number;
    appId: AppId;
    usage?: UsageMetrics;
  };
}

export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  selectedApp: AppId;
  selectedModel: string;
}