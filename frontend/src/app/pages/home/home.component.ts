import { Component, OnInit } from '@angular/core';
import { NgIf, NgFor, AsyncPipe, NgClass } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { catchError, of, Observable } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../../core/auth.service';

type Me = { id: number; name: string; email: string } | null;

type ProfileSummary = {
  background: {
    name: string | null;
    headline: string | null;
    industries: string[];
    keywords: string[];
    tone: string[];
    li_id: string | null;
    has_resume: boolean;
    picture_url: string | null;
    li_email: string | null;
  };
  prompt_seed: string;
} | null;

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [NgIf, NgFor, NgClass, AsyncPipe, RouterLink],
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.css']
})
export class HomeComponent implements OnInit {
  me$!: Observable<Me>;
  summary$!: Observable<ProfileSummary>;

  // résumé upload UX
  uploading = false;
  uploadError = '';
  uploadOk = '';

  constructor(
    private http: HttpClient,
    private auth: AuthService,
    private route: ActivatedRoute,
    private router: Router
  ) {}

  ngOnInit(): void {
    // in case token arrives as #token=...
    const hash = window.location.hash || '';
    if (hash.startsWith('#token=')) {
      const token = decodeURIComponent(hash.slice('#token='.length));
      this.auth.setToken(token);
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }

    this.me$ = this.auth.isAuthed()
      ? this.auth.me().pipe(catchError(() => of(null)))
      : of(null);

    this.loadSummary();
  }

  private loadSummary() {
    this.summary$ = this.auth.isAuthed()
      ? this.auth.getSummary().pipe(catchError(() => of(null)))
      : of(null);
  }

  continueWithLinkedIn() {
    const req$ = this.auth.isAuthed()
      ? this.auth.getLinkedInStartUrl()
      : this.auth.getLinkedInStartPublic();

    req$.pipe(
      catchError(err => {
        if (err?.status === 401) return this.auth.getLinkedInStartPublic();
        throw err;
      })
    ).subscribe(({ url }) => window.location.href = url);
  }

  async onResumeSelected(ev: Event) {
    this.uploadError = '';
    this.uploadOk = '';
    const input = ev.target as HTMLInputElement;
    if (!input.files?.length) return;
    const file = input.files[0];

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.uploadError = 'Please select a PDF file.';
      input.value = '';
      return;
    }

    try {
      this.uploading = true;
      await this.auth.uploadResume(file)
        .pipe(catchError((e: any) => {
          this.uploadError = e?.error?.detail || 'Upload failed';
          return of(null);
        }))
        .toPromise();
      if (!this.uploadError) {
        this.uploadOk = 'Résumé uploaded and analyzed!';
        this.loadSummary(); // refresh chips + seed
      }
    } finally {
      this.uploading = false;
      input.value = '';
    }
  }

  // optional: manual refresh from LinkedIn snapshot
  refreshFromLinkedIn() {
    this.http.post('/api/oauth/linkedin/sync', {})
      .pipe(catchError(() => of(null)))
      .subscribe(() => this.loadSummary());
  }

  logout() {
    this.auth.clear();
    this.router.navigateByUrl('/');
  }
}
