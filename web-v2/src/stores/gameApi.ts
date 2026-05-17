// ═══════════════════════════════════════════════════════════════════════════
// LoveSupremacy Universe - Centralized API Client (Axios)
// All backend communication goes through this module
// ═══════════════════════════════════════════════════════════════════════════
import axios, { type AxiosInstance } from 'axios';

// ─── Types ────────────────────────────────────────────────────────────────

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  email?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  username: string;
}

export interface ChatRequest {
  message: string;
  mode?: 'scripted' | 'void';
  context?: string;
}

export interface ChatResponse {
  reply: string;
  mode: 'scripted' | 'void';
  metadata?: Record<string, unknown>;
}

export interface PlantRequest {
  plot_id: string;
  crop_type: string;
}

export interface HarvestRequest {
  plot_id: string;
}

export interface WaterRequest {
  plot_id: string;
}

export interface SyncRequest {
  actions: Array<{
    type: string;
    payload: Record<string, unknown>;
    timestamp: number;
  }>;
}

export interface WorldShiftRequest {
  target_world: 'scripted' | 'void';
}

// ─── Axios Instance ───────────────────────────────────────────────────────

const BASE_URL = import.meta.env.VITE_API_URL || '';

const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle auth errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      // Redirect to home if not already there
      if (window.location.pathname !== '/') {
        window.location.href = '/';
      }
    }
    return Promise.reject(error);
  }
);

// ─── API Functions ────────────────────────────────────────────────────────

/** Auth */
export const authApi = {
  login: (data: LoginRequest) =>
    apiClient.post<AuthResponse>('/api/login', data),

  register: (data: RegisterRequest) =>
    apiClient.post<AuthResponse>('/api/register', data),
};

/** User */
export const userApi = {
  getProfile: () => apiClient.get('/api/user/profile'),
};

/** Game State */
export const gameApi = {
  getState: () => apiClient.get('/api/game/state'),

  sync: (data: SyncRequest) => apiClient.post('/api/game/sync', data),
};

/** World Layer */
export const worldApi = {
  getState: () => apiClient.get('/api/world/state'),

  shift: (data: WorldShiftRequest) =>
    apiClient.post('/api/world/shift', data),
};

/** Chat */
export const chatApi = {
  send: (data: ChatRequest) =>
    apiClient.post<ChatResponse>('/api/chat', data),
};

/** Farm */
export const farmApi = {
  getFarm: () => apiClient.get('/api/game/farm'),

  plant: (data: PlantRequest) => apiClient.post('/api/game/plant', data),

  harvest: (data: HarvestRequest) =>
    apiClient.post('/api/game/harvest', data),

  water: (data: WaterRequest) => apiClient.post('/api/game/water', data),
};

// ─── Utility ──────────────────────────────────────────────────────────────

/** Store auth token after login/register */
export function setAuthToken(token: string): void {
  localStorage.setItem('auth_token', token);
}

/** Clear auth token on logout */
export function clearAuthToken(): void {
  localStorage.removeItem('auth_token');
}

/** Check if user is authenticated */
export function isAuthenticated(): boolean {
  return !!localStorage.getItem('auth_token');
}

export default apiClient;
