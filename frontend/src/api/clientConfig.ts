const TOKEN_KEY = "ragai-negsim.access-token";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    return;
  }
  localStorage.removeItem(TOKEN_KEY);
}

export function getAccessToken() {
  if (accessToken) {
    return accessToken;
  }
  accessToken = localStorage.getItem(TOKEN_KEY);
  return accessToken;
}

export function clearAccessToken() {
  setAccessToken(null);
}

export function getApiBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL ?? "";
}
