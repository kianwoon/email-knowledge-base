import { apiClient } from './client';

// Type definitions for AutoGen API requests and responses
export interface AgentConfig {
  name: string;
  type: string;
  systemMessage: string;
}

export interface ChatHistoryItem {
  role: string;
  content: string;
  agent?: string;
}

export interface ChatResponse {
  messages: ChatHistoryItem[];
}

// Research workflow interfaces
export interface ResearchRequest {
  query: string;
  model_id?: string;
  max_rounds?: number;
  temperature?: number;
}

export interface ResearchResponse {
  messages: ChatHistoryItem[];
  summary: {
    query: string;
    summary: string;
    agent: string;
  };
}

// Code generation workflow interfaces
export interface CodeGenRequest {
  task_description: string;
  model_id?: string;
  max_rounds?: number;
  temperature?: number;
  work_dir?: string;
}

export interface CodeGenResponse {
  messages: ChatHistoryItem[];
  output_path: string;
}

// QA workflow interfaces
export interface QARequest {
  question: string;
  context: string[];
  model_id?: string;
  temperature?: number;
}

export interface QAResponse {
  question: string;
  answer: string;
  context_used: string[];
  confidence: string;
}

// Chat workflow interfaces
export interface ChatRequest {
  message: string;
  model_id?: string;
  temperature?: number;
  history?: ChatHistoryItem[];
  agents: AgentConfig[];
  max_rounds?: number;
}

// New hybrid chat interfaces
export interface HybridChatRequest {
  message: string;
  model_id?: string;
  temperature?: number;
  history?: ChatHistoryItem[];
  agents: AgentConfig[];
  max_rounds?: number;
  orchestration_type?: 'parallel' | 'sequential' | null;
  use_mcp_tools?: boolean;
}

/**
 * Run a research workflow with multiple agents collaborating to research a topic.
 */
export const sendResearch = async (
  query: string,
  options?: {
    modelId?: string;
    maxRounds?: number;
    temperature?: number;
  }
): Promise<ResearchResponse> => {
  const response = await apiClient.post<ResearchResponse>('/autogen/research', {
    query,
    model_id: options?.modelId,
    max_rounds: options?.maxRounds ?? 15,
    temperature: options?.temperature ?? 0.5
  });
  return response.data;
};

/**
 * Run a code generation workflow with multiple agents collaborating to generate code.
 */
export const sendCodeGen = async (
  taskDescription: string,
  options?: {
    modelId?: string;
    maxRounds?: number;
    temperature?: number;
    workDir?: string;
  }
): Promise<CodeGenResponse> => {
  const response = await apiClient.post<CodeGenResponse>('/autogen/code-generation', {
    task_description: taskDescription,
    model_id: options?.modelId,
    max_rounds: options?.maxRounds ?? 10,
    temperature: options?.temperature ?? 0.2,
    work_dir: options?.workDir ?? 'workspace'
  });
  return response.data;
};

/**
 * Run a question-answering workflow using the provided context.
 */
export const sendQA = async (
  question: string,
  context: string[],
  options?: {
    modelId?: string;
    temperature?: number;
  }
): Promise<QAResponse> => {
  const response = await apiClient.post<QAResponse>('/autogen/qa', {
    question,
    context,
    model_id: options?.modelId,
    temperature: options?.temperature ?? 0.3
  });
  return response.data;
};

/**
 * Run a flexible chat workflow with customizable agents.
 */
export const sendChat = async (
  message: string,
  agents: AgentConfig[],
  options?: {
    modelId?: string;
    temperature?: number;
    maxRounds?: number;
    conversationId?: string;
    history?: ChatHistoryItem[];
  }
): Promise<ChatResponse> => {
  const response = await apiClient.post<ChatResponse>(
    `/autogen/chat${options?.conversationId ? `?conversation_id=${options.conversationId}` : ''}`,
    {
      message,
      agents,
      model_id: options?.modelId,
      temperature: options?.temperature ?? 0.7,
      max_rounds: options?.maxRounds ?? 5,
      history: options?.history ?? []
    }
  );
  return response.data;
};

/**
 * Run a hybrid orchestration workflow with dynamic agent collaboration patterns.
 */
export const sendHybridChat = async (
  message: string,
  agents: AgentConfig[],
  options?: {
    modelId?: string;
    temperature?: number;
    maxRounds?: number;
    conversationId?: string;
    history?: ChatHistoryItem[];
    orchestrationType?: 'parallel' | 'sequential' | null;
    useMcpTools?: boolean;
  }
): Promise<ChatResponse> => {
  const response = await apiClient.post<ChatResponse>(
    `/autogen/hybrid-chat${options?.conversationId ? `?conversation_id=${options.conversationId}` : ''}`,
    {
      message,
      agents,
      model_id: options?.modelId,
      temperature: options?.temperature ?? 0.7,
      max_rounds: options?.maxRounds ?? 5,
      history: options?.history ?? [],
      orchestration_type: options?.orchestrationType ?? null,
      use_mcp_tools: options?.useMcpTools ?? true
    }
  );
  return response.data;
};

/**
 * Check if the AutoGen service is available.
 */
export const checkAutogenStatus = async (): Promise<{status: string; message: string}> => {
  const response = await apiClient.get<{status: string; message: string}>('/autogen/status');
  return response.data;
}; 