import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../../core/auth.service';

@Component({
  selector: 'app-linkedin-callback',
  standalone: true,
  template: `<p class="p-4 text-sm">Signing you in…</p>`,
})
export class LinkedinCallbackComponent implements OnInit {
  constructor(private ar: ActivatedRoute, private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
    const jwt = this.ar.snapshot.queryParamMap.get('jwt');
    if (jwt) {
      this.auth.setToken(jwt);
      this.router.navigateByUrl('/app'); // go to home
    } else {
      this.router.navigateByUrl('/signup');
    }
  }
}
