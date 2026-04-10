# Firmware Release

Use when the user asks about official firmware changelog, version availability, package download links, upgrade guidance, or upgrade execution, or when the current device problem may be explained by a known firmware fix published by the vendor.

Read [tool-contract.md](tool-contract.md) only when the exact MCP call shape matters. Read [inhand-release-api.md](inhand-release-api.md) before making website requests, and replay the vendor API with shell `curl` instead of generic `Fetch` helpers.

## Trigger Conditions

- The user explicitly asks whether a newer firmware exists, whether an upgrade is recommended, or asks for firmware download links or changelog details.
- The current device problem may be caused by a bug or regression that could already be fixed in an official release note.
- The user approves an upgrade and needs help selecting or applying the target official version.

## Collection Sequence

1. Resolve the target `device_id` first. Do not invent `default` for fixed resource URIs.
2. Read basic device info before any vendor website request:
   - If the exact `device_id` is known, prefer the fixed resource `device://<device_id>/status/basic`.
   - If `resources/read` returns `Unknown resource uri` or the exact `device_id` is not yet confirmed, immediately fall back to the `status` MCP tool with `subcommand: "basic"`.
3. Obtain both the current `model` and current `firmware` from the `status basic` payload. Local `status basic` is the source of truth for the installed version.
4. Derive two identifiers from `model`:
   - `full_model`: the trimmed model exactly as returned by the device
   - `model_family`: if `model` contains `-`, use the substring before the first `-`; otherwise use the full model
   - Example: `ODU2012-NANR` keeps `full_model=ODU2012-NANR` and `model_family=ODU2012`
5. Resolve the official `category_group` from the explicit mapping table in [inhand-release-api.md](inhand-release-api.md).
   - If `model_family` is not in the maintained map, call the official root directory endpoint `category-groups?locale=en` once with shell `curl` and the required headers.
   - Return the latest published category-group catalog from that response as evidence. Prefer each entry's `id`, `name.en`, `state`, and `metadata.updated_at` when present.
   - Then stop and tell the user in plain language that the vendor's public catalog does not yet let us confirm the product line for this model, so it is not safe to guess a firmware package. Recommend confirming the exact model with technical support instead of guessing.
   - Do not say things like "the skill has no verified `category_group` mapping" unless the user explicitly asks for debug detail.
   - Do not guess unknown groups from that directory.
6. Call the official `category-groups/<group>` API with shell `curl --fail-with-body -sS` and the required `accept`, `origin`, `referer`, and `x-api-key` headers.
7. Match the product family inside the `category-groups` response:
   - Prefer a `product_series.id` equal to `model_family`
   - Also treat the series as a match when `full_model` appears in that series `change_logs` list or in a `changelogMaps` key
   - Capture the matched `product_category` from `product_series.category_id` exactly as returned by the API
8. If the official category lookup does not expose the resolved product family, stop immediately. Tell the user in plain language that the vendor's public site does not currently show a firmware entry for this model or product line, and recommend contacting technical support. Do not keep searching the website.
9. Resolve the firmware query key:
   - If `full_model` appears in the matched series `change_logs` or `changelogMaps`, query `published-files` with `series_id=<full_model>`
   - Otherwise query `published-files` with `series_id=<matched product_series.id>`
   - If that exact query returns no rows and `full_model` contains `-`, retry once with the broader `model_family` value for advisory purposes
10. Query `published-files` with `category=firmware`.
11. Select the correct firmware artifacts from the response:
   - Prefer entries whose `products[]` or `series_id` explicitly contain `full_model`
   - Otherwise prefer entries whose `series_id` matches the resolved family-level series
   - If a family-level fallback returns mixed variants and none explicitly matches `full_model`, stop and tell the user in plain language that the public site only shows broader family packages, not a package clearly marked for this exact device model; do not guess a cross-variant package for upgrade
12. Build changelog text from the firmware artifact itself:
   - Prefer `release_note.en`
   - Fall back to `release_note.cn`, then `desc.en`, then `desc.cn`
   - Normalize `<br>` tags and other simple HTML markup into readable text before comparing it with the current problem
   - Only call `series/<series_id>/release-notes.md` when an official response or a user-provided trace already gives a concrete URL or `access_token`; do not invent tokens
