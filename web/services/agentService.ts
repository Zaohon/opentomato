import { EnergyData, SystemMode } from "../types";

type AgentStreamEvent = {
  type?: string;
  status?: string;
  message?: string;
  text?: string;
  phase?: string;
  response?: string;
  session_id?: string;
  path?: string;
  agent?: string;
  tool?: string;
  round?: number;
};

type UploadResourceResponse = {
  accepted?: boolean;
  ingest_id?: string;
  filename?: string;
  bytes?: number;
  dropbox_path?: string;
  target_uri?: string;
  status?: string;
};

type UploadResourcePayload = {
  file: File;
  uploader?: string;
};

export type ChatHistoryItem = {
  role: string;
  content: string;
};

export type Soul = {
  name: string;
  description: string;
};

export type SoulsResult = {
  souls: Soul[];
  defaultSoul: string;
};

type SoulsResponse = {
  default?: string;
  count?: number;
  souls?: Record<string, string>;
};

type ChatHistoryResponse = {
  user_id?: string;
  session_id?: string;
  history?: ChatHistoryItem[];
  summary?: string;
  updated_at?: number;
};

type ResetChatResponse = {
  user_id?: string;
  previous_session_id?: string;
  session_id?: string;
  cleared?: boolean;
  commit_ok?: boolean;
  extracted_count?: number;
  warning?: string;
};

export type SuggestionResponse = {
  user_id?: string;
  brief?: string;
  detail?: string;
};

type VoiceResponse = {
  text?: string;
  model?: string;
};

// Force same-origin API path in production to avoid cross-gateway mismatch (401/timeout).
// Dev still works via Vite proxy on /api/v1.
const AGENT_API_BASE = "/api/v1";
const DEFAULT_STATION_ID = "1000";

const buildUrl = (path: string) => {
  const normalizedBase = AGENT_API_BASE.endsWith("/") ? AGENT_API_BASE.slice(0, -1) : AGENT_API_BASE;
  return `${normalizedBase}${path.startsWith("/") ? path : `/${path}`}`;
};

const normalizeBackendUserId = (userId: string): string => {
  const trimmed = String(userId || "").trim();
  if (!trimmed) return "";
  if (/^\d+$/.test(trimmed)) {
    return trimmed.padStart(3, "0");
  }
  return trimmed;
};

export const loadChatHistory = async (userId: string): Promise<ChatHistoryResponse> => {
  const normalizedUserId = normalizeBackendUserId(userId);
  if (!normalizedUserId) {
    return { user_id: "", session_id: "", history: [] };
  }

  try {
    const url = new URL(buildUrl("/chat/history"), window.location.origin);
    url.searchParams.set("user_id", normalizedUserId);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000); // 30 second timeout

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      throw new Error(`History request failed: ${response.status}`);
    }

    const data = (await response.json()) as ChatHistoryResponse;
    return {
      user_id: normalizedUserId,
      session_id: data.session_id || "",
      history: Array.isArray(data.history) ? data.history : [],
      summary: data.summary || "",
      updated_at: data.updated_at || 0,
    };
  } catch (error) {
    console.error("Failed to load chat history:", error);
    return {
      user_id: normalizedUserId,
      session_id: "",
      history: [],
      summary: "",
      updated_at: 0,
    };
  }
};

export const resetChatConversation = async (userId: string): Promise<ResetChatResponse> => {
  const normalizedUserId = normalizeBackendUserId(userId);
  if (!normalizedUserId) {
    return {
      user_id: "",
      previous_session_id: "",
      session_id: "",
      cleared: false,
      commit_ok: false,
      extracted_count: 0,
      warning: "missing_user_id",
    };
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000); // 30 second timeout

    const response = await fetch(buildUrl("/chat/reset"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: normalizedUserId }),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      throw new Error(`Reset request failed: ${response.status}`);
    }

    const data = (await response.json()) as ResetChatResponse;
    return {
      user_id: normalizedUserId,
      previous_session_id: data.previous_session_id || "",
      session_id: data.session_id || "",
      cleared: Boolean(data.cleared),
      commit_ok: Boolean(data.commit_ok),
      extracted_count: data.extracted_count || 0,
      warning: data.warning || "",
    };
  } catch (error) {
    console.error("Failed to reset chat conversation:", error);
    return {
      user_id: normalizedUserId,
      previous_session_id: "",
      session_id: "",
      cleared: false,
      commit_ok: false,
      extracted_count: 0,
      warning: "reset_request_failed",
    };
  }
};

export const fetchSouls = async (): Promise<SoulsResult> => {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000); // 30 second timeout

    const response = await fetch(buildUrl("/souls"), {
      method: "GET",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!response.ok) {
      throw new Error(`Souls request failed: ${response.status}`);
    }

    const data = (await response.json()) as SoulsResponse;
    
    if (data.souls && typeof data.souls === "object") {
      const souls = Object.entries(data.souls).map(([name, description]) => ({
        name,
        description: typeof description === "string" ? description : String(description),
      }));
      const defaultSoul = String(data.default || "").trim();
      return {
        souls,
        defaultSoul: defaultSoul && souls.some((soul) => soul.name === defaultSoul)
          ? defaultSoul
          : souls[0]?.name || "",
      };
    }

    return { souls: [], defaultSoul: "" };
  } catch (error) {
    console.error("Failed to fetch souls:", error);
    return { souls: [], defaultSoul: "" };
  }
};

export const sendChatMessage = async (
  message: string,
  userId: string,
  soul?: string,
): Promise<string> => {
  return sendChatMessageStream(message, userId, soul);
};

