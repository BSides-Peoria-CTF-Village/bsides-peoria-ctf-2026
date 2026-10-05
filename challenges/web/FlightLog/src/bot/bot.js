const fs = require("fs/promises");
const path = require("path");
const puppeteer = require("puppeteer");

const ALLOWED_HOST_RE = /^(localhost|127\.0\.0\.1|([a-z0-9-]+\.)*bsidespeoriac\.tf)$/i;
const FLAG_PATH = path.resolve(__dirname, "..", "..", "flag.txt");
const BOT_ORIGIN = new URL(process.env.BOT_ORIGIN || "http://localhost:3000");

function resolveNotePath(notePath) {
  try {
    if (typeof notePath !== "string") {
      return null;
    }

    const target = new URL(notePath, BOT_ORIGIN);

    if (target.origin !== BOT_ORIGIN.origin) {
      return null;
    }

    if (!/^\/note\/[0-9a-f-]{36}$/i.test(target.pathname)) {
      return null;
    }

    return target;
  } catch {
    return null;
  }
}

async function loadFlag() {
  try {
    return (await fs.readFile(FLAG_PATH, "utf8")).trim();
  } catch (err) {
    console.warn("Flag file not available; continuing without cookie.", err.message);
    return "";
  }
}

async function visit(notePath) {
  const target = resolveNotePath(notePath);

  if (!target) {
    throw new Error(
      "Note path must be /note/<UUID>."
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
  const flag = await loadFlag();

  if (flag) {
    await page.setCookie({
      name: "flag",
      value: flag,
      url: target.href,
      path: "/",
    });
  }

  await page.setRequestInterception(true);

  page.on("request", (req) => {
    try {
      const reqUrl = new URL(req.url());

      if (
        reqUrl.protocol === "data:" ||
        reqUrl.protocol === "blob:"
      ) {
        return req.continue();
      }

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
    await page.goto(target.href, {
      waitUntil: "networkidle2",
      timeout: 10000,
    });

    // Let any allowed JS execute.
    await new Promise((resolve) => setTimeout(resolve, 5000));
  } finally {
    await browser.close();
  }
}

module.exports = { visit, resolveNotePath };

if (require.main === module) {
  (async () => {
    const notePath = process.argv[2];

    if (!notePath) {
      console.error("Usage: node bot.js /note/<UUID>");
      process.exit(1);
    }

    try {
      await visit(notePath);
      console.log("Done.");
    } catch (err) {
      console.error(err.message);
      process.exit(1);
    }
  })();
}
