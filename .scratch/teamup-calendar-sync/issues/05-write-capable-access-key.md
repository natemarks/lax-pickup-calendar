# Obtain a write-capable Teamup Access Key

Type: task
Status: resolved

## Question

[Confirm Teamup's real API behavior](02-confirm-teamup-api-behavior.md)'s live test found that the "public link" Access Key from [ticket 04](04-real-teamup-access-key.md) is **read-only**: a minimal `POST /events` was rejected with `{"error":{"id":"no_permission",...}}`, and `GET /subcalendars` independently confirms `"readonly": true` on the calendar's one sub-calendar as seen through this key. Reads work fine (`GET /events` returns `200 OK`); writes are denied outright. Public/share links appear to default to read-only in Teamup regardless of the calendar owner's own access level.

Concretely:
1. In the Teamup web UI, open the calendar's **Settings -> Sharing/Keys** panel (same place as ticket 04, but this time do **not** use the "public link" option).
2. Generate a **different** Access Key at an elevated permission level -- Teamup's permission levels are typically Read-only / Modify from same link / Modify / Admin; pick "Modify" or "Admin" (Admin is safest if unsure, since the sync engine needs create + update + delete).
3. Replace `TEAMUP_CALENDAR_KEY` in the repo's gitignored `.env` with this new key.
4. A quick sanity check (a single minimal `POST` then `DELETE` of a throwaway test event) is worth doing before re-running the full ticket 02 test plan, to avoid a third round-trip if this key also turns out to be under-permissioned.

This is a manual step -- only the user can generate the Access Key from Teamup's own UI; permission-level naming may not match exactly what's guessed above, so use whatever Teamup's actual UI calls the elevated option. Once done, [ticket 02](02-confirm-teamup-api-behavior.md) is ready to re-run immediately: request shapes are already spec-confirmed, and the real `subcalendar_id` (`16069515`) is already known from this attempt, so nothing else needs re-discovery.

## Answer

Done. The blocker turned out to be UI confusion, not a Teamup limitation: "Add User" isn't only for account-based users -- it also contains a "Link" sub-option (Settings -> Sharing -> Add User -> expand "Link" -> Add), separate from adding an account. The user generated a new link scoped to just this one calendar with "Modify" permission, and swapped its key into `.env`'s `TEAMUP_CALENDAR_KEY`.

**Security note, added after the fact:** the user pasted this link's URL directly into the planning chat while reporting it, which exposed the key outside `.env`. Since a Teamup "Link" is a bearer credential (no login tied to it -- anyone holding the string can use it at its granted permission level), that specific key was treated as compromised and **revoked and replaced** immediately after discovery; see the note in the map's Notes section for the current key's status. The URL is redacted from this file for the same reason. Going forward, credential values should never be pasted into chat -- update `.env` directly instead.

Confirmed working with a full write round-trip, done directly rather than via a subagent to avoid a third blocked attempt:
- `GET /subcalendars` now shows `"readonly": false` on the calendar's one sub-calendar (`id: 16069515`).
- `POST /events` with a minimal test event succeeded: `201 Created`, returned a real Teamup event id.
- Notably, the response included `"tz":"America/New_York"` even though no timezone field was sent -- Teamup appears to derive/store tz from the UTC offset in `start_dt`/`end_dt` (`-04:00`) rather than needing an explicit tz field on write. Relevant to the map's open timezone-mapping question.
- `DELETE /events/{id}` (by Teamup's own internal id, not yet `remote_id`) succeeded: `200 OK`, and a follow-up `GET /events` confirmed the calendar is empty again -- clean.

[Confirm Teamup's real API behavior](02-confirm-teamup-api-behavior.md) can now run its full remaining test plan (recurrence/`rrule`, upsert-on-duplicate-`remote_id`, delete-by-`remote_id` specifically, list round-trip, full field mapping) with a confirmed-working key.