export const sendChatMessageStream = async (
  message: string,
  userId: string,
  soul?: string,
  onEvent?: (event: AgentStreamEvent) => void,
): Promise<string> => {
  const normalizedUserId = normalizeBackendUserId(userId);
  if (!normalizedUserId) {
    return "Please select a user first.";
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);

  try {
    const requestBody: Record<string, string> = {
      message,
      user_id: normalizedUserId,
      station_id: DEFAULT_STATION_ID,
    };
    
    if (soul) {
      requestBody.soul = soul;
    }

    const response = await fetch(buildUrl("/chat/stream"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Chat request failed: ${response.status}`);
    }

    if (!response.body) {
      throw new Error("Chat stream has no response body.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalResponse = "";

    const extractNextFrame = (): string | null => {
      const match = buffer.match(/\r?\n\r?\n/);
      if (!match || typeof match.index !== "number") return null;
      const frame = buffer.slice(0, match.index).trim();
      buffer = buffer.slice(match.index + match[0].length);
      return frame || null;
    };

    const processFrame = (frame: string) => {
      const lines = frame.split("\n");
      const dataLines: string[] = [];
      for (const rawLine of lines) {
        const line = rawLine.trimEnd();
        if (line.startsWith("data:")) {
          dataLines.push(line.slice("data:".length).trim());
        }
      }
      if (!dataLines.length) return;
      let payload: AgentStreamEvent;
      try {
        payload = JSON.parse(dataLines.join("\n")) as AgentStreamEvent;
      } catch {
        payload = { type: "state", message: dataLines.join("\n") };
      }
      if (!payload.type) payload.type = "state";
      onEvent?.(payload);
      if (payload.type === "result" && typeof payload.response === "string") {
        finalResponse = payload.response;
      }
      if (payload.type === "error") {
        throw new Error(payload.message || "chat_stream_error");
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      while (true) {
        const frame = extractNextFrame();
        if (!frame) break;
        processFrame(frame);
      }
      if (done) break;
    }

    if (!finalResponse) {
      const fallback = buffer.trim();
      if (fallback) processFrame(fallback);
    }
    return finalResponse || "No response was returned.";
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      console.error("Chat stream timed out after 60 seconds");
      return "The request timed out. The agent backend may be slow or overloaded. Please try again in a moment.";
    }
    console.error("Failed to call agent chat stream API:", error);
    return "Unable to reach the agent backend right now.";
  } finally {
    clearTimeout(timeout);
  }
};

export const getFeSolarAdvice = async (
  currentData: EnergyData,
  mode: SystemMode,
  userId: string
): Promise<string> => {
  const prompt = [
    "You are the FeSolar home energy assistant.",
    `Current mode: ${mode}`,
    `PV power: ${currentData.solarPower} kW`,
    `Grid power: ${currentData.gridPower} kW (positive=import, negative=export)`,
    `Battery power: ${currentData.batteryPower} kW`,
    `Battery level: ${currentData.batteryLevel}%`,
    `Home load: ${currentData.homeLoad} kW`,
    `EV power: ${currentData.evPower} kW`,
    "Reply in concise Simplified Chinese within two sentences, focusing on the current action and expected benefit.",
  ].join("\n");

  return sendChatMessage(prompt, userId);
};

export const generateSuggestion = async (userId: string): Promise<SuggestionResponse> => {
  const normalizedUserId = normalizeBackendUserId(userId);
  if (!normalizedUserId) {
    throw new Error("user_id is required");
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 180000);

  try {
    const response = await fetch(buildUrl("/generate_suggestion"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: normalizedUserId }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Generate suggestion failed: ${response.status} ${text.slice(0, 200)}`);
    }

    return (await response.json()) as SuggestionResponse;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Generate suggestion timeout after 180 seconds");
    }
    throw error instanceof Error ? error : new Error("Generate suggestion request failed");
  } finally {
    clearTimeout(timeout);
  }
};

export const transcribeVoice = async (
  audioBase64OrDataUri: string,
  audioMimeType = "audio/webm",
): Promise<string> => {
  const payload = {
    audio_base64: String(audioBase64OrDataUri || "").trim(),
    audio_mime_type: String(audioMimeType || "audio/webm"),
  };

  if (!payload.audio_base64) {
    throw new Error("audio_base64 is required");
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);

  try {
    const response = await fetch(buildUrl("/voice"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Voice request failed: ${response.status} ${text.slice(0, 200)}`);
    }

    const data = (await response.json()) as VoiceResponse;
    return String(data.text || "").trim();
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Voice request timeout after 120 seconds");
    }
    throw error instanceof Error ? error : new Error("Voice request failed");
  } finally {
    clearTimeout(timeout);
  }
};

export const uploadResourceFile = async (payload: UploadResourcePayload): Promise<UploadResourceResponse> => {
  if (!(payload.file instanceof File)) {
    throw new Error('file is required');
  }

  const formData = new FormData();
  formData.append('file', payload.file);
  formData.append('uploader', (payload.uploader || 'web-ui').trim() || 'web-ui');

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);

  try {
    const response = await fetch(buildUrl('/resources/upload'), {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Upload failed: ${response.status} ${text.slice(0, 200)}`);
    }

    return (await response.json()) as UploadResourceResponse;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Upload timeout after 120 seconds');
    }
    throw error instanceof Error ? error : new Error('Upload failed');
  } finally {
    clearTimeout(timeout);
  }
};
