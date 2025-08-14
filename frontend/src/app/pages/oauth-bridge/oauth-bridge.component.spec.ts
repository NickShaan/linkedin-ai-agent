import { ComponentFixture, TestBed } from '@angular/core/testing';

import { OauthBridgeComponent } from './oauth-bridge.component';

describe('OauthBridgeComponent', () => {
  let component: OauthBridgeComponent;
  let fixture: ComponentFixture<OauthBridgeComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OauthBridgeComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(OauthBridgeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
