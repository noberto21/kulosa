# KULOSA (Phases 1 to 4)

Kenya-first event discovery and sharing. **Discover. Share. Experience.**

Stack: Python, Django, SQLite, Django Templates, Tailwind CSS, vanilla JavaScript.

## Phase 1 (design)

- Homepage with search, categories, Featured / Trending / Happening today / Coming this week / Recently added, organizer promotion and footer
- Explore Events with keyword, category, county/town, date, free/paid filters, sorting, pagination and an empty state
- Event detail page with WhatsApp, Facebook, X and copy-link sharing, external booking link and related events
- About and Categories pages

## Added in Phase 2

- **Custom user model** (`accounts.User`): email login, case-insensitive uniqueness, full name, optional phone. Defined before the first migration.
- **Models and migrations:** Category, OrganizerProfile, Event, SavedEvent, EventReport, with database constraints (end after start, paid events need a price, one save per user per event, one open report per user per event).
- **Auth:** register, login, logout (POST only), account page, password reset by email (links last 3 hours).
- **Permissions:** `Event.can_view()` / `Event.can_edit()` (owners edit their own, staff manage all, nobody edits completed events except staff); `Event.objects.published()` is the only public queryset.
- **Rate limits** on login, registration and password reset (see `apps/accounts/ratelimit.py`).
- **Django Admin** for users, categories, organizers, events, saved events and reports.
- **Tests:** `python manage.py test` (39 tests).

## Added in Phase 3

- **Event submission** at `/my-events/new/` (the "Share an Event" button): validated form with a Kenyan-county dropdown, date and price rules, http/https-only ticket links, and "Save as draft" or "Submit for review".
- **Safe poster uploads:** only real JPEG, PNG or WebP files up to 5 MB and 6000 px; SVG, GIF and disguised files are rejected; images are re-encoded under random names so EXIF/GPS data is removed. Replaced or deleted posters are removed from disk.
- **Review workflow** (`apps/events/workflow.py`): Draft, Pending, Published, Rejected, Cancelled, Completed. Editing a published event sends it back to Pending.
- **Dashboard** at `/my-events/`: status filters, rejection reasons, submit, withdraw, cancel, delete (drafts and rejected only). Other people's events return 404.
- **Organizer profile** (name, logo, contact, website). Only admins can mark one verified.
- **Admin approval:** in Django Admin, filter Events by status "Pending review", then use "Approve selected pending events", or set a status to Rejected with a required reason. Owners get an email either way.
- **Profile settings:** edit name/phone and change password from the account page.
- `python manage.py complete_past_events` marks finished published events as Completed. Run it daily from cron or your host's scheduler.

## Added in Phase 4 (discovery)

- **Database-backed listings.** The built-in demo data is gone. The homepage, Explore, categories and event pages all read the database, and only events that are *Published* and not yet ended are discoverable (`apps/events/services.py`).
- **Search and filters:** every word you type must match the title, summary, description, venue, town, county, organizer or category; plus category, county/town, date (today, this week, this weekend, this month, or a specific day), free/paid, sort by soonest or recently added, and pagination. Queries per page are constant (no N+1).
- **Homepage sections:** Featured (set by staff in Admin), Trending (upcoming events with the most saves), On today, Coming this week, Recently added, popular categories. Empty sections hide themselves, and an empty site shows a "share an event" prompt.
- **Event pages** (`/events/<slug>/`): poster, details, organizer card with contact details and a public organizer page, external ticket link (opens in a new tab with `nofollow`), WhatsApp/Facebook/X/copy-link sharing, related events. Cancelled events show a clear cancellation notice and no ticket button; completed or ended events say so. Unpublished events return 404 to the public and show an owner/staff-only preview.
- **Favorites:** signed-in users save and unsave events, and see them at `/saved/`.
- **Reports:** signed-in users can report a published listing (reason and details). One open report per person per event, no reporting your own event, and a rate limit. In Admin, reports appear in a queue with "Mark resolved" and "Dismiss" actions, and the Events list shows an "Open reports" column. Staff can also feature or unfeature events from the Events list.
- **Moderator emails:** set `MODERATOR_EMAILS` in `.env` to email staff on each new submission and report.
- **SEO and sharing:** `sitemap.xml`, `robots.txt`, canonical links, Open Graph tags, schema.org Event data (safely escaped), and `noindex` on non-published pages.
- **Sample data for local development:** `python manage.py seed_demo_events` creates clearly labelled `[Demo]` events (it refuses to run unless `DEBUG` is on); `python manage.py seed_demo_events --remove` deletes them. Never use it on a real site.
- Tests: `python manage.py test` (149 tests).

## What is NOT built yet

- Contact page shows a "not available yet" page. Write a real one before launch.
- The newsletter box is a disabled placeholder.
- Per-event timezone (all events use East Africa Time).
- Email verification at sign-up.
- Map display (coordinates are stored but not shown).
- Admin activity reporting beyond the Django Admin lists and filters.

