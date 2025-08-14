import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { AuthService } from '../../core/auth.service';

@Component({
  standalone: true,
  selector: 'app-oauth-bridge',
  template: `
    <main class="min-h-screen grid place-items-center text-sm text-gray-600">
      Finishing sign-in…
    </main>
  `
})
export class OAuthBridgeComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private auth = inject(AuthService);

  async ngOnInit(): Promise<void> {
    // 1) Save token from #token=...
    const hash = window.location.hash || '';
    if (hash.startsWith('#token=')) {
      const token = decodeURIComponent(hash.slice('#token='.length));
      localStorage.setItem('token', token);
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }

    // keep the linkedin badge if present
    const suffix = this.route.snapshot.queryParamMap.get('linkedin') === 'ok' ? '?linkedin=ok' : '';

    try {
      const me: any = await firstValueFrom(this.auth.me());
      const target = me?.onboarded ? '/app' : '/app/setup';
      this.router.navigateByUrl(target + suffix);
    } catch {
      this.router.navigateByUrl('/login');
    }
  }
}

