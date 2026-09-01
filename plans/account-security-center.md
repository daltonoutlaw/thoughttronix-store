# Plan: Account Security Center

> Source PRD: `prd/account-security-center.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app**: `accounts`
- **URLs**:
  - `accounts:security_center` (`/accounts/security/`) — central security dashboard and overview
  - `accounts:password_change` (`/accounts/security/password/`) — password rotation with current password confirmation
  - `accounts:two_factor_setup` (`/accounts/security/2fa/setup/`) — initiate TOTP configuration
  - `accounts:two_factor_verify` (`/accounts/security/2fa/verify/`) — confirm 6-digit TOTP code and activate 2FA
  - `accounts:two_factor_backup_codes` (`/accounts/security/2fa/backup-codes/`) — view/regenerate recovery codes
  - `accounts:two_factor_disable` (`/accounts/security/2fa/disable/`) — disable 2FA with password confirmation
  - `accounts:two_factor_challenge` (`/accounts/login/2fa/`) — secondary challenge during sign-in
  - `accounts:session_list` (`/accounts/security/sessions/`) — view active sessions and devices
  - `accounts:session_revoke` (`/accounts/security/sessions/<int:pk>/revoke/`) — revoke a specific session
  - `accounts:session_revoke_others` (`/accounts/security/sessions/revoke-others/`) — revoke all secondary sessions
  - `accounts:audit_log` (`/accounts/security/activity/`) — security activity and event history
- **Models**:
  - `TOTPDevice`: One-to-one with `User` (`secret_key`, `is_confirmed`, `created_at`, `last_used_at`)
  - `BackupCode`: Foreign key to `User` (`code_hash`, `is_used`, `used_at`, `created_at`)
  - `UserSession`: Foreign key to `User` (`session_key`, `ip_address`, `user_agent`, `device_type`, `last_activity`, `created_at`)
  - `SecurityEvent`: Foreign key to `User` (`event_type`, `ip_address`, `user_agent`, `details`, `created_at`)
- **Authentication & Security Policies**:
  - Step-up verification: Re-authentication via current password required for sensitive modifications (password update, 2FA deactivation, backup code regeneration).
  - Rate limiting on login and 2FA challenge endpoints against brute-force attempts.
  - 30-day active session lifetime with middleware-based activity updates.
  - Standard Django password validation and transactional alert emails triggered via Django's mail system.

---

## Phase 1: Security Center Hub & Password Rotation

**User stories**: 1, 2, 3, 4

### What to build

A dedicated Security Center hub accessible from customer account navigation. The dashboard presents an overview of the account's security posture (password health, 2FA status, active device summary). Customers can update their password via a step-up form validating their current password and enforcing password complexity rules. Successful password rotation automatically dispatches a transactional security notification email to the customer's email address.

### Acceptance criteria

- [x] "Security Center" link is visible in account navigation for authenticated customers.
- [x] Security Center overview page renders current security posture cards (2FA status, password status, active session count).
- [x] Password change form requires entry of the current password and validates new password confirmation and complexity.
- [x] Submitting an invalid current password displays a clear error message and does not alter the password.
- [x] Successful password rotation updates the user's password, maintains the active user session without forcing an immediate unexpected sign-out, and displays a success notification.
- [x] An email notification alerting the user of the password change is sent immediately upon successful password update.
- [x] Automated tests cover authorized access, password form validation errors, successful update, and email dispatch.

---

## Phase 2: TOTP Two-Factor Authentication Setup & Recovery Codes

**User stories**: 5, 6, 7, 8, 9

### What to build

Self-service TOTP Two-Factor Authentication management within the Security Center. Customers can initiate 2FA setup to generate an unconfirmed TOTP secret, displaying both an inline SVG QR code and a plaintext manual entry key. Customers must submit a valid 6-digit TOTP code to confirm and activate 2FA. Upon activation, a set of single-use backup recovery codes is generated and presented in plaintext for the customer to copy/download (with securely hashed copies stored in the database). Customers can regenerate backup recovery codes or disable 2FA at any time by confirming their current password.

### Acceptance criteria

- [ ] Initiating 2FA setup generates a standard TOTP secret and renders an inline SVG QR code alongside a manual entry key.
- [ ] Submitting an invalid or expired 6-digit TOTP code prevents activation and shows an inline validation error.
- [ ] Submitting a valid 6-digit TOTP code marks 2FA as active and redirects to the backup recovery codes view.
- [ ] 8–10 single-use backup recovery codes are generated, displayed in plaintext for immediate backup, and stored securely as hashes.
- [ ] Customers can regenerate backup recovery codes by confirming their current password, which immediately invalidates all prior backup codes.
- [ ] Customers can disable 2FA by providing their current password; deactivation removes the TOTP device and purges existing backup codes.
- [ ] Automated unit and integration tests verify QR generation, TOTP time-step validation, code hashing, regeneration, and deactivation.

---

## Phase 3: Two-Factor Sign-In Challenge & Rate Limiting

**User stories**: 10, 11, 12

### What to build

A two-step sign-in flow that enforces secondary verification for accounts with active 2FA. When a customer with 2FA enabled provides valid username and password credentials, the initial login stages the session and redirects to a dedicated 2FA challenge screen instead of granting full access. The challenge screen accepts either a current 6-digit TOTP authenticator code or one of the user's single-use backup recovery codes. Successfully providing a backup recovery code marks that specific code as permanently used. Both login and 2FA challenge endpoints enforce strict attempt rate limiting to prevent brute-force attacks.

### Acceptance criteria

- [ ] Signing in with valid credentials on a 2FA-enabled account redirects to the 2FA challenge view (`/accounts/login/2fa/`).
- [ ] Unauthenticated requests directly accessing the 2FA challenge view are redirected back to the login page.
- [ ] Submitting a valid 6-digit TOTP code completes the login and establishes a fully authenticated session.
- [ ] Submitting a valid backup recovery code completes the login and permanently invalidates that specific code.
- [ ] Attempting to reuse a previously consumed backup recovery code fails.
- [ ] Failed attempts on login and 2FA challenge views are rate-limited, locking out further attempts after the configured threshold.
- [ ] Automated tests cover normal login (non-2FA), staged 2FA challenge redirect, TOTP validation, backup code consumption, and rate limiter enforcement.

---

## Phase 4: Session & Device Tracking with Revocation

**User stories**: 13, 14, 15, 16

### What to build

Middleware-driven session and device management. A dedicated middleware tracks active sessions on each request, recording the session key, IP address, parsed user-agent device type (e.g., desktop, mobile, tablet), and last activity timestamp, while enforcing a 30-day session lifetime. The Security Center provides an active sessions dashboard highlighting the current device session. Customers can revoke any individual secondary session or trigger a global "sign out all other sessions" action, which immediately invalidates the target session records in storage and forces re-authentication on those devices.

### Acceptance criteria

- [ ] Every authenticated request updates or creates a `UserSession` record with current IP, device type, and timestamp.
- [ ] The Sessions view in the Security Center lists all active sessions with device details, IP address, and relative last active time.
- [ ] The customer's current session is clearly tagged with a "Current Session" badge and cannot be revoked via the single-item revocation button.
- [ ] Clicking "Revoke" on a specific secondary session deletes its session record and invalidates the session in Django session storage.
- [ ] Clicking "Sign out all other sessions" revokes all non-current sessions in a single operation.
- [ ] Any revoked session encountering the application is immediately forced to sign in again.
- [ ] Automated tests verify middleware tracking, session listing, single revocation, bulk revocation, and session invalidation.

---

## Phase 5: Security Audit Log & Critical Activity Alerts

**User stories**: 17, 18

### What to build

A unified security event audit logging system and transactional alert pipeline. Security-critical events across the application (successful logins, failed login attempts, password changes, 2FA activations/deactivations, and session revocations) are recorded in a chronological audit log table. Customers can inspect their recent security activity timeline directly within the Security Center. In addition, critical security events (2FA status changes, password changes, and new/unrecognized device logins) automatically trigger transactional email alerts with actionable security guidance.

### Acceptance criteria

- [ ] Security events are automatically logged with timestamp, event type, IP address, and device metadata across all auth actions.
- [ ] Security Center provides a chronological activity log view (`/accounts/security/activity/`) displaying recent events with appropriate icons and timestamps.
- [ ] Critical events (2FA activation/deactivation, password changes, new device logins) trigger immediate transactional email alerts to the user's email address.
- [ ] Email notifications provide clear context on the event and guidance on securing the account if the action was unexpected.
- [ ] Automated tests verify event creation across all relevant views and confirm transactional email triggers for critical event types.
