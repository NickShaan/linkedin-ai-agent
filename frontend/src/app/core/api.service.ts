import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private base = 'http://localhost:8000';

  async generate(topic: string, voice: string, count = 3): Promise<{ posts: string[] }> {
    const r = await fetch(`${this.base}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, voice, count })
    });
    if (!r.ok) throw new Error('API error');
    return r.json();
  }
}
