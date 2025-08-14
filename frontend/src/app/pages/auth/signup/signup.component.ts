import { Component } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { NgIf, NgFor, NgClass } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../../core/auth.service';


function nameValidator(c: AbstractControl): ValidationErrors | null {
  const v = (c.value || '').trim();
  return /^[A-Za-z ]{2,50}$/.test(v) ? null : { name: true };
}
function digitsOnly(len: number) {
  return (c: AbstractControl): ValidationErrors | null =>
    new RegExp(`^\\d{${len}}$`).test(c.value || '') ? null : { digits: true };
}
function linkedinIdValidator(c: AbstractControl): ValidationErrors | null {
  const v = (c.value || '').trim();
  const username = /^[A-Za-z0-9-]{3,100}$/;
  const url = /^https?:\/\/(www\.)?linkedin\.com\/in\/[A-Za-z0-9-_%]+\/?$/i;
  return (username.test(v) || url.test(v)) ? null : { linkedin: true };
}

@Component({
  selector: 'app-signup',
  standalone: true,
  imports: [ReactiveFormsModule, NgIf, NgFor, NgClass,RouterLink],
  templateUrl: './signup.component.html',
  styleUrls: ['./signup.component.css']
})
export class SignupComponent {
  loading = false;
  error = '';
  submitted = false;
  success = ''; 

  countries = [
    { code: '+91',  label: 'India (+91)' },
    { code: '+1',   label: 'USA (+1)' },
    { code: '+44',  label: 'UK (+44)' },
    { code: '+61',  label: 'Australia (+61)' },
    { code: '+971', label: 'UAE (+971)' },
  ];

  form = this.fb.group({
    name: ['', [Validators.required, nameValidator]],
    email: ['', [Validators.required, Validators.email]],
    countryCode: ['+91', [Validators.required]],
    mobile: ['', [Validators.required, digitsOnly(10)]],
    linkedinId: ['', [Validators.required, linkedinIdValidator]],
    password: ['', [Validators.required, Validators.minLength(8)]],
    confirmPassword: ['', [Validators.required]],
    acceptTos: [false, [Validators.requiredTrue]]
  }, {
    validators: (group) => {
      const p = group.get('password')?.value;
      const c = group.get('confirmPassword')?.value;
      return p && c && p === c ? null : { mismatch: true };
    }
  });

  constructor(private fb: FormBuilder, private auth: AuthService, private router: Router) {}

  // Helpers for error display
  isInvalid(name: string) {
    const c = this.form.get(name);
    return !!c && c.invalid && (c.touched || this.submitted);
  }
  err(name: string): string {
    const c = this.form.get(name);
    if (!c || !c.errors) return '';
    if (c.errors['required'])     return 'This field is required.';
    if (c.errors['email'])        return 'Enter a valid email address.';
    if (c.errors['name'])         return 'Only letters and spaces (2–50 characters).';
    if (c.errors['digits'])       return 'Enter exactly 10 digits.';
    if (c.errors['linkedin'])     return 'Provide a LinkedIn username or a valid profile URL.';
    if (c.errors['minlength'])    return `Minimum ${c.errors['minlength'].requiredLength} characters.`;
    if (c.errors['maxlength'])    return `Maximum ${c.errors['maxlength'].requiredLength} characters.`;
    if (c.errors['requiredTrue']) return 'You must accept the terms.';
    if (name === 'confirmPassword' && this.form.errors?.['mismatch']) return 'Passwords do not match.';
    return '';
  }

  get f() { return this.form.controls; }

  // Debug aid (optional)
  get invalidReasons() {
    const out: any = { form: this.form.errors };
    for (const [k, c] of Object.entries(this.form.controls)) {
      if ((c as any).invalid) out[k] = (c as any).errors;
    }
    return out;
  }

  async submit() {
    this.submitted = true;
    this.error = '';

    if (this.form.invalid) { this.form.markAllAsTouched(); return; }

    this.loading = true;
    try {
      const f = this.form.controls;
      const payload = {
        name: (f.name.value || '').trim(),
        email: f.email.value!,
        country_code: f.countryCode.value!,
        mobile: f.mobile.value!,
        linkedin_id: f.linkedinId.value!,
        password: f.password.value!
      };

      const res = await firstValueFrom(this.auth.signup(payload));
      this.auth.setToken(res.access_token);
      this.success = res.message ?? 'Account created successfully!';
       await this.router.navigateByUrl('/app/setup'); // login is your home page
    } catch (e: any) {
      this.error = e?.error?.detail || 'Signup failed';
    } finally {
      this.loading = false;
    }
  }
}
