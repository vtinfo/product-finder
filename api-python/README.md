# VIP Brand Finder - Python API example

A minimal, **standard-library-only** example that calls VIP's Brand Finder
Web Service (API) to list retail locations near a ZIP code that recently sold
your products.

- **Fork:** Web Services (API) - your backend signs and calls VIP directly.
- **Search:** locations within 10 miles of ZIP `05446`, customer ID `VIP`.
- **Python:** 3.13. No third-party packages (`requests` is not needed).

## Prompt
`/vip-brand-finder build a simple python api example using our finder api to show resulting locations of a search around zip 05446 using custid VIP and a secret value I will provide via env var FINDER_SAMPLE_VIP_SECRET. house this code inside docs/examples/ inside a new folder called "api-python". assume python 3.13; use minimal 3rd party packages; keep it super simple and lots of code comments to guide others because this is an EXAPMLE implementation`

## Run it

Provide your API secret via the `FINDER_SAMPLE_VIP_SECRET` environment
variable - never hard-code or commit it.

```powershell
# PowerShell
$env:FINDER_SAMPLE_VIP_SECRET = "your-secret-here"
python finder_example.py
```

```bash
# bash
export FINDER_SAMPLE_VIP_SECRET="your-secret-here"
python finder_example.py
```

## How the request is signed

Every call sends three headers:

- `vipCustID` - your 3-5 character VIP customer ID.
- `vipTimestamp` - GMT time, seconds forced to `:00`, day with **no** leading
  zero (e.g. `Tue, 17 Sep 2019 17:41:00 GMT`).
- `vipSignature` - lowercase SHA-256 hex of, concatenated **with no
  separators and in this exact order**:

  ```
  vipTimestamp + yourSecret + queryString + vipCustID
  ```

Two rules that cause most signature failures:

1. The `queryString` you hash must be **byte-for-byte identical** to the one
   you put in the URL. This example builds it once and reuses it.
2. Your server clock must be within ~10 minutes of VIP's (GMT).

## Notes

- HTTPS only - plain HTTP is not supported.
- "No results" is usually a **data** issue (excluded Classes of Trade, sales
  date range, distributor involvement), not a code issue.
- Confirm the exact API host and your `custID`/secret with VIP before going
  live.
- This is an **example**. AI-generated integration code must be reviewed and
  fact-checked before production use; it should not be the sole basis for a
  launch decision.
