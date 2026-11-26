const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const APP_URL = process.env.DEMO_URL || "https://aqi.akashg.me/";
const VIDEO_DIR = "/tmp/opencode/breathewise-video";
const OUTPUT = path.resolve(__dirname, "../../docs/artifacts/breathewise-demo-final.mp4");
const FAILURE_SHOT = "/tmp/opencode/breathewise-recording-failure.png";

async function waitForLiveObservation(page, coordinatePattern) {
  if (coordinatePattern) {
    await page.getByText(coordinatePattern).first().waitFor({ state: "visible", timeout: 45_000 });
  }
  await page.getByText("Fetching genuine environmental sensor telemetry...")
    .waitFor({ state: "hidden", timeout: 45_000 });
  await page.getByText("Data Provenance & Sensor Verification")
    .waitFor({ state: "visible", timeout: 45_000 });
  await page.getByText(/Coordinates:/).first()
    .waitFor({ state: "visible", timeout: 15_000 });
}

async function main() {
  fs.mkdirSync(VIDEO_DIR, { recursive: true });

  const browser = await chromium.launch({
    headless: false,
    slowMo: 400,
    executablePath: "/usr/bin/chromium",
    args: ["--disable-dev-shm-usage"],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: VIDEO_DIR, size: { width: 1440, height: 900 } },
    permissions: ["geolocation"],
    geolocation: { latitude: 28.6469, longitude: 77.316 },
  });

  const page = await context.newPage();
  page.setDefaultTimeout(45_000);

  page.on("requestfailed", (req) => {
    console.error("REQUEST FAILED:", req.url(), req.failure()?.errorText || "");
  });
  page.on("response", (res) => {
    if (res.url().includes("/api/v1/")) {
      console.log("API:", res.status(), res.url());
    }
  });
  page.on("pageerror", (err) => console.error("PAGE ERROR:", err.message));

  try {
    const airQuality = page.waitForResponse(
      (res) => res.url().includes("/api/v1/air-quality") && res.status() === 200,
      { timeout: 45_000 }
    );

    await page.goto(APP_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
    const response = await airQuality;
    const payload = await response.json();
    if (!payload.success || !payload.data) {
      throw new Error("Air-quality API returned no observation");
    }

    await waitForLiveObservation(page, /Coordinates:\s*28\.6289/);
    await page.getByText("Data Provenance & Sensor Verification")
      .scrollIntoViewIfNeeded();
    await page.waitForTimeout(1800);

    await page.getByRole("button", { name: "Delhi (Anand Vihar)" }).click();
    await waitForLiveObservation(page, /Coordinates:\s*28\.6469/);
    await page.getByText("Data Provenance & Sensor Verification")
      .scrollIntoViewIfNeeded();
    await page.waitForTimeout(1800);

    const scenes = [
      ["planner", "Daily Planner", "Personalized Daily Action Planner"],
      ["indoor", "Indoor Air Guide", "Evidence-Based Indoor Air Quality Assistant"],
      ["trends", "24-Hour Trends", "24-Hour Observation Trend"],
      ["sustainability", "Sustainable Transit", "Sustainable Mobility & Emission Impact"],
      ["map", "Station Map", "Monitoring Station Map"],
      ["assistant", "AI Assistant", "BreatheWise Assistant"],
    ];

    for (const [tabId, tabName, readyText] of scenes) {
      await page.getByRole("tab", { name: tabName }).click();
      await page.locator(`#panel-${tabId}`).scrollIntoViewIfNeeded();
      if (tabId === "assistant") {
        await page.getByRole("button", { name: /Quick question:/ }).first()
          .waitFor({ state: "visible", timeout: 30_000 });
      } else {
        await page.getByText(readyText).first().waitFor({ state: "visible", timeout: 30_000 });
      }
      await page.waitForTimeout(1600);
    }

    await page.getByRole("button", { name: /Quick question:.*Direct impact/i }).click();
    await page.getByRole("status", { name: "BreatheWise is thinking" })
      .waitFor({ state: "hidden", timeout: 60_000 });
    await page.getByRole("listitem").nth(2).waitFor({ state: "visible", timeout: 60_000 });
    await page.getByText(/AI-explained|Deterministic engine/).last()
      .waitFor({ state: "visible", timeout: 15_000 });
    await page.waitForTimeout(2500);

    await page.screenshot({ path: "/tmp/opencode/breathewise-final-frame.png" });
  } catch (err) {
    await page.screenshot({ path: FAILURE_SHOT, fullPage: true }).catch(() => {});
    throw err;
  } finally {
    const video = page.video();
    await context.close();
    if (video) {
      fs.copyFileSync(await video.path(), OUTPUT);
      console.log("VIDEO_SAVED:", OUTPUT);
    }
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
