import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { FormBuilder, Validators, ReactiveFormsModule } from '@angular/forms';
import { NgIf } from '@angular/common';
import { catchError, of, firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-profile-setup',
  standalone: true,
  imports: [ReactiveFormsModule, NgIf],
  templateUrl: './profile-setup.component.html',
  styleUrls: ['./profile-setup.component.css'],
})
export class ProfileSetupComponent implements OnInit {
  saving = false;
  error = '';

  form = this.fb.group({
    headline: [''],
    industriesCSV: [''],
    goals: [''],
    skillsCSV: [''],
    about: [''],
  });

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    // prefill if profile already exists (when editing later)
    this.auth
      .getProfile()
      .pipe(catchError(() => of(null)))
      .subscribe((p) => {
        if (!p) return;
        this.form.patchValue({
          headline: p.headline || '',
          industriesCSV: (p.industries || []).join(', '),
          goals: p.goals || '',
          // map existing keywords -> skills field for editing
          skillsCSV: (p.keywords || []).join(', '),
          // use existing bio as “about”
          about: p.bio || '',
        });
      });
  }

  private toArr(s?: string | null): string[] {
    return (s || '')
      .split(',')
      .map((x) => x.trim())
      .filter(Boolean);
  }

  async save() {
    this.error = '';
    this.saving = true;
    try {
      const f = this.form.value;
      await firstValueFrom(
        this.auth.saveProfile({
          headline: f.headline || null,
          bio: f.about || null,
          industries: this.toArr(f.industriesCSV),
          goals: f.goals || null,
          tone: [], // optional: add a control if you want to collect tone here
          keywords: this.toArr(f.skillsCSV),
        })
      );
      this.router.navigateByUrl('/app');
    } catch (e: any) {
      this.error = e?.error?.detail || 'Failed to save profile';
    } finally {
      this.saving = false;
    }
  }

  skip() {
    this.router.navigateByUrl('/app');
  }
}