## Setup (Linux / macOS)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit values
python manage.py check
python manage.py migrate
python manage.py seed_categories
python manage.py createsuperuser
python manage.py runserver
```

Optional, to see the site with content: `python manage.py seed_demo_events`.

## Setup (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env     # then edit values
python manage.py check
python manage.py migrate
python manage.py seed_categories
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Database

Local development uses SQLite by default. Production on Vercel requires a managed PostgreSQL database; the app deliberately refuses to start there without `DATABASE_URL` or `POSTGRES_URL`, so production data cannot silently end up in ephemeral SQLite.

## Tailwind CSS

The compiled stylesheet `static/css/tailwind.css` is committed, so Node is only needed when you change styles:

```bash
npm install
npm run build:css     # one-off
npm run watch:css     # while editing templates
```

Source: `static/css/input.css`; config: `tailwind.config.js`.

## Design notes

Midnight navy, electric orange, off-white. The ticket-stub card (date stub, perforated tear line) is the signature element. Fonts use `Inter` if installed, otherwise the system sans-serif; no external font requests are made. Events without an uploaded poster show a CSS placeholder styled by category.


## Verification checklist

- [ ] `python manage.py check` reports no issues
- [ ] Homepage renders on desktop and a ~375px-wide mobile viewport
- [ ] Explore page renders; each filter, sorting and pagination work; empty state appears for `?q=zzzzzz`
- [ ] Event detail page opens from a card; WhatsApp link, copy-link and booking link work
- [ ] Save/unsave an event while signed in; submit a report; approve an event and see it appear in Explore
- [ ] Mobile menu opens and closes; keyboard focus is visible; skip link works

## Email

Password-reset emails print to the console in development. For production set `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` plus the `EMAIL_*` and `DEFAULT_FROM_EMAIL` variables.

## Production notes

- Rate limits use Django's cache. The default is per-process memory; configure a shared cache (Redis or Memcached) so limits hold across workers.
- Behind a proxy, make sure the proxy sets `REMOTE_ADDR` correctly; `X-Forwarded-For` is deliberately not trusted.
- Local media uploads use the filesystem. Vercel uses a public Vercel Blob store for persistent event posters and organizer logos; the function's `/tmp` directory is not used for uploaded media.
- Set `SITE_URL` so links in emails point to your real domain.

## Fresh Vercel deployment (PostgreSQL and Blob)

1. Push the application code to GitHub and import that repository in Vercel. Keep the Root Directory at the repository root (the directory containing `manage.py`) and use the Django framework defaults.
2. Before the first deployment, provision a managed PostgreSQL database through the Vercel Marketplace (Neon is supported) and connect it to the project. Set `DATABASE_URL` for Production. `POSTGRES_URL` is also supported; do not rename the variable with a custom prefix. Use a separate database or branch for Preview.
3. In the same Vercel project, create a **public** Vercel Blob store and connect it to Production. This app serves event posters and organizer logos directly from their Blob URLs, so the store must be public. Ensure the project receives `BLOB_READ_WRITE_TOKEN` (or `BLOB_STORE_ID` when using Vercel OIDC). Connect a separate store for Preview if Preview deployments are enabled.
4. Set `DJANGO_SECRET_KEY` to a new, private, high-entropy value in Vercel for Production and Preview. Keep `DJANGO_DEBUG` unset or set it to `False`. Never reuse or upload a local `.env` file or commit secrets.
5. Set any optional production values such as `SITE_URL`, SMTP email settings, and `MODERATOR_EMAILS`. Vercel supplies its deployment host variables automatically; Django uses those for allowed hosts and CSRF.
6. Deploy. Vercel must have the PostgreSQL and Blob variables before the app starts: Django intentionally stops with a configuration error if a Vercel deployment has no persistent database or Blob store. The application runs its Django migrations at startup; check the deployment/runtime logs and verify the site and `/admin/` load before creating the admin user.
7. Create a superuser in that same PostgreSQL database. From PowerShell in the repository root, run the following and paste the Production `DATABASE_URL` only at the hidden prompt:

   ```powershell
   $secureUrl = Read-Host "Production PostgreSQL URL" -AsSecureString
   $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureUrl)
   try {
       $env:DATABASE_URL = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
       python manage.py migrate
       if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
       python manage.py createsuperuser
       if ($LASTEXITCODE -ne 0) { throw "Superuser creation failed." }
   }
   finally {
       Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
       [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
       Remove-Variable secureUrl, pointer -ErrorAction SilentlyContinue
   }
   ```

   Use the same PostgreSQL database that Vercel has in Production. This creates a new production admin account; it does not copy local SQLite users or events. Do not paste the database URL or account password into chat or source control.
8. Log in at `https://<your-production-domain>/admin/`. The site registration form does not grant staff/admin permission; use `createsuperuser` for the first admin.

If a domain is added later, set `SITE_URL` to its HTTPS origin. Web Analytics is optional and can be enabled in Vercel's Analytics dashboard.

The local `.env.example` is for development only. It uses SQLite and filesystem media unless local database/storage variables are explicitly configured. Production password-reset and moderator emails will not be delivered until SMTP is configured.
