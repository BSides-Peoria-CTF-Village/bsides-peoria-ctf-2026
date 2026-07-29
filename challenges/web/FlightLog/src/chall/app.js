const express = require("express");
const fs = require("fs/promises");
const path = require("path");
const crypto = require("crypto");

const app = express();
const port = 3000;
const { visit } = require("../bot/bot");

app.use(express.json());
app.use(express.urlencoded({ extended: false }));

app.use((req, res, next) => {
    res.set(
        "Content-Security-Policy",
        "default-src *.bsidespeoriac.tf:*"
    );
    next();
});

const NOTES_DIR = path.join(__dirname, "notes");

app.get("/", (req, res) => {
    res.type("html").send(`
        <!doctype html>
        <html lang="en">
            <head>
                <meta charset="utf-8">
                <title>Flight Log</title>
            </head>
            <body>
                <h1>Flight Log</h1>
                <p>Leave a note for the flight crew.</p>
                <form action="/note" method="post">
                    <label for="note">Log entry</label><br>
                    <textarea id="note" name="note" rows="8" cols="60" required></textarea><br><br>
                    <button type="submit">Submit Note</button>
                </form>
            </body>
        </html>
    `);
});

app.post("/note", async (req, res) => {
    const { note } = req.body;

    if (!note) {
        return res.status(400).send("Please provide a log.");
    }

    try {
        await fs.mkdir(NOTES_DIR, { recursive: true });

        const id = crypto.randomUUID();
        const filepath = path.join(NOTES_DIR, `${id}.txt`);

        await fs.writeFile(filepath, note, "utf8");

        const url = `${req.protocol}://${req.get("host")}/note/${id}`;

        return res.status(201).json({
            id,
            url
        });
    } catch (err) {
        console.error(err);
        return res.status(500).send("Failed to save log.");
    }
});

app.get("/note/:id", async (req, res) => {
    try {
        const filepath = path.join(
            NOTES_DIR,
            `${req.params.id}.txt`
        );

        const note = await fs.readFile(filepath, "utf8");

        res.type("html").send(`
            <!doctype html>
            <html lang="en">
                <head>
                    <meta charset="utf-8">
                    <title>Flight Log</title>
                </head>
                <body>
                    <h1>Flight Log</h1>
                    <div class="note">
                        ${note}
                    </div>
                </body>
            </html>
        `);
    } catch {
        return res.status(404).send("Log not found.");
    }
});

app.post("/report", async (req, res) => {
    const { url } = req.body;

    if (!url) {
        return res.status(400).send("Please provide a URL.");
    }

    try {
        await visit(url);
        return res.send("Admin will review your report.");
    } catch (err) {
        return res.status(400).send(err.message);
    }
});

app.listen(port, () => {
    console.log(
        `Flight Log app listening at http://localhost:${port}`
    );
});