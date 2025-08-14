import { ComponentFixture, TestBed } from '@angular/core/testing';

import { LinkedinCallbackComponent } from './linkedin-callback.component';

describe('LinkedinCallbackComponent', () => {
  let component: LinkedinCallbackComponent;
  let fixture: ComponentFixture<LinkedinCallbackComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [LinkedinCallbackComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(LinkedinCallbackComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
