# Survey Python client options for Teamup's API

Type: research
Status: resolved

## Question

Before building the sync engine, determine how it should talk to Teamup's API from Python:

1. Is there an actively-maintained, reasonably-trustworthy Python client library for Teamup's Calendar API on PyPI (or elsewhere)? If so, check its maintenance status (recent commits/releases), license, and whether it covers the create/update/delete/list-event endpoints this project needs.
2. If no good library exists, calling the REST API directly (e.g. via `requests`, already a natural fit alongside this project's other pinned dependencies) is the fallback -- confirm there's nothing that makes that impractical (auth scheme, pagination, rate limits documented anywhere).
3. Separately: is there a machine-readable spec for Teamup's API (an OpenAPI/Swagger file, a Postman collection, or similar) available anywhere -- from Teamup directly, or a well-known third-party mirror -- as an alternative to the JS-rendered apidocs.teamup.com pages that prior research (`hugo-natenite.net/HOSTED.md`) couldn't directly fetch? If one exists, it could shortcut or corroborate [Confirm Teamup's real API behavior](02-confirm-teamup-api-behavior.md).

This is pure documentation/library research -- no credentials needed, can run independently of the credentials-setup task.

## Answer

No actively-maintained, trustworthy Python client library exists for Teamup's Calendar API (the closest, `pyTeamUp`, hasn't been touched since December 2021 and is self-described as early-stage; the others are read-only, unmaintained, or have no discoverable source repo). **Recommendation: call the REST API directly via `requests`** — auth is a single static `Teamup-Token` header, and nothing found makes direct calls impractical. Bonus find: Teamup's full OpenAPI 3.0 spec is directly fetchable as raw YAML (not JS-rendered) and independently confirms the `remote_id`/`rrule`/`ristart_dt` field names the prior `hugo-natenite.net` research could only source from search snippets.

Full findings, citations, and the OpenAPI spec URL: [../../../docs/research/teamup-python-client-options.md](../../../docs/research/teamup-python-client-options.md)
