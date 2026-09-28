# Public Lacrosse Calendar Site

## Problem Statement

Adult lacrosse leagues and pickup games across Massachusetts and New Hampshire are currently tracked only in a hand-maintained, internal, prose-based file (`LOCATIONS.md`, originally built in the `group-me` project). There is no public-facing way for a prospective player to glance at a calendar and see what's happening this week across all these locations; someone has to read location-by-location notes ("Tuesdays, 8–9 PM... Fall 2026: Sept 22 – Nov 10, 2026") to figure out what's on and when. There's also no single place that distinguishes recurring weekly pickup games from one-off events, or that separates "what's happening soon" from the full list of every venue ever researched.

## Goals

- Make MA/NH adult lacrosse event info genuinely public and glanceable — no login, no reading prose location-by-location.
- Keep running cost at $0/month and complexity minimal: a static site, no backend, no database, no accounts.
- Prove the technical stack works (walking skeleton) before spending effort on real data, and prove real data renders correctly (including recurrence) before spending effort on automation — de-risking each layer before building the next.
- Make publishing a routine schedule update trivial: regenerate one file, redeploy — never hand-edit the published calendar feed once automation is in place.
- Keep the calendar strictly read-only and clearly labeled as a community resource, not an official league/venue channel.
- Avoid building a prose parser: introduce a structured, human-editable schedule schema instead of trying to extract structured data from free text after the fact.

## Solution

Publish a public, read-only calendar website (a static page hosted via Hugo, a Go-based static site generator) that displays upcoming lacrosse events, built and verified in three deliberately ordered phases so that each layer of the stack is proven before the next is built on top of it:

1. **Walking skeleton** — a minimal static page, ready to drop into the Hugo site, that loads the calendar library from a CDN and renders a *blank* calendar. This proves the dependency chain (Hugo static-file serving + CDN script loading + calendar library initialization) before any real data or automation is involved.
2. **Manual data** — a small, hand-written `.ics` (iCalendar, RFC 5545) file with a handful of real events copied from the source location data (including at least one recurring event) is wired into the Phase 1 page, to confirm real event data — and recurrence — actually renders correctly in the browser.
3. **Automation** — only once Phases 1 and 2 work is the pipeline built that turns structured, machine-readable event/schedule data into that `.ics` file automatically, so the published calendar stays current without hand-editing the feed.

GroupMe bot-posting is explicitly out of scope for this spec (see Out of Scope) — this covers the calendar website only.

## User Stories

