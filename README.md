# lax-pickup-calendar

Keeps a public [Teamup](https://teamup.com) calendar of MA/NH adult lacrosse pickup games and leagues in sync with a single, human-edited JSON file. The JSON file is the source of truth -- edit it, re-run the sync, and the Teamup calendar matches it exactly (events added, changed, or removed).

Full background: `docs/specs/public-lacrosse-calendar-site.md` (the original spec) and `docs/research/teamup-live-api-behavior.md` (how Teamup's API actually behaves, empirically confirmed).

## Managing events

All events live in `data/events.json`. Each event is a JSON object with a stable `id` plus its schedule fields; `data/events.example.json` has the full annotated schema and worked examples of both event shapes (one-off and weekly recurring).

To add, change, or remove an event:

1. Edit `data/events.json` directly -- add a new object to the `events` array, change fields on an existing one, or delete an object entirely.
2. Run the sync (see below). The Teamup calendar will end up exactly matching the file: new entries are created, changed entries are updated, and anything removed from the file is deleted from Teamup.

A few things worth knowing about how entries map onto Teamup, from the live research:

- `recurrenceType: "weekly"` becomes a single recurring Teamup event (one `rrule`), not one event per occurrence.
- `notes` is sent as plain text; Teamup renders it as HTML (wraps it in `<p>...</p>`) on its end -- this is cosmetic, no action needed on your part.
- An entry missing a required field (e.g. a weekly event with no `dayOfWeek`) is skipped and reported, never silently guessed at -- fix the entry and re-run.
- Re-running the sync is always safe: it's idempotent, so running it again with no changes to the file reports `0 created, 0 deleted`, and existing events are simply re-confirmed.

## Setup

```bash
git clone <this repo>
cd lax-pickup-calendar
```

Create a `.env` file at the repo root (already gitignored) with your Teamup credentials:

```
TEAMUP_TOKEN=<your Teamup API token>
TEAMUP_CALENDAR_KEY=<your Teamup calendar's Access Key>
```

- `TEAMUP_TOKEN`: requested for free from Teamup's [API key request form](https://teamup.com/api-keys/request).
- `TEAMUP_CALENDAR_KEY`: a **Calendar Link** key with "Modify" (or higher) permission, scoped to just this calendar -- from the Teamup web app: blue menu (top right) -> **Settings** -> **Sharing** -> **Add User** -> expand the **Link** section -> **Add**. (Don't use a plain public/share link -- those default to read-only and can't write events.)

**Never commit `.env` or paste its contents anywhere outside your own editor** -- a Teamup Calendar Link key is a bearer credential: whoever holds it can modify the calendar, no login required. If a key is ever exposed, revoke it in Teamup's Sharing settings and generate a replacement.

## Running the sync

```bash
make sync-teamup
```

This reads `data/events.json`, compares it against what's currently in the Teamup calendar, and applies whatever create/update/delete calls are needed to make them match. Output looks like:

```
Sync complete: 2 created, 1 updated, 0 deleted, 0 skipped.
```

A non-zero exit code means something needs attention: skipped (malformed) entries, or a Teamup API call failing partway through.

## Development

Static analysis and tests follow this project's standard scaffolding -- see `CLAUDE.md` for the full standards. Quick reference:

```bash
make static        # black, mypy, shellcheck, pylint, unit tests -- auto-formats
make static-check  # same, but check-only (what CI runs)
make unit           # unit tests only (mocked, no credentials needed)
make integration    # tests against the real Teamup API (requires .env)
```

`scripts/teamup_client.py` is a thin HTTP wrapper around Teamup's REST API. `scripts/sync_teamup.py` holds the actual sync logic: mapping JSON events to Teamup's event shape, diffing against Teamup's current state, and executing the create/update/delete plan.
