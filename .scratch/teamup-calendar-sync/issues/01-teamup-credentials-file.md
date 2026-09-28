# Set up local Teamup credentials file

Type: task
Status: resolved

## Question

Get the already-existing Teamup API key and the target calendar's id into a local, gitignored config file that the sync tooling can load -- unblocking any real API testing.

Concretely:
1. Agree on and create the file (suggested: `.teamup.local.json` at the repo root, containing `{"api_key": "...", "calendar_id": "..."}` -- adjust naming if you prefer something else).
2. Add that filename to `.gitignore`.
3. Populate it with your real, already-issued Teamup API key and the id of the flat calendar you created.
4. Confirm the file exists, is gitignored (`git check-ignore` or `git status` shows nothing), and is readable.

This is a manual step -- only the user can supply the real credential values. The agent can create the `.gitignore` entry and a loader stub, but the human should place the actual secret value into the file directly rather than pasting it into a chat transcript.

## Answer

Done, though with a different shape than the ticket's suggested filename: the user created a `.env` file at the repo root (already gitignored) containing `TEAMUP_TOKEN` (the real, already-issued API token). The agent added `TEAMUP_CALENDAR_KEY=<redacted>` to the same file, extracted from the calendar's public share URL (`https://teamup.com/c/<redacted>/adult-lax-ma-nh` -- the `/c/<key>/` segment). `.env` is confirmed gitignored (`.gitignore:7:.env`).

Note for [Confirm Teamup's real API behavior](02-confirm-teamup-api-behavior.md): whether this share-link key was the same identifier Teamup's API expects as the calendar key in its endpoint paths was assumed, not yet verified -- it was later proven **not** to be (see ticket 02/04).