1. As a prospective pickup player, I want to see a calendar of upcoming lacrosse events in MA/NH, so that I can decide which games to attend without reading prose notes location-by-location.
2. As a prospective player, I want to click or tap an event to see its address, time, cost, and contact info, so that I know exactly where to go and who to ask before showing up.
3. As a prospective player, I want to view the calendar on my phone, so that I can check it while out and about.
4. As a site visitor, I want the calendar to load without needing to log in or create an account, so that I can check it casually, on a whim.
5. As a site visitor, I want the calendar to visually distinguish recurring weekly games from one-off events, so that I understand which games repeat and which are single occurrences.
6. As a site visitor, I want to see whether an event's fields are indoor or outdoor, so that I know what to expect weather-wise before I go.
7. As a site visitor, I want past events to not clutter the default calendar view, so that I only see relevant upcoming events by default.
8. As a site visitor, I want the site to state clearly that this is a community-run resource and not an official page for any given league or venue, so that I don't mistake it for an authoritative source from the venue itself.
9. As a site visitor, I want each event to link back to the venue's real contact info or page, so that I can verify details or ask questions directly at the source rather than relying solely on this calendar.
10. As the project maintainer, I want a minimal static test page I can drop straight into the Hugo site, so that I can confirm the calendar library and its dependencies actually load and render before investing in real data or automation.
11. As the project maintainer, I want that walking-skeleton page to render a blank calendar grid with zero events, so that I know Hugo's static-file serving, the CDN script loads, and the calendar library's initialization all work together before anything else is layered on.
12. As the project maintainer, I want to verify the walking skeleton renders correctly in at least one desktop and one mobile browser, so that I catch basic integration or responsiveness issues as early and cheaply as possible.
13. As the project maintainer, I want to hand-write a small `.ics` file containing a few real events copied from the source location data, so that I can verify real event data renders correctly before any generation code exists.
14. As the project maintainer, I want at least one hand-written recurring event (using an RRULE) in that test `.ics` file, so that I can directly confirm the calendar library actually expands recurrence in its rendered UI, rather than assuming it from documentation alone.
15. As the project maintainer, I want to confirm that clicking an event in the rendered calendar shows the correct location, time, and description text, so that I know the detail/popup rendering path works end-to-end, not just the grid view.
16. As the project maintainer, I want a structured, human-editable schedule format (recurrence type, day-of-week, start time, end time, date range) defined for each event, so that schedule data becomes machine-parseable without needing to write a prose parser.
17. As the project maintainer, I want this structured schedule format to sit alongside the existing human-readable contact/address/notes fields rather than replace them, so that I don't end up maintaining two disconnected lists of the same locations.
18. As the project maintainer, I want a script that reads the structured event/schedule data and generates a valid `.ics` file, so that I never have to hand-edit the published feed again once this exists.
19. As the project maintainer, I want the generator to express a recurring event as a single VEVENT with an RRULE, not as one VEVENT per occurrence, so that the generated file stays small and matches how the schedule is actually described by the source data.
20. As the project maintainer, I want the generator to handle one-off (non-recurring) events distinctly from recurring ones, so that a single pickup event isn't forced into a recurrence rule it doesn't have.
21. As the project maintainer, I want the generator to skip and flag any entry missing required schedule fields (for example, a league listing with a start date but no explicit clock time), so that incomplete source data doesn't silently produce a broken or misleading calendar entry.
22. As the project maintainer, I want the generated `.ics` output validated before publishing, so that a malformed file doesn't break the calendar for site visitors.
23. As the project maintainer, I want the generation step to be re-runnable on demand (and eventually on a schedule or on every data change), so that the published calendar can stay current without manual `.ics` edits.
24. As the project maintainer, I want publishing an update to be as simple as "regenerate the `.ics` file, redeploy the static site," so that no change to the Hugo page or calendar code is needed for a routine schedule update.
25. As the project maintainer, I want to add a brand-new location or event to the structured data and see it appear on the calendar after the next generation run, so that adding events doesn't require touching any code.
26. As the project maintainer, I want to remove or modify an existing event in the structured data and see that change reflected in the next generated `.ics`, so that outdated or corrected events don't linger on the public calendar.

## Implementation Decisions

- **Hosting**: a Hugo static site (any static host works — GitHub Pages, Cloudflare Pages, and Netlify were all confirmed to have usable free tiers with no backend requirement). The calendar page is a Hugo template/content page; the generated `.ics` file is served via Hugo's `static/` directory passthrough — anything placed in a Hugo project's `static/` directory is copied as-is to the site root on build (e.g. `static/events.ics` → `https://<site>/events.ics`), confirmed directly in Hugo's own documentation.

- **Calendar rendering — FullCalendar**: use FullCalendar's core bundle plus its first-party `@fullcalendar/icalendar` plugin (npm description: "Display events from a public iCalendar feed"), loaded via CDN `<script>` tags rather than npm/a bundler:

  ```html
  <script src="https://cdn.jsdelivr.net/npm/fullcalendar@7.1.0/all/global.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@fullcalendar/icalendar@7.1.0/index.global.min.js"></script>
  <div id="calendar"></div>
  <script>
    document.addEventListener('DOMContentLoaded', function () {
      var calendarEl = document.getElementById('calendar');
      var calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        events: { url: '/events.ics', format: 'ics' }
      });
      calendar.render();
    });
  </script>
  ```

  Both `fullcalendar` and `@fullcalendar/icalendar` are MIT-licensed (confirmed via their npm registry `license` fields, v7.1.0) — this is distinct from FullCalendar's separately-licensed Premium/Scheduler bundle (resource/timeline views, cross-resource drag-and-drop), which carries a commercial or CC-BY-NC-ND license depending on use case and is **not needed** for a simple read-only events list; do not add it. No Node.js, npm, or bundler is required to ship the site itself — pin the version (e.g. `7.1.0` above) rather than tracking `@latest`, to avoid an untested library update silently breaking the public page.

  Documented limitation to design around: FullCalendar's ICS plugin fetches the feed once per page load, not via live polling (per FullCalendar's own docs) — acceptable given how infrequently this data changes, but it means a page left open in a background tab won't pick up a same-session update.

- **Data flow, end state (post-Phase 3)**: structured event/schedule data → generation script → `events.ics` (static file) → the Hugo page's FullCalendar instance reads it via `events: { url: '/events.ics', format: 'ics' }`.

