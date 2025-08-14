import { Component } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { NgIf, NgFor, NgClass } from '@angular/common';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../../core/auth.service';
import { RouterLink } from '@angular/router';


@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule, NgIf, RouterLink, NgClass],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css']
})
export class LoginComponent {
  loading = false;
  error = '';
  showPassword = false;


  // Use "loginId" as the email field for backend
  form = this.fb.group({
    loginId: ['', [Validators.required, Validators.minLength(3)]], // email (or username if you add support later)
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router
  ) {}

  async submit() {
    this.error = '';
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }

    this.loading = true;
    try {
      const email = this.form.value.loginId as string;
      const password = this.form.value.password as string;
      const res = await firstValueFrom(this.auth.login(
        this.form.value.loginId as string,
        this.form.value.password as string
      ));
      this.auth.setToken(res.access_token);
      
      const me = await firstValueFrom(this.auth.me());
      if (!me.onboarded) {
        this.router.navigateByUrl('/app/setup');
      } else {
        this.router.navigateByUrl('/app');
      }
    } catch (e: any) {
      // surface backend detail if available (we added DEV_VERBOSE there)
      this.error = e?.error?.detail || 'Invalid credentials';
    } finally {
      this.loading = false;
    }
  }
  async continueWithLinkedIn() {
  this.loading = true;
  try {
    const r = await firstValueFrom(this.auth.getLinkedInStartPublic());
    window.location.href = r.url; // goes to LinkedIn
  } finally { this.loading = false; }
}
}
