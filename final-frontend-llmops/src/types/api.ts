// All types exactly match the backend POST /invoke contract

export type AppId = "mock_app" | "default_llm" | "rag_bot" | "code_agent";

export type PipelineType = "llm" | "rag" | "agent";

export interface InvokeRequest {
  app_id: AppId;
  user_input: string;
  model?: string;
}

export interface TaskDetection {
  needs_rag: boolean;
  needs_agent: boolean;
}

export interface UsageMetrics {
  prompt_tokens: number;
  completion_tokens: number;
  total_cost: number;
}

export interface InvokeResponse {
  request_id: string;
  app_id: AppId;
  user_input: string;
  config: Record<string, unknown>;
  task_detection: TaskDetection;
  pipeline_executed: PipelineType;
  output: string;
  latency_ms: number;
  usage: UsageMetrics;
}

export interface HealthResponse {
  status: string;
  message: string;
}

export interface ApiError {
  detail: string;
  status: number;
}