- **New structured schedule schema**: each event gets explicit fields — recurrence type (one-off vs. weekly), day-of-week (for recurring events), start time, end time, start date, end date/until, and timezone (default `America/New_York` for all MA/NH entries, since none of the source location data specifies one). This schema is **additive** alongside the source data's existing free-text notes/contact/address fields — it does not replace them, and no prose-parsing of that existing free text is attempted.

- **Recurring event representation**: translated 1:1 into a single RFC 5545 `RRULE` line in the generated `.ics`, not enumerated as individual per-occurrence rows/events. Example `VEVENT` shape (a weekly Tuesday 8–9 PM pickup game, Sept 22 – Nov 10):

  ```
  BEGIN:VEVENT
  UID:example-pickup-fall2026@<project>
  DTSTAMP:20260922T000000Z
  DTSTART;TZID=America/New_York:20260922T200000
  DTEND;TZID=America/New_York:20260922T210000
  RRULE:FREQ=WEEKLY;BYDAY=TU;UNTIL=20261110T235959Z
  SUMMARY:Example Adult Lacrosse Pickup
  LOCATION:123 Example St, Anytown, NH 00000
  DESCRIPTION:Pickup-style lacrosse. $15 drop-in.
  END:VEVENT
  ```

- **Incomplete data handling**: entries missing a required schedule field (e.g., no explicit time) are excluded from `.ics` generation and flagged in generator output — never silently guessed or defaulted.

- **Phase ordering is itself a decision, not just a process note**: Phase 1's Hugo/FullCalendar wiring carries forward unchanged into Phase 3 — only the `.ics` source changes, from a hand-written fixture (Phase 2) to a generated file (Phase 3). Phases 1 and 2's specific fixture content may be discarded once Phase 3 supersedes it, but the walking-skeleton page itself is the same page used at every subsequent phase.

## Testing Decisions

- **Phase 1 (walking skeleton)**: no automated test suite. Success is a manual/visual check — the page builds under Hugo and renders an empty calendar grid in a real browser. This is intentionally not unit-tested; it's an integration/dependency smoke check, and the point of doing it first is precisely to catch stack-level problems before writing any code worth unit-testing.
- **Phase 2 (manual data fixture)**: also manual/visual verification, not automated tests — confirm the hand-written `.ics` fixture's specific events render with correct time/location/description, and specifically confirm the recurring-event fixture expands into multiple visible occurrences in the UI. (Whether FullCalendar's ICS plugin reliably expands `RRULE` recurrence through the rendering path is not explicitly guaranteed in its own docs, so this phase exists specifically to verify it directly rather than assume it.) This remains manual because it's validating a third-party library's rendering behavior, not our own code.
- **Phase 3 (automation) — this is where real automated tests apply**: the generation script (structured event data → `.ics` file) is the actual seam under our control, and should get fixture-based tests: given a small set of structured event entries (a recurring one, a one-off one, and a deliberately incomplete one), assert the generated `.ics` output has the right shape — correct `VEVENT` count, correct `RRULE` string for the recurring case, and the incomplete entry excluded/flagged rather than silently included. Test the generator's output structure directly (the text/structure our code controls), not by round-tripping it through a third-party ICS parser or the calendar library — that rendering behavior is already covered manually in Phase 2.
- **Prior art**: none — this is a new project with no existing code or test conventions yet. The Phase 3 generator would be the first tested module introduced.

## Out of Scope

- GroupMe bot-posting/integration — deliberately excluded from this spec; a candidate for a separate future spec.
- Live/API-based sync via the Google Calendar API — this spec is a static-file pipeline only; no OAuth credentials, no live backend calls.
- Any backend, database, or server-rendered dynamic content.
- User accounts, login, or any write/interactive functionality on the public site — it is strictly read-only.
- Automated prose-parsing of the existing free-text schedule notes — deliberately avoided by introducing an additive structured schema instead (see Implementation Decisions).
- Events outside Massachusetts/New Hampshire, or sports other than lacrosse.
- Visual design/theming of the Hugo site beyond what's needed to host the calendar page (navigation, other pages, branding) — not precluded later, just not part of this spec.

## Further Notes

- **Seed data**: the source location/event data (venue names, addresses, contacts, indoor/outdoor status, and free-text schedule notes) currently lives in `LOCATIONS.md` in the `group-me` project. This new project will need to import or copy that data as its starting seed rather than starting from scratch, and will need the new structured schedule fields (see Implementation Decisions) added to it, since `LOCATIONS.md` today only has free-text schedule notes.
- No issue tracker has been configured for this spec yet — it was written as a local Markdown file rather than published to a tracker with a `ready-for-agent` label. Configure a tracker for the new project and publish this content there once ready.
