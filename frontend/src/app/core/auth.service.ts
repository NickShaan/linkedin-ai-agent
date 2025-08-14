import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';

export interface AuthResponse {
  access_token: string;
  token_type: string;
  message?: string; // <-- add message so TS knows it exists
}
export interface GenOut {
  post_id: number;
  text: string;
  format: 'short_post' | 'article' | 'carousel';
}


export interface GenResponse { post_id: number; text: string; format: string; }

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private base = '/api'; // using the Angular proxy
  isAuthed() { return !!this.getToken(); }

  login(email: string, password: string) {
    return this.http.post<AuthResponse>(`${this.base}/auth/login`, { email, password });
  }

  signup(body: {
    name: string; email: string; country_code: string; mobile: string; linkedin_id: string; password: string;
  }) {
    return this.http.post<AuthResponse>(`${this.base}/auth/signup`, body);
  }

  
  me() {
  return this.http.get<{ id: number; name: string; email: string; onboarded: boolean }>(`${this.base}/auth/me`);
  }


  contentGenerate(body: { topic: string; format: 'short_post'|'article'|'carousel' }) {
  const token = this.getToken();
  const headers = token ? new HttpHeaders({ Authorization: `Bearer ${token}` }) : undefined;
  return this.http.post<GenResponse>(`${this.base}/content/generate`, body, { headers });
  }
 // auth.service.ts
  getLinkedInStartUrl() {
    return this.http.get<{url: string}>(`${this.base}/oauth/linkedin/start-url`);
  }
  getLinkedInStartPublic() {
    return this.http.get<{url: string}>(`${this.base}/oauth/linkedin/start-public`);
  }
   getSummary() {
    return this.http.get<any>(`${this.base}/profile/summary`);
  }
  uploadResume(file: File) {
    const fd = new FormData();
    fd.append('file', file);
    return this.http.post<any>(`${this.base}/profile/upload-resume`, fd);
  }

  getProfile() {
    return this.http.get<{
      user_id: number; headline: string|null; bio: string|null;
      industries: string[]; goals: string|null; tone: string[]; keywords: string[];
    }>(`${this.base}/profile`);
  }
  
  

  saveProfile(body: {
    headline?: string|null;
    bio?: string|null;
    industries: string[];
    goals?: string|null;
    tone: string[];
    keywords: string[];
  }) {
    return this.http.put(`${this.base}/profile`, body);
  }

  
   generatePost(payload: {
    topic?: string | null;
    format?: 'short_post'|'article'|'carousel';
    model?: string;
    emojis?: boolean;
    suggest_image?: boolean;
    tone?: string[];
    kind?: string | null;
    publish_now?: boolean;
    visibility?: 'PUBLIC' | 'CONNECTIONS';
  }) {
    return this.http.post<{ post_id: number; text: string; format: string }>(
      `/api/content/generate`, payload
    );
  }

  schedulePost(body: { post_id: number; scheduled_at: string; provider?: string }) {
    return this.http.post<{ message: string; scheduled_at: string }>(
      `/api/content/schedule`, body
    );
  }

  publishNow(body: { post_id: number; visibility?: 'PUBLIC'|'CONNECTIONS' }) {
    return this.http.post<{ message: string; linkedin_urn?: string }>(
      `/api/content/publish-now`, body
    );
  }




  setToken(t: string) { localStorage.setItem('token', t); }
  getToken() { return localStorage.getItem('token') || ''; }
  clear() { localStorage.removeItem('token'); }
}
