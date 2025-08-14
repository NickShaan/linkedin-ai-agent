import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { NgIf, NgFor } from '@angular/common';
import { ApiService } from '../../core/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [FormsModule, NgIf, NgFor],
  template: `
  <main class="container space-y-4">
    <h1 class="text-2xl font-semibold">LinkedIn Personal Branding Agent</h1>

    <input class="input" placeholder="Topic (e.g. GenAI evals for SMBs)" [(ngModel)]="topic" />
    <input class="input" placeholder="Brand voice" [(ngModel)]="voice" />

    <button class="btn btn-primary" (click)="generate()" [disabled]="loading">
      {{ loading ? 'Generating...' : 'Generate 3 Posts' }}
    </button>

    <section class="grid gap-3">
      <article *ngFor="let p of posts" class="card">{{ p }}</article>
    </section>
  </main>
  `
})
export class DashboardComponent {
  topic = '';
  voice = 'concise, practical, credible';
  posts: string[] = [];
  loading = false;

  constructor(private api: ApiService) {}

  async generate() {
    this.loading = true;
    try {
      const res = await this.api.generate(this.topic, this.voice, 3);
      this.posts = res.posts || [];
    } catch {
      alert('Failed to generate. Is backend running on :8000?');
    } finally {
      this.loading = false;
    }
  }
}
