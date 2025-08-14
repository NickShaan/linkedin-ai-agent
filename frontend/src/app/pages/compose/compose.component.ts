// frontend/src/app/pages/compose/compose.component.ts
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormControl, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/** Keep the response type in THIS file (no separate types.ts needed) */
type GenOut = {
  post_id: number;
  text: string;
  format: 'short_post' | 'article' | 'carousel';
};

@Component({
  selector: 'app-compose',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './compose.component.html',
})
export class ComposeComponent {
  // ---- Form ----
  form = new FormGroup({
    date: new FormControl<string>('', { nonNullable: true, validators: [Validators.required] }),
    time: new FormControl<string>('', { nonNullable: true, validators: [Validators.required] }),
    topic: new FormControl<string | null>(null),
    format: new FormControl<'short_post' | 'article' | 'carousel'>('short_post', { nonNullable: true }),
    model: new FormControl<string>('gemini-1.5-flash', { nonNullable: true }),
    emojis: new FormControl<boolean>(true, { nonNullable: true }),
    suggestImage: new FormControl<boolean>(false, { nonNullable: true }),
    toneCSV: new FormControl<string>(''),
    kind: new FormControl<string | null>(null),

    // New controls for immediate posting
    postNow: new FormControl<boolean>(false, { nonNullable: true }),
    visibility: new FormControl<'PUBLIC' | 'CONNECTIONS'>('PUBLIC', { nonNullable: true }),
  });

  // ---- UI state ----
  loading = false;
  saving = false;
  error = '';
  success = '';
  schedError = '';

  // ---- Data state ----
  draft: GenOut | null = null;
  lastDraft: { when: string; text: string } | null = null;

  constructor(private http: HttpClient) {}

  // --- Helpers ---
  private toneCSVtoArray(v: string | null | undefined): string[] {
    return (v || '')
      .split(',')
      .map(s => s.trim())
      .filter(Boolean);
  }

  private buildGeneratePayload(publishNow: boolean) {
    const tone = this.toneCSVtoArray(this.form.value.toneCSV || '');
    return {
      topic: this.form.value.topic ?? null,
      format: this.form.value.format ?? 'short_post',
      model: this.form.value.model ?? 'gemini-1.5-flash',
      emojis: this.form.value.emojis ?? true,
      // map camelCase -> snake_case for backend
      suggest_image: this.form.value.suggestImage ?? false,
      tone,
      kind: this.form.value.kind ?? null,
      publish_now: publishNow,
      visibility: this.form.value.visibility ?? 'PUBLIC',
    };
  }

  /** Accepts both (ngSubmit)="generate()" and (click)="generate('postNow')" */
  async generate(mode: 'draft' | 'postNow' = 'draft') {
    this.loading = true;
    this.error = '';
    this.success = '';
    try {
      const publishNow = mode === 'postNow' || this.form.value.postNow === true;
      const payload = this.buildGeneratePayload(publishNow);

      // Typed response so we don't get "unknown" errors
      const res = await firstValueFrom(
        this.http.post<GenOut>('/api/content/generate', payload)
      );

      this.draft = res;
      this.lastDraft = { when: new Date().toLocaleString(), text: res.text };

      this.success = publishNow ? 'Posted to LinkedIn ✅' : 'Draft generated ✅';
    } catch (e: any) {
      this.error = e?.error?.detail || e?.message || 'Failed to generate';
    } finally {
      this.loading = false;
    }
  }

  private combineDateTimeToISO(dateStr: string, timeStr: string): string {
    // interpret input as local time, then convert to UTC ISO
    const [h, m] = timeStr.split(':').map(Number);
    const d = new Date(dateStr);
    d.setHours(h, m ?? 0, 0, 0);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString();
  }

  async schedule() {
    if (!this.draft) return;
    this.saving = true;
    this.schedError = '';
    this.success = '';
    try {
      const date = this.form.controls.date.value!;
      const time = this.form.controls.time.value!;
      const iso = this.combineDateTimeToISO(date, time);

      await firstValueFrom(
        this.http.post<{ message: string; scheduled_at: string }>(
          '/api/content/schedule',
          { post_id: this.draft.post_id, scheduled_at: iso, provider: 'linkedin' }
        )
      );
      this.success = 'Scheduled ✅';
    } catch (e: any) {
      this.schedError = e?.error?.detail || e?.message || 'Failed to schedule';
    } finally {
      this.saving = false;
    }
  }

  copy() {
    if (!this.draft) return;
    navigator.clipboard.writeText(this.draft.text);
    this.success = 'Copied!';
  }
}
