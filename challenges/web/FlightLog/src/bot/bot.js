const puppeteer = require("puppeteer");

const ALLOWED_HOST_RE = /^([a-z0-9-]+\.)*bsidespeoriac\.tf$/i;
const TARGET_RE =
  /^https?:\/\/challs\.bsidespeoriac\.tf:\d+\/note(?:\/?|[?#].*)?$/i;

async function visit(url) {
  if (!TARGET_RE.test(url)) {
    throw new Error(
      "URL must be http(s)://challs.bsidespeoriac.tf:<port>/note"
    );
  }

  const browser = await puppeteer.launch({
    headless: "new",
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
    ],
  });

  const page = await browser.newPage();

  await page.setRequestInterception(true);

  page.on("request", (req) => {
    try {
      const reqUrl = new URL(req.url());

      // Allow data/blob URLs
      if (
        reqUrl.protocol === "data:" ||
        reqUrl.protocol === "blob:"
      ) {
        return req.continue();
      }

      // Block everything except *.bsidespeoriac.tf
      if (
        reqUrl.protocol !== "http:" &&
        reqUrl.protocol !== "https:"
      ) {
        return req.abort();
      }

      if (!ALLOWED_HOST_RE.test(reqUrl.hostname)) {
        console.log("Blocked:", req.url());
        return req.abort();
      }

      req.continue();
    } catch {
      req.abort();
    }
  });

  try {
    await page.goto(url, {
      waitUntil: "networkidle2",
      timeout: 10000,
    });

    // Let any allowed JS execute.
    await page.waitForTimeout(5000);
  } finally {
    await browser.close();
  }
}

(async () => {
  const url = process.argv[2];

  if (!url) {
    console.error("Usage: node bot.js <url>");
    process.exit(1);
  }

  try {
    await visit(url);
    console.log("Done.");
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
})();