# lax-pickup-calendar

Keeps a public [Teamup](https://teamup.com) calendar of MA/NH adult lacrosse pickup games and leagues in sync with `data/events.json`, the source of truth. Edit the file, run the sync, and Teamup matches it exactly.

**View the calendar:** [natenite.net/lacrosse-calendar](https://natenite.net/lacrosse-calendar) (redirects to Teamup) or directly at [teamup.com/kso7z4zmxh7jgq15iq](https://teamup.com/kso7z4zmxh7jgq15iq).

## Updating events

1. Edit `data/events.json` -- add, change, or remove an entry in the `events` array. Schema and worked examples: `data/events.example.json`.
2. Run `make sync-teamup`. Output: `Sync complete: N created, N updated, N deleted, N skipped.`

Notes:
- A weekly event is written as one recurring Teamup event, not one row per occurrence.
- An entry missing a required field is skipped and reported, never guessed at -- fix it and re-run.
- Re-running with no changes is safe and reports all zeros; deletions are real, though -- anything removed from the JSON is deleted from Teamup on the next run.

## Setup

Create a gitignored `.env` at the repo root:

```
TEAMUP_TOKEN=<application API token>
TEAMUP_CALENDAR_KEY=<a Modify-permission Calendar Link key>
```

- **`TEAMUP_TOKEN`**: one-time, requested free from [teamup.com/api-keys/request](https://teamup.com/api-keys/request). Not calendar-specific.
- **`TEAMUP_CALENDAR_KEY`**: see below.

**Never paste either value into chat, a commit, or anywhere outside `.env`** -- both are bearer credentials: whoever holds one can use it, no login required.

## Generating / rotating a Calendar Link

Teamup calendar (blue menu, top right) -> **Settings** -> **Sharing** -> **Add User** -> expand the **Link** section -> **Add**. Name it, scope **Calendars Shared** to just this calendar, and pick a permission level:

- **Read-only** -- for the public viewing link (see top of this file). Safe to share/publish.
- **Modify** (or higher) -- for `TEAMUP_CALENDAR_KEY` in `.env`. Required for the sync to write events; a plain read-only link cannot.

To rotate a key (e.g. after accidental exposure): delete the old link in the same Sharing panel, create a new one the same way, and update `.env` (or this README, for the read-only link).

## Development

Standards: `CLAUDE.md`. Quick reference:

```bash
make static        # black, mypy, shellcheck, pylint, unit tests -- auto-formats
make static-check  # same, check-only (CI)
make unit           # mocked unit tests, no credentials needed
make integration    # tests against the real Teamup API (requires .env)
```

`scripts/teamup_client.py` is the HTTP layer; `scripts/sync_teamup.py` holds the JSON-to-Teamup mapping and sync logic.
