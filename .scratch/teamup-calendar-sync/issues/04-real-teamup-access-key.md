# Obtain a real Teamup Access Key

Type: task
Status: resolved

## Question

[Confirm Teamup's real API behavior](02-confirm-teamup-api-behavior.md)'s first live API call discovered that `TEAMUP_CALENDAR_KEY=<redacted>` (extracted in [ticket 01](01-teamup-credentials-file.md) from the calendar's public share URL) is **not** a working API credential -- every real call authenticated with it returned `401 login_required`, and the share URL itself redirects a browser to a login page. Controlled comparisons confirmed `TEAMUP_TOKEN` is a valid application token and the share-URL slug is a real identifier of *some* kind, just not one the API accepts for authenticated access. Teamup's OpenAPI spec's own examples show real Access Keys as ~17-19 characters, conventionally prefixed `ks` -- structurally nothing like that slug.

Concretely:
1. In the Teamup web UI, open the calendar's **Settings -> Sharing** (or "Keys") panel -- not the public share link -- and generate/copy a real Access Key with enough permission to create, modify, and delete events (not a read-only key, since the sync engine needs full write access).
2. Replace the `TEAMUP_CALENDAR_KEY` value in the repo's gitignored `.env` with that real Access Key.
3. Confirm it works with one minimal real call (e.g. `GET https://api.teamup.com/{key}/events` with the `Teamup-Token` header) -- should return event data or an empty list, not a 401.

This is a manual step -- only the user can generate the Access Key from Teamup's own UI. Once done, [ticket 02](02-confirm-teamup-api-behavior.md) can be re-run to empirically confirm the 6 behaviors it still only has spec-derived (not live-verified) answers for.

## Answer

Done. The user generated a public-link Access Key from Teamup (URL redacted -- superseded and revoked, see [ticket 05](05-write-capable-access-key.md)) -- an 18-char `ks`-prefixed key, matching the OpenAPI spec's real-key format, unlike the earlier share-URL slug. Swapped into `.env`'s `TEAMUP_CALENDAR_KEY`. Confirmed working with a minimal real call: `GET https://api.teamup.com/{key}/events` returned `200 OK` with `{"events":[],"timestamp":...}` (read access confirmed).

**Not yet confirmed: write permission level.** The user described this as a "public link," and Teamup's permission model typically makes public/share links read-only by default -- whether this specific key has create/modify/delete access is unverified and is now squarely [ticket 02](02-confirm-teamup-api-behavior.md)'s first job (its create-event test will surface a permission error immediately if this key can't write, distinct from the `401 login_required` the previous invalid key produced).
