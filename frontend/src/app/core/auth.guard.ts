import { CanActivateFn } from '@angular/router';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  // Return a UrlTree when unauthenticated (clean redirect)
  return auth.isAuthed() ? true : router.parseUrl('/login');
};
