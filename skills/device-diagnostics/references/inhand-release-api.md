# InHand Official Release API Rules

Use this reference when the task is to fetch official changelog, firmware download URLs, manuals, specifications, flyers, or developer resources from the InHand website APIs.

## Official Sources Only

- Use only the official API host: `https://poweris.inhandnetworks.com`
- Use the official website origin and referer: `https://www.inhand.com/`
- Do not use mirrors, forums, or guessed download URLs when the API has no matching item.

## Execution Rules

- Do not use generic `Fetch` helpers for `poweris.inhandnetworks.com`; they often omit the required authentication headers and return `401`.
- Use shell `curl` with explicit headers for every vendor API request.
- Prefer `curl --fail-with-body -sS` so authentication failures remain visible in the output.
- Prefer `--get` with `--data-urlencode` for query parameters instead of hand-building long URLs when values are dynamic.
- If a request returns `401`, treat it as a bad request shape or missing headers. Verify `x-api-key`, `origin`, and `referer` before making any conclusion about product availability.
- Ignore browser-only noise such as `sec-ch-*`, `priority`, and desktop `user-agent` strings. They are not required business inputs for this skill.

## Required Local Model Resolution

Resolve both the exact model and the product-family prefix from the local device `status basic` result before querying the vendor website.

Rule:

1. Read the `model` and `firmware` fields from `device://<device_id>/status/basic` when the exact `device_id` is known.
2. If that fixed resource read fails with `Unknown resource uri`, call the `status` MCP tool with `subcommand: "basic"` and use that payload instead.
3. Trim surrounding whitespace from `model`.
4. Keep the trimmed model as `full_model`.
5. If the value contains `-`, take the substring before the first `-` and store it as `model_family`.
6. If the value does not contain `-`, use the full model as both `full_model` and `model_family`.
7. Use `model_family` only for product-family lookup. Keep `full_model` for variant-specific firmware lookup whenever the official API distinguishes variants.

Examples:

- `ODU2012-NANR` -> `full_model=ODU2012-NANR`, `model_family=ODU2012`
- `ODU2002-NATM` -> `full_model=ODU2002-NATM`, `model_family=ODU2002`
- `IR302` -> `full_model=IR302`, `model_family=IR302`

Do not invent `device://default/...` resource URIs; fixed resources require the actual configured `device_id`.

## Maintained Category-Group Mapping

Use the explicit mapping below to choose the `category-groups/<group>` endpoint. Do not brute-force other groups when a family is unmapped or not found.

Known families verified from the official `EnterpriseNetwork` response:

- `ER600`, `ER615`, `ER800`, `ER815`, `ER2000` -> `EnterpriseNetwork`
- `ES220`, `ES620` -> `EnterpriseNetwork`
- `ODU2002`, `ODU302` -> `EnterpriseNetwork`
- `FWA02`, `FWA12` -> `EnterpriseNetwork`
- `CPE02` -> `EnterpriseNetwork`
- `CR202`, `CR202-Lite`, `CR202-Pro`, `CR602` -> `EnterpriseNetwork`
- `IR302`, `IR305`, `IR315` -> `EnterpriseNetwork`

If `model_family` is not in the maintained map:

1. Call the official root directory endpoint once:

   ```text
   GET /api/plm/product/category-groups?locale=en
   ```

2. Return the latest published category-group catalog from that response as evidence. Prefer each entry's:
   - `id`
   - `name.en`
   - `state`
   - `metadata.updated_at` when present
3. Then stop and say in plain language that the vendor's public catalog does not yet let us confirm the product line for this model. Recommend confirming the exact model with technical support instead of guessing.
4. Do not choose a `category_group` from the root directory by inference.

## Category-Group Directory Endpoint

Use the root directory endpoint only when the maintained map does not contain `model_family`, and only to show the latest official category-group catalog before stopping:

```text
GET /api/plm/product/category-groups?locale=en
```

## Category-Group Endpoint

Use the group-specific endpoint below to resolve `product_category`, the canonical series identifier, and any variant metadata:

```text
GET /api/plm/product/category-groups/<group>?locale=en
```

Known example from the official site:

```text
GET /api/plm/product/category-groups/EnterpriseNetwork?locale=en
```

Matching rules:

1. Search `result.product_categories[].product_series[]`.
2. Treat a series as the match when:
   - `product_series.id == model_family`, or
   - `full_model` appears in that series `change_logs`, or
   - `full_model` appears in a `changelogMaps` key
