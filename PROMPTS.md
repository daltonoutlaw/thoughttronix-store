# PROMPTS.md — AI Usage Log

This file is the record of AI use on this codebase. At the end of every
agent session, direct the agent to write the session log with this prompt:

> Append a session log to PROMPTS.md at the repo root, under today's date,
> newest entry at the top. Record every prompt I gave you this session, in
> order, including any corrections. End the entry with a short summary:
> the outcome, any places where I deviated from a recommended answer or
> asked follow-up questions, and anything that went sideways.

Two rules:

- Entries are added only by that prompt, never unprompted.
- New entries go at the top. Never rewrite or delete an old entry — the
  log is part of your work, and an honest log of a session that went
  sideways is worth more than a tidy one.

Each entry has this shape:

    ## YYYY-MM-DD — <one-line summary>

    ### Prompts
    1. ...

    ### Summary
    - **Outcome:** what was built and what was kept
    - **Deviations:** recommendations overridden, follow-up questions asked
    - **Sideways:** failures, wrong turns, and how they were caught

---

## 2026-09-02 — Customer Wishlist Phase 3: Wishlist Page Actions (Cart Integration & Inline Removal)

### Prompts
1. `/implement @prd/wishlist.md @plans/wishlist.md implement phase 3`
2. `i approve`
   - *TDD Candidates Approved:* (1) Removal endpoint & isolation, (2) Empty state transition on final item removal, (3) Cart action states for in-stock vs unavailable products
3. `i approve`
   - *Cycle 1 Approved:* Wishlist removal endpoint and partial rendering
4. `approved`
   - *Manual Verification:* Confirmed manual verification passed

### Summary
- **Outcome:** Completed Phase 3 of the Customer Wishlist feature. Added `wishlists:remove` (`/wishlist/remove/<int:pk>/`) endpoint allowing authenticated customers to remove items directly from the wishlist page with HTMX without full page reload. Extracted `templates/wishlists/partials/_wishlist_contents.html` to dynamically update wishlist contents, item count header, and seamlessly transition to the empty state when the final item is removed. Integrated cart actions on each item card using `orders/partials/_add_button.html` so in-stock items can be added to the active cart with out-of-band navbar badge updates, while unavailable items display a disabled button. Added comprehensive automated tests for removal, customer isolation, empty state transition, and cart addition integration. All 259 tests passed, and linter/formatter checks passed cleanly.
- **Deviations:** None. Followed TDD and implement skill guidelines.
- **Sideways:** Encountered an `AttributeError` in the cart integration test when calling `cart.lines.filter` (`lines` is a method on Cart); resolved by querying `cart.items.filter`.

---

## 2026-09-02 — Customer Wishlist Phase 2: Dedicated Wishlist Page & Storefront Navigation

### Prompts
1. `/implement @prd/customer-wishlist.md d @plans/customer-wishlist.md md implement phase`
   - *Phase Selection:* `(Recommended) Phase 2: Dedicated Wishlist Page & Storefront Navigation`
2. `if i use the /implement command, will it use the skill located in .agents or .claude`
3. `/implement @prd/customer-wishlist.md d @plans/customer-wishlist.md md implement phase`
4. `approved`
5. `yes`
6. `/implement @prd/wishlist.md @plans/wishlist.md implement phase 2`
7. `backtrack. I approve the last phase. proceed with the next step for that. Then i will review this`

### Summary
- **Outcome:** Completed Phase 2 of the Customer Wishlist feature. Added the "Wishlist" navigation link to the main navbar for authenticated customers in `templates/base.html`. Implemented and verified test coverage for the dedicated `/wishlist/` page, including customer authentication enforcement, item detail rendering (image, title link, formatted price, stock status badge), empty state rendering with a call-to-action catalog link, and strict cross-customer data isolation. All 254 tests passed and linting/formatting checks passed cleanly.
- **Deviations:** None. Followed the TDD process with approved candidate behaviors for navigation and empty state verification.
- **Sideways:** None. Encountered a minor import sorting issue reported by `ruff check` which was automatically corrected with `ruff check --fix`.

---

## 2026-09-01 — Account Security Center Design & PRD Generation

### Prompts
1. `/grill-me to design a account security center`
   - *Q1 (Scope):* "(Recommended) Comprehensive Security Hub: Password change, Two-Factor Authentication (TOTP / Authenticator app), Active Session Management (view devices & revoke sessions), and Security Event History (logins, password changes)."
   - *Q2 (MFA Implementation):* "(Recommended) TOTP via lightweight library (pyotp + qrcode/svg generation) with custom Django models for TOTP secrets and hashed single-use backup recovery codes."
   - *Q3 (Session Tracking):* "(Recommended) Dedicated UserSession model + middleware: Records session key, IP address, user-agent (parsed device/browser), last active timestamp, and allows individual session revocation as well as 'Revoke all other sessions'."
   - *Q4 (Audit & Alerts):* "(Recommended) Comprehensive SecurityEvent Log + Notification Emails: Record events (success/failed login, password changed, 2FA toggled/used, session revoked) and dispatch email notifications on critical events (password change, 2FA state change, new device login)."
   - *Q5 (Login Challenge & Sudo Mode):* "(Recommended) Two-step login flow with session staging: If 2FA is active, initial login stages credentials in session and redirects to a dedicated 2FA verification challenge screen (accepting 6-digit TOTP or backup code); plus require current password for sensitive actions (password reset, 2FA toggle)."
   - *Q6 (UI Architecture):* "(Recommended) Unified Card-Based Security Hub: A central '/accounts/security/' page with account navigation tabs, structured into distinct cards for Security Status, Password Management, Two-Factor Authentication, Active Sessions (with revoke controls), and Recent Activity Timeline."
   - *Q7 (Security Policies):* "(Recommended) Standard Django Password Validators + 30-day session expiry + Rate limiting on 2FA/login attempts."
2. `why are you not recognizing the /to-prd skill`
3. `it is in the @[.claude/skills/to-prd]`
4. `why are you not recognizing the skill to-prd in @[.claude/skills/to-prd]`
5. `you were recognizing the /grill-me and /handoff skills that i created in .claude before/grill-me`
6. `give me the terminal command that will fix it. I want to use the skills that are in the .claude folder`
7. `/to-prd`
8. `Append a session log to PROMPTS.md at the repo root, under today's date, newest entry at the top. Record every prompt I gave you this session, in order, including any corrections. End the entry with a short summary: the outcome, any places where I deviated from a recommended answer or asked follow-up questions, and anything that went sideways.`

### Summary
- **Outcome:** Completed a full architectural interview via `/grill-me`, produced a technical design document artifact, diagnosed custom skill discovery discrepancies between `.claude` and `.agents`, and generated a complete Product Requirements Document in `prd/account-security-center.md` conforming to the `to-prd` skill specifications.
- **Deviations:** None on design choices (user accepted all recommended architecture options across scope, TOTP approach, session tracking, audit logging, step-up authentication, UI structure, and policies). Follow-up questions centered around why skills residing in `.claude/skills/` were not discovered natively by Antigravity.
- **Sideways:** The agent initially failed to locate `/to-prd` because Antigravity scans `.agents/skills/` rather than `.claude/skills/`, and `/grill-me` had only appeared to work because it matched Antigravity's built-in slash command. An initial attempt to write the PRD directly encountered a permission prompt denial, after which the user triggered `/to-prd` once the directory structure was clarified.
