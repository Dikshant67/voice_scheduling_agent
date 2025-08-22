// types/google.ts
export interface GoogleTokenResponse {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  token_type: string;
  scope: string;
}

export interface GoogleUserInfo {
  email: string;
  name: string;
  picture: string;
  sub: string;
}

export interface CalendarAuthState {
  isAuthenticated: boolean;
  token: GoogleTokenResponse | null;
  userInfo: GoogleUserInfo | null;
  error: string | null;
}

// Extend the Window interface to include gapi
declare global {
  interface Window {
    gapi: any;
    google: any;
  }
}
