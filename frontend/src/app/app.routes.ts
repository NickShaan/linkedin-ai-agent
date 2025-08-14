import { Routes } from '@angular/router';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { HomeComponent } from './pages/home/home.component';
import { LoginComponent } from './pages/auth/login/login.component';
import { SignupComponent } from './pages/auth/signup/signup.component';
import { authGuard } from './core/auth.guard';
import { ComposeComponent } from './pages/compose/compose.component';
import { LinkedinCallbackComponent } from './pages/auth/linkedin-callback/linkedin-callback.component';
import { OAuthBridgeComponent } from './pages/oauth-bridge/oauth-bridge.component';
import { ProfileSetupComponent } from './pages/profile-setup/profile-setup.component';

export const routes: Routes = [
//   { path: '', component: DashboardComponent },
  
  { path: 'login', component: LoginComponent },
  { path: 'signup', component: SignupComponent },
  { path: 'auth/linkedin', component: LinkedinCallbackComponent },
  { path: 'oauth-bridge', component: OAuthBridgeComponent },
  { path: 'app/setup', component: ProfileSetupComponent, canActivate: [authGuard] },
  { path: 'app', component: HomeComponent, canActivate: [authGuard] },
  { path: 'app/compose', component: ComposeComponent, canActivate: [authGuard] },

  { path: '**', redirectTo: 'login' },
];