3. Capture:
   - `category_group`
   - `matched_series_id = product_series.id`
   - `product_category = product_series.category_id`
   - `change_logs`
   - `changelogMaps`
4. Preserve `product_category` exactly as returned, even when it contains commas such as `InRouter,CellularRouter300`.
5. Do not call the root directory endpoint again after the one allowed unmapped-family fallback.
6. Do not hard-code `product_category`.

## Negative Result Rules

- Treat an official miss as a terminal result, not as a prompt to keep searching.
- If `model_family` is not in the maintained map, call the official root directory endpoint once, return that catalog result, and stop there.
- If the resolved official `category-groups/<group>` response does not expose a matching product or `product_category` for `model_family`, stop there.
- When `full_model` contains `-`, one fallback is allowed from the exact variant firmware query to a broader family query. After that single fallback, stop there.
- If the `published-files` query for `category=firmware` returns no matching item for the resolved firmware query key and `product_category`, stop there.
- Do not brute-force other group names, guessed `product_category` values, alternate `series_id` spellings, extra pages, guessed release-note tokens, or broader web searches after an official miss. The root directory fallback is for reporting only, not for guessing.
- When the official source has no matching firmware entry, state that the product is likely a pre-research, pre-release, or not-yet-published model on the public site, and recommend contacting technical support or the vendor for internal release information.
- Query `Manuals`, `Specifications`, `Flyers`, `DeveloperTools`, or `DeveloperDocumentation` only when the user explicitly asked for those document classes. Do not use them as fallback hunting when `firmware` is absent.

## Published File Endpoint

Use the published-files endpoint for actual resources:

```text
GET /api/plm/product/published-files?category=<category>&series_id=<series_id>&pageSize=8&pageNumber=1&product_category=<product_category>&locale=en
```

Required query parameters:

- `category`
- `series_id`
- `pageSize`
- `pageNumber`
- `product_category`
- `locale=en`

Firmware query rules:

1. Prefer `series_id=<full_model>` when `full_model` appears in the matched series `change_logs` or `changelogMaps`.
2. Otherwise use `series_id=<matched_series_id>`.
3. If that exact query returns no rows and `full_model` contains `-`, retry once with `series_id=<model_family>`.
4. When a family-level fallback returns mixed variants, upgrade only from the artifact whose `products[]` or `series_id` explicitly match the current `full_model`.
5. Preserve the raw endpoint used for the final conclusion.

## Categories To Query

Query these categories when needed:

- `firmware`
- `Manuals`
- `Specifications`
- `Flyers`
- `DeveloperTools`
- `DeveloperDocumentation`

Query order:

1. `firmware`
2. `Manuals`
3. `Specifications`
4. `Flyers`
5. `DeveloperTools`
6. `DeveloperDocumentation`

Only query categories relevant to the user request after `firmware`, unless a broader document inventory is requested.

## Header Rules

These headers are mandatory for vendor API replay:

- `accept: application/json, text/plain, */*`
- `origin: https://www.inhand.com`
- `referer: https://www.inhand.com/`
- `x-api-key: 48e8e814-3eaa-4c11-bc9e-f5092f755739`

Use the four headers above for:

- `category-groups/<group>`
- `published-files`
- `common/documents/<doc_id>`

If you already have a concrete `release-notes.md` URL or `access_token`, the release-note fetch normally needs only `accept`, `origin`, and `referer`. Do not invent or scrape tokens from unrelated pages.

## Response Fields You Must Use

Use exact vendor fields instead of guessing from filenames or marketing pages:

- `version`
- `release_date`
- `publish_date`
- `release_note.en`
- `release_note.cn`
- `desc.en`
- `desc.cn`
- `url`
- `doc_id`
- `products[]`
- `series_id`
- `need_auth`

Treat these fields as the source of truth for version ranking, changelog analysis, and exact artifact selection.

## Changelog And Download Resolution

Changelog priority:

1. `release_note.en`
2. `release_note.cn`
3. `desc.en`
4. `desc.cn`
5. `series/<series_id>/release-notes.md?...` only when an official response or user-provided trace already exposes the concrete URL or `access_token`

Normalize simple HTML such as `<br>` tags before comparing the changelog with the user's problem.

Download URL priority:

1. If `url` already points to object storage or another direct file URL, use it directly.
2. If `url` points to `/api/common/documents/<id>` or only `doc_id` is present, call the document-detail endpoint below and use the returned signed `result.url`.

## Document Detail Endpoint

Use this endpoint when you need the final signed firmware download URL:

