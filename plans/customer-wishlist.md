# Plan: Customer Wishlist

> Source PRD: `prd/customer-wishlist.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app**: `wishlists`
- **URLs**:
  - `wishlists:toggle` (`/wishlist/toggle/<int:pk>/`) — HTMX toggle for adding/removing a product on detail pages
  - `wishlists:detail` (`/wishlist/`) — dedicated customer wishlist management page
  - `wishlists:remove` (`/wishlist/remove/<int:pk>/`) — HTMX inline removal of a product from the wishlist page
- **Models**:
  - `Wishlist`: One-to-one with `settings.AUTH_USER_MODEL` (`user`, `created_at`) with `Wishlist.for_user(user)` lookup/creation helper
  - `WishlistItem`: Foreign key to `Wishlist` (cascade delete), Foreign key to `Product` (cascade delete), `added_at` (`DateTimeField(auto_now_add=True)`), with `UniqueConstraint(fields=["wishlist", "product"], name="unique_wishlist_product")`
- **Authentication & Scoping**:
  - All wishlist endpoints enforce `LoginRequiredMixin`.
  - All operations strictly resolve through `request.user.wishlist` to prevent cross-user data exposure.
  - Anonymous visitors on product detail pages are presented with standard sign-in links carrying the return `?next=` URL parameter.
- **Interactivity & UI Conventions**:
  - Interactivity uses HTMX partial swaps returning targeted partial templates.
  - Styling strictly adheres to Tailwind + DaisyUI semantic classes (`btn-outline`, `btn-secondary`, `badge-success`, `badge-warning`).

---

## Phase 1: Wishlist Foundation & Product Detail Page Toggle

**User stories**: 1, 2, 3, 4, 5, 11

### What to build

Create the `wishlists` application, data models (`Wishlist` and `WishlistItem`), and database migrations. Implement model helper methods (`toggle`, `contains`, `for_user`) for adding and removing products safely scoped to the owner. Add the wishlist toggle button to the product detail page alongside the "Add to Cart" button. For signed-in customers, clicking the button issues an HTMX request that adds or removes the item and swaps the button in place with an updated state (heart icon and label). For anonymous visitors, render a link prompting them to sign in and redirect back. Allow wishlisting unavailable/out-of-stock products. Write automated tests covering models, views, anonymous behavior, and user isolation.

### Acceptance criteria

- [x] `wishlists` app is registered in Django settings and migrations apply cleanly.
- [x] `Wishlist` and `WishlistItem` models enforce a single wishlist per user and unique products per wishlist.
- [x] Product detail page displays the wishlist toggle button next to the "Add to Cart" button.
- [x] For logged-in users, clicking "Add to Wishlist" saves the product and updates the button to "In Wishlist (Remove)" via HTMX without a full page reload.
- [x] For logged-in users, clicking "In Wishlist (Remove)" removes the product and updates the button back to "Add to Wishlist" via HTMX without a full page reload.
- [x] Anonymous visitors see a wishlist button linking to the login page with the return `?next=` parameter.
- [x] Unavailable/out-of-stock products can be added to and removed from the wishlist.
- [x] Automated tests verify model methods, toggle view permissions, HTMX partial rendering, and customer data isolation.

---

## Phase 2: Dedicated Wishlist Page & Storefront Navigation

**User stories**: 6, 7, 10, 11

### What to build

Add a "Wishlist" navigation link in the top navbar for authenticated users. Implement the dedicated `/wishlist/` page that fetches and displays the signed-in customer's wishlisted products ordered by most recently added. Each item card displays the product image, title (linking to the product detail page), price, and current stock status badge (`In stock` or `Unavailable`). When the wishlist contains no items, render a designed empty state explaining that the wishlist is empty with a button to explore the catalog. Ensure strict access control so customers can only access their own wishlist. Write automated tests for page access, authentication enforcement, user isolation, and empty state rendering.

### Acceptance criteria

- [x] "Wishlist" link appears in the main navbar for authenticated customers.
- [x] `/wishlist/` requires authentication; unauthenticated requests redirect to the login page.
- [x] `/wishlist/` renders all wishlisted items belonging to the logged-in customer with image, title, price, and stock status.
- [x] Customers cannot view or access another customer's wishlist items.
- [x] When the wishlist is empty, a styled empty state is displayed with a call-to-action link to the catalog.
- [x] Automated tests verify navigation visibility, authentication requirements, correct rendering of items/badges, empty state display, and strict data isolation.

---

## Phase 3: Wishlist Page Actions (Cart Integration & Inline Removal)

**User stories**: 8, 9, 11

### What to build

Enhance the `/wishlist/` page by adding interactive item actions: an "Add to Cart" button for in-stock products and an instant HTMX-powered "Remove" button per item. Clicking "Add to Cart" adds the product to the customer's cart (using existing cart mechanics) and provides feedback. Clicking "Remove" sends an HTMX request that immediately removes the product item card from the DOM without a full page reload and displays the empty state if the last item is removed. Write automated tests covering inline removal, cart addition from the wishlist, and unavailable item cart restrictions.

### Acceptance criteria

- [ ] Each item on `/wishlist/` has a "Remove" button that removes the item immediately via HTMX.
- [ ] Removing the final item dynamically transitions the page or container to the designed empty state.
- [ ] In-stock wishlisted items include an "Add to Cart" button that adds the item to the user's active cart.
- [ ] Unavailable wishlisted items have their "Add to Cart" button disabled with an "Unavailable" badge.
- [ ] Removing an item only affects the authenticated customer's own wishlist.
- [ ] Automated tests verify HTMX removal endpoint, cart addition integration, unavailable product behavior, and customer isolation.
