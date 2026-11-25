# LinkedIn process post — BreatheWise

Draft written from work actually performed in this workspace. Every number below is reproducible
with the commands in `docs/PHASE_2_CPCB_REPORT.md`. No deployment or live-provider claim is included.

---

I built BreatheWise, an evidence-based air-quality assistant for Indian families, as a
production-style full-stack project rather than a demo with hardcoded numbers.

**The problem I started with:** the first version accepted a city name and quietly swapped in
pre-registered coordinates. That is fine for a mock, but wrong for a product that claims to tell
a family whether their child should play outside. I treated that as a defect, not a detail.

**What I changed:**

1. Precise device geolocation and geocoder results now flow unchanged into every downstream
   feature — observation, plan, indoor guidance, assistant, comparison and trends. The assistant
   refuses to answer when it has no validated observation instead of inventing an AQI of 150.

2. I replaced guessed CPCB payloads with an adapter written against the actual data.gov.in
   resource schema (`state`, `city`, `station`, `last_update`, latitude/longitude,
   `pollutant_id`, `min_value`, `max_value`, `avg_value`). Rows are grouped by station **and**
   source timestamp; malformed and null values become `null`, never zero; units stay unknown when
   the provider does not supply them.

3. Filter verification is explicit rather than assumed. Tamil Nadu and Chennai filters are probed
   at runtime and reported through a dedicated endpoint. When a filter is unverified, the adapter
   falls back to bounded unfiltered pagination plus exact local filtering — it does not relabel
   unrelated rows.

4. Freshness is honest: ≤2h verified, 2–6h delayed, >6h stale, invalid/missing unavailable. A
   failed refresh preserves the previous valid observation but marks it stale. Official AQI stays
   unavailable until the feed's averaging-period contract is verified; pollutant averages are
   never presented as an index.

5. The UI shows provenance, real station coordinates, source time versus retrieval time, min/max,
   and explicit empty/error/stale states. The map is hidden when only estimated city-centre
   coordinates exist.

**Verification, not victory laps:** 122 backend tests and 45 frontend tests pass; lint, format,
type-check and build are clean; application coverage is 85%. Live data.gov.in requests from my
machine timed out repeatedly, so I documented the provider as unreachable and the filters as
unverified rather than claiming a successful integration.

**What this taught me:** the hardest part of "AI for social good" is not the model. It is deciding
what the system must refuse to say when the data is missing, stale, or unverified — and then
building the tests that keep that refusal intact.

*Work in progress: live provider verification, third-party audits, deployment and a recorded demo
are tracked separately in the repository's phase report.*
