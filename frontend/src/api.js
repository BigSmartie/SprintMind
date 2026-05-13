import axios from 'axios';

export const API_BASE_URL = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000,
});

const parseMaybeJson = (text) => {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
};

const dispatchStreamEvent = (block, handlers) => {
  if (!block.trim()) return;

  let eventName = 'message';
  const dataLines = [];

  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) {
      eventName = line.slice(6).trim();
      continue;
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  const rawData = dataLines.join('\n');
  const parsedData = rawData ? parseMaybeJson(rawData) ?? { detail: rawData } : {};
  const handler = handlers?.[eventName];
  if (handler) {
    handler(parsedData);
  }
};

export const checkHealth = () => api.get('/health');
export const getProfile = () => api.get('/api/profile');
export const getTasks = () => api.get('/api/tasks');
export const getChatHistory = (sessionId = 'default') => api.get('/api/chat/history', { params: { session_id: sessionId } });
export const clearChat = (sessionId = 'default') => api.post('/api/chat/clear', { session_id: sessionId });
export const sendMessage = (message, sessionId = 'default', image_base64 = null) => {
  return api.post('/api/chat', { session_id: sessionId, message, image_base64 });
};

export const sendMessageStream = async (message, sessionId = 'default', image_base64 = null, handlers = {}) => {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      image_base64,
    }),
  });

  if (!response.ok || !response.body) {
    const detail = await response.text();
    const parsed = parseMaybeJson(detail);
    throw new Error(parsed?.detail || detail || '流式请求失败');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    let boundaryIndex = buffer.indexOf('\n\n');
    while (boundaryIndex !== -1) {
      const block = buffer.slice(0, boundaryIndex);
      buffer = buffer.slice(boundaryIndex + 2);
      dispatchStreamEvent(block, handlers);
      boundaryIndex = buffer.indexOf('\n\n');
    }

    if (done) {
      if (buffer.trim()) {
        dispatchStreamEvent(buffer, handlers);
      }
      break;
    }
  }
};

export const getDocuments = () => api.get('/api/knowledge');
export const deleteDocument = (docId) => api.delete(`/api/knowledge/${docId}`);
export const uploadDocument = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/api/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
};

export default api;