13. Resolve the actual download URL:
   - If the firmware item `url` already points to object storage or another direct file URL, use it as the download URL
   - If the firmware item `url` points to `/api/common/documents/<id>` or only `doc_id` is present, call `common/documents/<doc_id>?verbose=100` and use the returned signed `result.url`
14. Compare the current firmware against the available official versions:
   - Prefer the explicit `version` field over filename guesses
   - Sort artifacts by `release_date`, then `publish_date`, newest first
   - When the current firmware string parses cleanly as a dotted version, compare segment-wise; otherwise explain that ordering is inferred from vendor publish metadata
15. Form the recommendation:
   - If there is no newer official version, say so clearly
   - If the changelog fixes the current problem, recommend upgrade
   - If a newer version exists but the changelog does not address the current problem, give neutral advice and explain the likely limited benefit
   - If the changelog includes breaking changes, compatibility notes, reset behavior, or downgrade restrictions, call them out explicitly as risks
16. If the user wants to upgrade:
   - If no version was specified, list the available candidate versions and require the user to choose one explicitly
   - If a version was specified, require an exact official match
   - Same-version reinstall is allowed only when the user explicitly asks for that exact version
   - A downgrade to an older official version is allowed only when the target version's official release note does not mention downgrade, compatibility, or rollback risk
   - If the target version note contains warnings such as `Breaking`, `Can not downgrade`, or similar compatibility restrictions, stop and explain the risk instead of proceeding automatically
17. Execute upgrade only after explicit approval:
   - Resolve the exact target artifact and final official download URL first
   - Call MCP `upgrade` with `subcommand: "--url <final official url>"`
   - Surface the tool result and remind the user that the action is disruptive

## Interpretation

- `status basic` is the source of truth for the current model and installed firmware. The vendor website lookup starts only after that local read succeeds.
- The root `category-groups?locale=en` directory is a one-time visibility fallback only when the maintained `category_group` map has no entry for `model_family`; it is not a license to guess a group.
- The official `category-groups/<group>` response is the source of truth for `product_category`, `product_series.id`, and variant metadata such as `change_logs` and `changelogMaps`.
- The `published-files` firmware item is the source of truth for available versions, release dates, release-note text, document identifiers, and the first-stage download reference.
- `common/documents/<doc_id>` is the source of truth for the final signed download URL when the firmware item does not already expose a direct file URL.
- The full `model` takes precedence over the normalized family whenever the official response distinguishes variants.
- A normalized `series_id` mismatch usually means the model parsing rule or selected product category is wrong.
- An `Unknown resource uri` error means the fixed resource URI was wrong, usually because `device_id` was guessed. Retry with the real `device_id` or fall back to the `status` tool instead of stopping the playbook.
- An HTTP `401` from the vendor API means the request was not replayed with the required headers or API key; fix the request first instead of treating that response as evidence that the product is absent.
- If the official category lookup or the official firmware query does not contain the resolved product after the one allowed family fallback, treat that as the final public-site result. Do not continue browsing the official website for more guesses.
- If the vendor API returns manuals or specifications but no matching firmware for the exact device model, state that no official firmware entry was found for that exact series.
- If `release_note` is absent, state that the official API did not expose a changelog for that artifact instead of inventing one.
- If multiple firmware entries exist, prefer the newest official entry by explicit vendor metadata and keep the exact endpoint used as evidence.

## Handoff Notes

- Do not continue searching outside the resolved official source when the product is absent there.
- When `model_family` is absent from the maintained map, fetch the official root category-group directory once, return its result, and then stop.
- Do not continue searching inside the official site after an authoritative miss from `category-groups` or `published-files`.
- Do not stop the playbook on `Unknown resource uri`; retry the local basic-info read with `status basic`.
- Do not conclude that the product is absent from the official source based on an unauthenticated `401` response.
- Do not invent `release-notes.md` URLs or access tokens. Use them only when another official response or a user-provided trace already contains the concrete value.
- Do not infer a `category_group` from the root directory fallback.
- Do not use a family-level firmware artifact to upgrade a different full-model variant.
- If the product is absent from the public site, tell the user it may be a pre-research or unpublished model and recommend contacting technical support.
- Keep evidence compact and cite the exact API endpoint or source URL used for the conclusion.
- Translate internal reasoning into user language in the final answer. Say "I could not confirm a public firmware package for this model on the vendor site" instead of exposing raw terms such as `model_family`, `category_group`, `product_category`, or "maintained map".
