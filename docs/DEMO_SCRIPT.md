# Demo video script / storyboard

Status: **a real 37.2-second screen recording exists** at
`docs/artifacts/breathewise-demo.mp4` (raw Chromium capture in `docs/artifacts/demo-raw/`).
It was recorded with Playwright driving the locally running frontend at `127.0.0.1:3000` and the
local backend at `127.0.0.1:8000`, then converted with system ffmpeg. It is a **local verification
instance**, not a deployed application. The script below is the longer narration target; the
captured clip demonstrates the same steps in condensed form. No synthetic/fabricated video was used.

Target length: 3–4 minutes. Capture at 1280×720 or higher. Narrate only what is on screen.

---

## 0. Opening (0:00–0:20)
- Show the repository README and the phase report file names on screen.
- Say: "This is BreatheWise. Every number you see comes with its source, its timestamp, and its
  freshness status. When the data is not available, the app says so."

## 1. Precise location, not a city guess (0:20–0:55)
- Open the app. Use browser devtools geolocation override to set `28.6289, 77.2407`.
- Trigger "Use my location" and show the coordinates in the location status line.
- Open network tab: show `/api/v1/air-quality?lat=28.6289&lon=77.2407` and
  `/api/v1/recommendations/plan` carrying the same values.
- Say: "The exact device coordinates reach the observation and every derived feature. No city
  centre is substituted."

## 2. Provenance and honest data display (0:55–1:45)
- Show the Live Dashboard. Point to: provider source, reporting station, station coordinates,
  retrieved-at, measured-at, and freshness banner.
- Show a pollutant card with `min`, `max`, average and "Unit not provided by source".
- Say: "The source did not give us a unit, so we do not invent one. We show min, max and average
  as statistics — not as an AQI."

## 3. AQI refusal and stale data (1:45–2:20)
- Show a CPCB-backed observation where AQI reads "Unavailable" with the note about unverified
  averaging period.
- Show the stale warning and the retry button.
- Say: "Official CPCB AQI requires a verified averaging period. Until then the index stays
  unavailable. Stale data is labelled, not silently treated as live."

## 4. Tabs, indoor profile and assistant grounding (2:20–3:00)
- Keyboard-navigate the tablist with arrow keys; show focus moving and `aria-selected` changing.
- Open the Household Profile dialog: press Escape and show focus returning to the trigger.
- Ask the assistant a health question; show that the answer cites validated telemetry and
  approved actions only.
- Say: "The interface is keyboard operable, and the assistant explains approved policy output
  rather than inventing advice."

## 5. Map honesty and evidence (3:00–3:30)
- Open Station Map with live CPCB coordinates if reachable; otherwise show the explicit message
  that the map is hidden rather than plotting estimated positions.
- End on the test/artifact directory: "122 backend tests, 45 frontend tests, 85% application
  coverage, and the audit artifacts are in the repository. Live provider status and remaining
  blockers are documented, not hidden."

---

## Recording checklist
- No real API key visible on screen at any point.
- Show a failed/offline provider state deliberately; do not edit responses to fake a live feed.
- If the app is running locally, say "local verification instance" — do not imply a deployment.
- Keep the browser URL bar visible so same-origin `/api/v1` calls are demonstrable.