```text
GET /api/common/documents/<doc_id>?verbose=100
```

The response typically returns:

- `result.url`: signed download URL
- `result.doc`: document metadata
- `result.needAuth`
- `result.ttl`

Use `result.url` as the final `upgrade --url ...` value.

## Curl Templates

Use these templates directly when querying the vendor API.

Fetch the latest category-group directory when the maintained map has no entry:

```bash
curl --fail-with-body -sS \
  'https://poweris.inhandnetworks.com/api/plm/product/category-groups?locale=en' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'origin: https://www.inhand.com' \
  -H 'referer: https://www.inhand.com/' \
  -H 'x-api-key: 48e8e814-3eaa-4c11-bc9e-f5092f755739'
```

Resolve `product_category` and series metadata:

```bash
curl --fail-with-body -sS \
  'https://poweris.inhandnetworks.com/api/plm/product/category-groups/EnterpriseNetwork?locale=en' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'origin: https://www.inhand.com' \
  -H 'referer: https://www.inhand.com/' \
  -H 'x-api-key: 48e8e814-3eaa-4c11-bc9e-f5092f755739'
```

Query published firmware files:

```bash
curl --fail-with-body -sS --get \
  'https://poweris.inhandnetworks.com/api/plm/product/published-files' \
  --data-urlencode 'category=firmware' \
  --data-urlencode 'series_id=FWA12-NANR' \
  --data-urlencode 'pageSize=8' \
  --data-urlencode 'pageNumber=1' \
  --data-urlencode 'product_category=InFWA' \
  --data-urlencode 'locale=en' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'origin: https://www.inhand.com' \
  -H 'referer: https://www.inhand.com/' \
  -H 'x-api-key: 48e8e814-3eaa-4c11-bc9e-f5092f755739'
```

Resolve a signed document URL:

```bash
curl --fail-with-body -sS \
  'https://poweris.inhandnetworks.com/api/common/documents/6909501182420c22e2da8b3c?verbose=100' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'origin: https://www.inhand.com' \
  -H 'referer: https://www.inhand.com/' \
  -H 'x-api-key: 48e8e814-3eaa-4c11-bc9e-f5092f755739'
```

Optional direct release-note fetch when an official trace already gives the token:

```bash
curl --fail-with-body -sS \
  'https://poweris.inhandnetworks.com/api/plm/product/series/ER800/release-notes.md?access_token=<token>&mode=inline&lang=en&category=firmware' \
  -H 'accept: */*' \
  -H 'origin: https://www.inhand.com' \
  -H 'referer: https://www.inhand.com/'
```

## Extraction Rules

Track these values internally while working:

- exact `full_model`
- normalized `model_family`
- current installed `firmware`
- resolved `category_group`
- resolved `matched_series_id`
- resolved firmware query `series_id`
- resolved `product_category`
- queried `category`
- official resource title
- official version
- `release_date` or `publish_date` when present
- changelog text source used
- official download URL
- `doc_id` when present

In the final user-facing answer, prefer plain language:

- Say which device model and installed firmware you checked.
- Say whether the vendor's public site shows a matching firmware entry for that exact model.
- If a matching entry exists, give the latest version, date, download URL, and the relevant changelog summary.
- If the response does not contain a changelog field, say the official site did not provide release notes for that package.
- If `model_family` is not in the maintained map, say the vendor's public catalog does not yet let us confirm the product line for this model, cite the root catalog endpoint you checked, and recommend contacting technical support or the vendor for confirmation.
- When no matching official firmware resource exists, say the vendor's public site does not show a firmware listing for this exact product, cite the official endpoint checked, and recommend contacting technical support or the vendor for unpublished or internal-release firmware information.
- Do not expose raw terms such as `model_family`, `category_group`, `matched_series_id`, or `product_category` in the final answer unless the user explicitly asks for low-level debug detail.

Do not invent placeholder resource titles, download URLs, versions, changelogs, release-note tokens, or extra search evidence after a negative result.

## Safety And Accuracy

- Treat the vendor API response as the source of truth.
- Do not guess `product_category`.
- Do not infer `category_group` from the root directory fallback.
- Do not invent a changelog when the API exposes only a firmware package.
- Do not invent `release-notes.md` access tokens or URLs.
- Do not keep retrying the public site after an authoritative miss just to find something to return.
- Prefer the exact full-model variant over a broader family-level artifact.
- If multiple entries are returned, prefer the newest official one by `release_date`, then `publish_date`, not by filename guess alone.
