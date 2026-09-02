# PRD: Customer Wishlist

## Problem Statement

ThoughtTronix customers browsing the catalog frequently discover neural interface products, hardware, or accessories they want to purchase later or keep track of over time (including currently unavailable items), but currently have no way to bookmark or save them without adding them to their active shopping cart. Adding items to the cart clutters the checkout flow, creates confusion during purchasing, and does not provide a true persistent saved-for-later experience.

## Solution

A dedicated, customer-scoped Wishlist feature integrated into the storefront. Signed-in customers have a single, private wishlist where they can seamlessly add or remove products directly from product detail pages with instantaneous asynchronous feedback. Customers can access a dedicated Wishlist management page from the main navigation to review all saved items, inspect current availability, quickly add in-stock items to their shopping cart, or remove items with immediate inline updates.

## User Stories

1. As a signed-in customer, I want to add a product to my wishlist directly from its product detail page without a full page reload, so that I can easily save items I want to buy later.
2. As a signed-in customer, I want to remove a product from my wishlist directly from its product detail page without a full page reload, so that I can easily unsave items I am no longer interested in.
3. As a signed-in customer, I want the wishlist button on the product detail page to clearly reflect the product's current wishlist state, so that I always know whether an item is currently saved in my wishlist.
4. As an anonymous visitor, I want clicking the wishlist button to prompt me to sign in and redirect me back to the product page upon login, so that I can save the product immediately once authenticated.
5. As a signed-in customer, I want to add and keep unavailable (out-of-stock) products in my wishlist, so that I can track items I want to buy when they become available again.
6. As a signed-in customer, I want to access my wishlist directly from the top navigation bar, so that I can easily review all my saved products from anywhere on the storefront.
7. As a signed-in customer, I want to view all my saved items on a dedicated Wishlist page with product details, pricing, and stock availability status, so that I have a clear overview of everything I have bookmarked.
8. As a signed-in customer, I want to add an available product directly from my wishlist to my shopping cart, so that I can proceed to purchase items I have saved.
9. As a signed-in customer, I want to remove an item directly from my wishlist page with instant inline updates and no page reload, so that I can curate my list quickly.
10. As a signed-in customer, I want to see a clear empty state on my wishlist page when no products are saved with a link to browse the catalog, so that I understand my list is empty and know where to discover products.
11. As a customer, I want strict data isolation so that I can only view and modify my own wishlist data, so that my saved items and preferences remain completely private.

## Implementation Decisions

- **Application Structure**:
  - A dedicated `wishlists` domain application adhering to the storefront's modular architecture conventions.
- **Data Model & Relationships**:
  - A dedicated `Wishlist` container entity with a strict one-to-one relationship to the customer account.
  - A `WishlistItem` join entity linking the wishlist to catalog products, tracking timestamps (`added_at`) and enforcing uniqueness per product per customer.
  - Model-level convenience methods for adding, removing, toggling, and checking presence of products.
- **Interactivity & Asynchronous Behavior**:
  - Product detail page toggle utilizes asynchronous HTML fragment swapping (HTMX) to update the button state in place without full page reloads.
  - Product detail toggle presents a secondary action button with distinct visual states and icons for saved vs. unsaved items.
  - Wishlist management page uses asynchronous fragment updates to remove items inline smoothly.
- **Authentication & Access Control**:
  - All wishlist read and mutation endpoints require customer authentication.
  - Queries and mutations are strictly scoped through the authenticated user's own wishlist instance.
  - Anonymous interactions on the product detail page redirect to the login flow with a return redirect parameter.
- **Availability & Cart Integration**:
  - Unavailable / out-of-stock products can be wishlisted and remain visible in the wishlist with explicit status badges.
  - The wishlist page integrates with the existing cart system, providing one-click cart additions for in-stock items.
- **Navigation & User Interface**:
  - Prominent top navigation entry for authenticated customers.
  - Standardized empty state presentation matching the platform design guidelines.

## Out of Scope

- Named wishlists, multiple wishlists per customer, or custom user-created lists.
- Shared, collaborative, or public wishlists via shareable links.
- Wishlist toggle buttons on catalog listing grid cards (scoped exclusively to product detail pages).
- Automated restock notifications or email alerts when wishlisted items change price or availability.
- Back-office staff management or analytics views for customer wishlists.

## Further Notes

- Leverages DaisyUI semantic styles and HTMX partials consistent with the existing `orders` and `products` patterns.
- Fully backwards-compatible database migrations ensuring zero disruption to existing customer accounts.
