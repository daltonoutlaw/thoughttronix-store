# PRD: Account Security Center

## Problem Statement

ThoughtTronix customers manage highly personal neural tech products, account addresses, and purchase histories, but their account security is currently limited to basic password authentication. Users have no visibility into active sessions or connected devices, cannot enable Two-Factor Authentication (2FA/MFA) to protect against credential compromise, cannot review security audit logs, and have no ability to revoke stale or unfamiliar sessions.

## Solution

A dedicated, self-service Account Security Center integrated into the storefront account navigation. Customers can monitor their account security health, update passwords, set up and manage TOTP Two-Factor Authentication with backup recovery codes, inspect active browser/device sessions with individual or global revocation, and review an audit timeline of security events with email notifications for critical account changes.

## User Stories

1. As a customer, I want to access a dedicated Security Center from my account navigation, so that I have a central place to manage all my authentication and access settings.
2. As a customer, I want to view an overview of my security posture, so that I can immediately tell whether my account is adequately protected.
3. As a customer, I want to update my password by providing my current password and a new valid password, so that I can rotate my credentials safely.
4. As a customer, I want to receive an email notification when my password is changed, so that I am alerted if an unauthorized modification happens.
5. As a customer, I want to set up Two-Factor Authentication using an authenticator app (TOTP) by scanning a QR code or entering a key manually, so that my account has an additional layer of protection.
6. As a customer, I want to verify a 6-digit TOTP code before 2FA is officially activated, so that I do not lock myself out with an unverified authenticator.
7. As a customer, I want to receive a set of single-use backup recovery codes upon activating 2FA, so that I can regain access if I lose my primary authenticator device.
8. As a customer, I want to regenerate backup recovery codes when needed, so that previously saved or exposed codes are immediately invalidated.
9. As a customer, I want to disable Two-Factor Authentication by confirming my current password, so that I can adjust my security setup if my requirements change.
10. As a customer with 2FA enabled, I want to complete a secondary verification step (6-digit TOTP code or backup recovery code) during sign-in, so that unauthorized parties cannot access my account with only my password.
11. As a customer using a backup recovery code to sign in, I want that specific code to be consumed permanently, so that used codes cannot be intercepted and reused.
12. As a customer, I want rate limiting on login and 2FA challenge attempts, so that brute-force attacks against my credentials and codes are thwarted.
13. As a customer, I want to view a list of all active sessions and devices logged into my account (showing device type, IP address, and last activity timestamp), so that I can detect unauthorized access.
14. As a customer, I want my current session clearly identified in the active sessions list, so that I do not accidentally terminate my active session.
15. As a customer, I want to revoke any individual active session, so that I can disconnect unfamiliar devices immediately.
16. As a customer, I want a single action to sign out of all other sessions, so that I can secure my account across all secondary devices with one click.
17. As a customer, I want to view a chronological log of recent security events (logins, failed login attempts, password changes, 2FA status changes, and session terminations), so that I have complete audit visibility into my account activity.
18. As a customer, I want to receive email alerts for critical security events (2FA activation/deactivation, password changes, and new device logins), so that I can take prompt action if suspicious activity occurs.

## Implementation Decisions

- **Application Integration**: Built directly into the accounts application within the storefront.
- **Architectural Flow**:
  - Two-step authentication flow: initial username and password verification validates credentials and stages the session; if Two-Factor Authentication is active, the user is redirected to a secondary challenge screen before receiving a fully authenticated session.
  - Step-up verification: Current password confirmation is required for sensitive administrative actions, including password changes, 2FA deactivation, and backup code regeneration.
- **Two-Factor Authentication**:
  - Standard time-based one-time password (TOTP) algorithm compatible with industry-standard authenticator apps.
  - Inline SVG QR code rendering for visual setup alongside manual secret key display.
  - Securely hashed single-use backup recovery codes stored such that plaintext codes are only visible to the user at generation time.
- **Session & Device Management**:
  - Middleware-backed session tracking that records and updates active sessions with IP address, user-agent device parsing, and last activity timestamps.
  - Session revocation invalidates the underlying session storage record and immediately forces re-authentication on the targeted device.
- **Audit Logging & Notifications**:
  - Dedicated security event logging for all authentication attempts (successful and failed), credential modifications, 2FA lifecycle events, and session terminations.
  - Transactional email notifications triggered automatically on critical security actions.
- **Security Policies**:
  - Enforce standard platform password complexity and validation rules.
  - 30-day session lifespan for active sessions.
  - Attempt rate limiting on authentication and 2FA challenge endpoints.
- **User Interface**:
  - Unified card-based layout matching the storefront's design language, featuring clean status indicators, action modals, and activity timelines.

## Out of Scope

- SMS-based OTP verification.
- Hardware security keys (FIDO2 / WebAuthn / Passkeys).
- Geolocation resolution via third-party paid IP geolocation APIs (only IP and parsed user-agent strings are recorded).
- Social or third-party OAuth provider linking.

## Further Notes

- All security actions, forms, and session state changes should integrate seamlessly with existing customer models and address book navigation.
- Email alerts will provide actionable guidance for customers on what steps to take if an action was unexpected.
