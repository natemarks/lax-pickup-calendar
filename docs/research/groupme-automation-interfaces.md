# GroupMe Automation Interfaces

## Summary

GroupMe's official developer platform ([dev.groupme.com](https://dev.groupme.com)) exposes a REST API (`api.groupme.com/v3`) for groups, messages, direct messages, likes, users, blocks, and **bots**, plus a separate image-upload service and a Bayeux/long-polling push channel for real-time message events. **There is no documented, public API endpoint for GroupMe's in-app "Calendar" / Events feature.** The word "calendar" does not appear anywhere in the primary developer documentation, and "event" appears only in the unrelated sense of a push-protocol message event (e.g. `line.create`), not a scheduled calendar item. This absence was checked directly against the full text of the API reference page, the response-envelope doc, and both site-search and `site:dev.groupme.com` web searches — none surfaced a calendar/events resource. Consequently, any automation that wants to "manage events in a group" from the outside cannot create, read, update, or delete native Calendar entries through documented interfaces; the only officially supported fallback is a **Bot** posting formatted text messages (optionally with image/location attachments) into the group, which the app's users would read as an announcement rather than see appear in GroupMe's native Calendar UI. This document's Gherkin scenarios are written against that real constraint.

## Findings

### Authentication

- Base identity/session flow lives at [dev.groupme.com](https://dev.groupme.com), which links to Log In (`/session/new`) and to registering an app at `/applications/new`.
- OAuth is a simple OAuth 2.0 **implicit** grant, documented at [dev.groupme.com/tutorials/oauth](https://dev.groupme.com/tutorials/oauth):
  1. Register an application (a callback URL, required to be HTTPS, is configured at registration).
  2. Redirect the user to `https://oauth.groupme.com/oauth/authorize?client_id=CLIENT_ID`.
  3. The user logs in and authorizes the app in GroupMe's UI.
  4. GroupMe redirects back to the registered callback URL with the token appended: `https://YOUR_CALLBACK_URL/?access_token=ACCESS_TOKEN`.
- For a developer's own scripts/bots (rather than a third-party app used by other people), a personal access token can instead be copied directly from the dev.groupme.com dashboard (referenced from [dev.groupme.com/tutorials/bots](https://dev.groupme.com/tutorials/bots): "Your token is available at the bots page").
- The token must be sent as an `X-Access-Token` HTTP header on every request — the docs explicitly warn never to put it in the URL query string, "where it can be captured in server logs, proxy logs, and browser history" ([dev.groupme.com/tutorials/oauth](https://dev.groupme.com/tutorials/oauth), reiterated in [dev.groupme.com/docs/v3](https://dev.groupme.com/docs/v3)).
- **No OAuth scopes exist.** The documented flow grants a single, all-or-nothing access token per user/application — there is no parameter or mechanism in the primary docs for requesting a narrower permission set. (Confirmed by the absence of any scope parameter or scope list anywhere in `/tutorials/oauth` or `/docs/v3`.)
- No refresh-token mechanism is documented; the implicit-grant token is what's used going forward.

### Getting a Personal API Access Token (dashboard method)

This is the path a developer actually uses to script or run a bot against **their own** GroupMe account — it is distinct from the OAuth implicit-grant flow above (which is for a published third-party app acting on behalf of *other* users' accounts; see the cross-reference at the end of this subsection).

1. **Prerequisite — a GroupMe account.** The dev.groupme.com homepage states plainly: "You must log in with your GroupMe account before you can access the APIs" ([dev.groupme.com](https://dev.groupme.com)). There is no separate "developer" account type; it's the same account used in the regular GroupMe app.
2. **Log in at [dev.groupme.com/session/new](https://dev.groupme.com/session/new).** As fetched directly, this page presents a credentials-only form — two fields, "Email or Phone" and "Password," plus a "Log In" button, with the prompt "Sign in with your GroupMe credentials to manage your bots and applications." Unlike the end-user GroupMe app (which also supports Facebook login), the developer-site login page as rendered showed **only** the GroupMe email/phone-and-password form — no Facebook option was observable on this page. (Note: this reflects the page's fetched state at research time and could change; treat it as observed-not-guaranteed.)
3. **Navigate to the Bots page, [dev.groupme.com/bots](https://dev.groupme.com/bots).** This is the actual page where the token lives — confirmed by [dev.groupme.com/tutorials/bots](https://dev.groupme.com/tutorials/bots), which says verbatim: "For the sake of convenience, your access token is listed at the top of the [bots page](/bots)." Fetching `/bots` without an authenticated session returns an HTTP 302 redirect to `/session/new` (confirmed directly), which is consistent with the page being login-gated as the tutorial implies — the token itself could not be observed pre-login (see Limitation below).
4. **Copy the token shown at the top of the `/bots` page.** No further "generate" or "create token" action is documented anywhere in the primary docs — the personal access token appears to be provisioned automatically for the logged-in account and simply displayed for copying, not something a user requests or configures.
5. **Use it immediately as the `X-Access-Token` header** on requests to `https://api.groupme.com/v3` — the same header mechanism used for OAuth-obtained tokens ([dev.groupme.com/docs/v3](https://dev.groupme.com/docs/v3), [dev.groupme.com/tutorials/oauth](https://dev.groupme.com/tutorials/oauth)).

**Token security warnings documented on the primary source:** [dev.groupme.com/tutorials/bots](https://dev.groupme.com/tutorials/bots) states, verbatim: "Never put it in the URL query string, where it can be captured in server logs, proxy logs, and browser history," and "Treat your access token like a password and never commit it to source control."

**Regeneration:** No "regenerate token" or "revoke token" control is documented or mentioned on any fetched primary-source page (`/tutorials/bots`, `/docs/v3`, `/tutorials/oauth`, the homepage). This may exist as a UI control on the logged-in `/bots` page itself (not observable without an authenticated session — see Limitation below), but no primary-source text describes or confirms one.

**Personal token vs. OAuth token — the distinction, cross-referenced:** The token obtained via this dashboard method is scoped to the developer's own account with full, all-or-nothing access to it (same "no scopes" property noted in the Authentication section above) and is meant for **the developer's own scripts/bots acting on their own groups**. It is functionally the same kind of bearer credential as the OAuth implicit-grant `access_token` described earlier in this Authentication section (same `X-Access-Token` header usage, same lack of scopes/refresh tokens) — the difference is *whose* account it grants access to and *how it's issued*: the dashboard token is self-service and tied to the logged-in developer's own account, while the OAuth flow is how a **separately registered, published application** obtains a token to act on behalf of a *different* GroupMe user who explicitly authorizes it through the `oauth.groupme.com/oauth/authorize` redirect. Neither primary source page fetched (`/tutorials/oauth`, `/docs/v3`) draws this contrast explicitly in its own words — the distinction stated here is inferred from combining what each page documents about who initiates each flow and for whose account the resulting token is valid.

**Limitation — content behind the login wall was not observable.** Both `https://dev.groupme.com/bots` and `https://dev.groupme.com/applications` were fetched directly and returned an HTTP 302 redirect to `https://dev.groupme.com/session/new` (confirmed by direct WebFetch, not inferred). This means the actual rendered `/bots` page — where the token is displayed, and where a possible "regenerate" control might live — could not be read or verified in this research; everything stated above about that page's contents is sourced from what `/tutorials/bots` *says* about it, not from viewing it directly. This research did not attempt to log in (out of scope / requires real account credentials), so the exact layout, wording, and any regenerate/revoke affordance on the authenticated `/bots` page are unverified and should be confirmed by a developer who actually logs in.

### Core REST API

- Base URL: `https://api.groupme.com/v3` ([dev.groupme.com/docs/v3](https://dev.groupme.com/docs/v3)).
- Format: JSON request/response bodies. The docs specifically recommend sending JSON in the request body rather than form parameters "to maintain consistent hash ordering."
- Response envelope (documented at [dev.groupme.com/docs/responses](https://dev.groupme.com/docs/responses)): every response is `{ "response": {...}, "meta": { "code": <int>, "errors": [...] } }`. `meta.code` mirrors the HTTP status "for clients that cannot read HTTP status codes"; `meta.errors` is populated on 4XX responses.
- Documented endpoint groups on [dev.groupme.com/docs/v3](https://dev.groupme.com/docs/v3):
  - **Groups**: `GET /groups` (paginated, `page`/`per_page`/`omit` params, default 10/page), `GET /groups/:id`, `GET /groups/former`.
  - **Members**: `GET /groups/:group_id/members/results/:results_id` (add-member results, "temporary — only available for 1 hour"), `POST /groups/:group_id/members/:membership_id/remove` (group creator cannot be removed), `POST /groups/:group_id/memberships/update` (nickname, 1–255 chars).
  - **Messages**: `GET /groups/:group_id/messages` (`before_id`/`since_id`/`after_id`/`limit`, max `limit` 100, default 20, returns HTTP 304 when nothing matches); `POST /groups/:group_id/messages` (`source_guid` required for 1-minute de-duplication, `text` max 1,000 chars, optional `attachments`).
  - **Direct Messages / Chats**: `GET /chats`, paginated, sorted by `updated_at` descending.
  - **Likes**: `POST /messages/:conversation_id/:message_id/like` and `.../unlike`.
  - **Bots**: see dedicated section below.
  - **Users**: `GET /users/me`; `POST /users/update` (`avatar_url`, `name`, `email`, `zip_code`).
  - **Blocks**: `GET /blocks?user=...`, `GET /blocks/between?...`, `POST /blocks?...`, `DELETE /blocks?...` / `POST /blocks/delete?...`.
  - There is **no "events" or "calendar" endpoint group** on this page — the full documented list of resource groups is Groups, Members, Messages, Chats, Likes, Bots, Users, Blocks.
- Image uploads are a separate host, [dev.groupme.com/docs/image_service](https://dev.groupme.com/docs/image_service): base URL `https://image.groupme.com`, single endpoint `POST /pictures` (binary body, `Content-Type: image/...`, authenticated via `X-Access-Token`), returning `{"payload": {"url": ..., "picture_url": ...}}`; GroupMe auto-generates `preview` (200×200 cropped), `large` (960×960, aspect preserved) and `avatar` (60×60 cropped) thumbnail variants of the returned URL. This is the required path for attaching an image to a bot-posted message.

### Calendar / Events — verified absent from the public API

- The full rendered text of [dev.groupme.com/docs/v3](https://dev.groupme.com/docs/v3) was checked (twice, with targeted prompts) for the literal strings "calendar" and "event" (outside of the push-protocol sense of "event" meaning a pushed message) — neither a calendar resource nor an events CRUD resource is present.
- `site:dev.groupme.com calendar` and `site:dev.groupme.com event` web searches returned no indexed developer-docs pages describing a calendar/events API; the only "event" hit on-domain was the [push tutorial](https://dev.groupme.com/tutorials/push), which uses "event" only to mean a real-time push notification of a new chat message, not a scheduled calendar entry.
- Conclusion: GroupMe's in-app Calendar feature (visible to end users in the mobile/web client for scheduling group events) has **no corresponding public REST endpoint** in the official documentation. Automations cannot create, list, update, or delete native GroupMe Calendar events through any documented interface.

### Bots API

Documented at [dev.groupme.com/docs/v3#bots](https://dev.groupme.com/docs/v3) and walked through step-by-step in [dev.groupme.com/tutorials/bots](https://dev.groupme.com/tutorials/bots):

- **Create**: `POST /bots` with body `{"bot": {"name": ..., "group_id": ..., "avatar_url": ..., "callback_url": ..., "dm_notification": ...}}`. Response includes a `bot_id` used for all subsequent calls. Bots can also be created via the web form at `/bots/new`.
- **List**: `GET /bots` — returns bots owned by the authenticated user/token.
- **Post a message**: `POST /bots/post` with `{"bot_id": ..., "text": ...}`; optional `picture_url` (must already be a GroupMe image-service URL) and other attachments (image, location — "not multiple of the same type").
- **Delete**: `POST /bots/destroy` with `{"bot_id": ...}`.
- A bot only posts into the single group it was created against (`group_id` is set at creation and not documented as changeable) — there is no "post calendar event" bot action, only free-text/attachment messages.

### Webhooks / Callbacks

- `callback_url` (optional, set at bot creation or update) is the officially documented push mechanism for bots: per [dev.groupme.com/tutorials/bots](https://dev.groupme.com/tutorials/bots), GroupMe "receives POST requests when messages appear" in the group and forwards them to that URL, including sender info, timestamp, and message content.
- This callback fires only for **ordinary chat messages** posted to the group (by any member or bot) — the docs give no indication that Calendar/Event creation, edits, or reminders in the app trigger any callback or push event. No such payload shape is documented anywhere.
- Separately, [dev.groupme.com/tutorials/push](https://dev.groupme.com/tutorials/push) documents a full duplex push service built on the **Bayeux protocol** (websockets or HTTP long-polling) for building custom real-time clients: handshake → subscribe to a user channel (message events) → subscribe to a group channel (typing notifications) → long-poll. Event payloads carry a type such as `line.create`, user details, message content/group ID, and a timestamp. This, too, is scoped to chat messages/typing indicators, not calendar data.
- Net effect: there is no documented way to be notified when a Calendar event is created/changed in a group, and no documented way to push a native Calendar entry — `callback_url` and the push service are strictly message-level, not event/calendar-level.

### Rate Limits, Pagination, and Error Handling

- **Pagination**: documented per-endpoint, not globally. `GET /groups` uses `page`/`per_page` (default 10/page); `GET /groups/:group_id/messages` uses `before_id`/`since_id`/`after_id`/`limit` (max 100, default 20, descending by `created_at`, HTTP 304 when there's nothing new); `GET /chats` uses `page`/`per_page`. ([dev.groupme.com/docs/v3](https://dev.groupme.com/docs/v3))
- **Error handling**: 4XX/5XX responses carry `meta.errors` (an array of human-readable strings) alongside the mirrored `meta.code`. ([dev.groupme.com/docs/responses](https://dev.groupme.com/docs/responses))
- **Status codes actually documented** on the API reference page: `200 OK`, `201 Created`, `304 Not Modified` (no messages match a filter), `400 Bad Request`, `403 Forbidden` (e.g. group/user ID mismatch), `404 Not Found`, `409 Conflict` (duplicate `source_guid` within the 1-minute de-dup window), `503 Service Unavailable`.
- **Rate limits are NOT documented anywhere in the official GroupMe developer docs.** No numeric request-per-minute/hour ceiling, throttling header, or `429`/`420` status code appears in `/docs/v3` or `/docs/responses`. (An earlier automated pass over this same page mistakenly surfaced a "420 rate limiting" code; a second, targeted re-check of the verbatim page text found no such code and no rate-limit language at all — that claim is retracted here as unverifiable/incorrect.) A community discussion thread on the unofficial `groupme-api-support` Google Group speculates about an informal ~30 messages/60 seconds limit and mentions HTTP 429 responses in practice, but this is **not** an official/primary source and is listed only in Open Questions below.

### Official SDKs / GitHub

- GroupMe's official GitHub organization is [github.com/groupme](https://github.com/groupme) (repository index: [github.com/orgs/groupme/repositories](https://github.com/orgs/groupme/repositories)).
- Relevant official repos found there: **`bot-tutorial-nodejs`** ("an example bot callback server written in node.js and hosted on Heroku") and **`BotExamples`** ("example applications utilizing GroupMe's bot framework") — these are companion code samples for the `/tutorials/bots` walkthrough, not a maintained client SDK.
- The rest of the `groupme` org's public repos are general infrastructure (e.g. `faye`, `faye-redis-node`, `radix`, `appattest`) or the official `groupme-desktop` client app — none of them are a first-party REST/Bots API SDK library, and none reference calendar/events functionality.
- No official language-specific SDK (Python/JS/Go/etc. wrapper library) maintained by GroupMe itself was found. Community-maintained wrappers exist (e.g. `node-groupme`, Go packages, Python `Groupy`, and the community `groupme-js/GroupMeCommunityDocs` project) but these are explicitly third-party and out of scope as primary sources per this research's constraints — they are mentioned here only as pointers, not as cited fact sources.

## Gherkin User Stories

These scenarios assume the real, verified capability surface above: **no native Calendar/Events API exists**, so "syncing events into GroupMe" must mean a Bot posting formatted chat messages that represent events, with the local file as the reconciliation source of truth. There is no way to truly "update" or "delete" a previously posted event message via the API (message edit/delete is not a documented endpoint either — messages can only be *liked/unliked*, not edited or removed by a bot), so update/delete scenarios post explicit correction/cancellation messages rather than mutating a prior post.

```gherkin
Feature: Sync a local events file into a GroupMe group via a Bot
  As a group organizer
  I want to maintain events in a plain text/YAML file
  So that GroupMe's group chat reflects the current schedule,
  even though GroupMe has no public API for its native Calendar feature

  Background:
    Given a GroupMe Bot has been created via "POST /bots" with a valid "group_id" and "bot_id"
    And the automation holds a valid access token sent via the "X-Access-Token" header
    And GroupMe provides no public API to create, read, update, or delete native Calendar events
    And the automation instead posts formatted event messages to the group via "POST /bots/post"
    And the automation keeps a local sync-state record mapping each event's stable ID to the "source_guid" of the message it last posted about that event

  Scenario: Initial sync with an empty group state
    Given the local events file defines 3 upcoming events
    And the automation's local sync-state record is empty (no events have ever been synced)
    When the sync runs
    Then the automation posts one formatted message per event to "POST /bots/post"
    And each message includes the event's title, date, time, location, and description
    And each posted message is sent with a unique "source_guid" to avoid the 1-minute de-duplication conflict
    And the automation records each event's ID and its message "source_guid" in the local sync-state record

  Scenario: Adding a new event to the file
    Given the local sync-state record already reflects 3 previously synced events
    And the local events file now contains those 3 events plus 1 new event
    When the sync runs
    Then the automation detects the new event by its ID not being present in the sync-state record
    And it posts exactly one new formatted message announcing the new event
    And it does not repost messages for the 3 unchanged events
    And it adds the new event's ID to the sync-state record

  Scenario: Editing an existing event's title, time, or location
    Given the local sync-state record contains an event with ID "team-standup-2026-09-15"
    And the local events file changes that event's time from "10:00" to "11:00" and its location from "Room A" to "Room B"
    When the sync runs
    Then the automation detects a change by comparing the file's field values against the last-synced values stored in the sync-state record
    And because GroupMe provides no documented API to edit a previously sent message, the automation posts a new message clearly marked as an update, e.g. "UPDATED: Team Standup — now 11:00 in Room B (was 10:00, Room A)"
    And the automation updates the sync-state record with the new field values
    And the automation does not attempt to modify or delete the original message via the API

  Scenario: Deleting an event from the file
    Given the local sync-state record contains an event with ID "launch-party-2026-09-20"
    And the local events file no longer contains that event
    When the sync runs
    Then the automation detects the removal by finding an ID in the sync-state record that is absent from the current file
    And because GroupMe provides no documented API to delete a previously sent message, the automation posts a cancellation message, e.g. "CANCELED: Launch Party (was scheduled 2026-09-20) is no longer happening"
    And the automation removes that event's entry from the sync-state record

  Scenario: Malformed or invalid entries in the events file
    Given the local events file contains one well-formed event and one entry missing a required "date" field
    When the sync runs
    Then the automation skips posting anything for the malformed entry
    And it logs a validation error identifying the malformed entry and the missing field
    And it still processes and posts the well-formed event normally
    And the sync does not abort entirely because of the one bad entry

  Scenario: Duplicate detection within the file
    Given the local events file lists two entries with the same event ID "board-meeting-2026-10-01"
    When the sync runs
    Then the automation flags a duplicate-ID validation error before posting anything for that ID
    And it posts at most one message for that event ID, using the first valid occurrence
    And it logs which entries were treated as duplicates

  Scenario: Duplicate detection against GroupMe's own message de-duplication
    Given the automation is about to post a message for an event it has already posted about
    When it constructs the "POST /bots/post" request
    Then it reuses a deterministic "source_guid" derived from the event ID and its current field values
    And if GroupMe responds "409 Conflict" because the same "source_guid" was already sent within the last minute
    Then the automation treats this as "already posted, no action needed" and does not retry with a new "source_guid"

  Scenario: Posting a reminder before an event
    Given an event "board-meeting-2026-10-01" is scheduled and already synced
    And the automation runs on a recurring schedule (e.g. daily)
    And the event's date is within the configured reminder window (e.g. 24 hours away)
    And no reminder has yet been recorded as sent for this event in the sync-state record
    When the sync runs
    Then the automation posts a reminder message via "POST /bots/post", e.g. "REMINDER: Board Meeting is tomorrow at 14:00 in Room B"
    And it records in the sync-state record that a reminder was sent for this event
    And on subsequent runs before the event, it does not post a duplicate reminder for the same event
```

## Open Questions / Unverified

- **Rate limits**: No numeric rate limit is documented on any official GroupMe page checked ([dev.groupme.com/docs/v3](https://dev.groupme.com/docs/v3), [dev.groupme.com/docs/responses](https://dev.groupme.com/docs/responses)). An unofficial Google Group thread (`groups.google.com/g/groupme-api-support`) references an informal ~30 messages/60 seconds ceiling and HTTP 429 responses, but this is a community/support-forum claim, not a primary source, and could not be confirmed against official docs — treat any concrete rate-limit number as unverified.
- **Message editing/deletion**: The documented Messages endpoints cover only create (`POST`) and like/unlike; no `PATCH`/`PUT`/`DELETE` for an individual message was found. This research treats "bots cannot edit or delete a sent message" as the working assumption based on the absence of such an endpoint in `/docs/v3`, but a negative ("this endpoint does not exist") is inherently harder to fully prove than a positive; it's possible a message-delete capability exists in the app but is undocumented for third-party use.
- **Push service (`/tutorials/push`) full payload schema**: WebFetch returned a summarized description of the Bayeux handshake/subscribe/long-poll flow and event field names (type, user info, group ID, timestamp) but not a complete verbatim payload example; a deeper manual pass (e.g. viewing the page's rendered DOM in a browser rather than through automated fetch) might recover more exact field-level schema, but was not pursued further here since it doesn't bear on the calendar-events question.
- **Whether GroupMe's mobile/web app calls an *internal, undocumented* calendar API** (used by the official app but never published for third-party developers) could not be assessed — this research is scoped to publicly documented interfaces at `dev.groupme.com` only, per the task's primary-source constraint, and does not attempt reverse-engineering of internal/private endpoints.
- **Bot-to-group cardinality**: docs imply a bot is bound to one `group_id` at creation and don't document a way to move a bot to a different group; this wasn't explicitly stated as a limitation anywhere, only inferred from the absence of a "group_id" update parameter in the Bots endpoints.

### Primary-source URLs actually fetched and read for this research

1. https://dev.groupme.com
2. https://dev.groupme.com/docs/v3
3. https://dev.groupme.com/docs/responses
4. https://dev.groupme.com/docs/image_service
5. https://dev.groupme.com/tutorials
6. https://dev.groupme.com/tutorials/oauth
7. https://dev.groupme.com/tutorials/bots
8. https://dev.groupme.com/tutorials/push
9. https://github.com/orgs/groupme/repositories (official GitHub org index)
10. https://dev.groupme.com/session/new (login page — pre-login content only)
11. https://dev.groupme.com/bots (unauthenticated — confirmed 302 redirect to `/session/new`; page contents behind the login wall not observed)
12. https://dev.groupme.com/applications (unauthenticated — confirmed 302 redirect to `/session/new`; page contents behind the login wall not observed)
