const packet = document.querySelector("#packet");
const response = document.querySelector("#response");
const latency = document.querySelector("#latency");
const sampleButton = document.querySelector("#sampleButton");
const submitButton = document.querySelector("#submitButton");
const navLinks = document.querySelectorAll("[data-view]");
const viewPanels = document.querySelectorAll("[data-view-panel]");

const sample = {
  flightNumber: "AX-4817",
  tailNumber: "N742AX",
  dispatcher: "morgan.lee",
  origin: "KORD",
  destination: "KDEN",
  scheduledDeparture: "2026-06-08T21:35:00Z",
  routingStep: {
    station: "ORD-OCC",
    priority: "normal",
    lane: "westbound"
  },
  legs: [
    {
      from: "KORD",
      to: "KDEN",
      alternates: "KCOS,KPUB",
      reserveMinutes: 48
    }
  ]
};

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function show(value) {
  response.textContent = typeof value === "string" ? value : pretty(value);
}

function setView(name) {
  viewPanels.forEach((panel) => {
    const active = panel.dataset.viewPanel === name;
    panel.hidden = !active;
    panel.classList.toggle("active", active);
  });

  navLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.view === name);
  });
}

async function submitRelease() {
  const started = performance.now();
  latency.textContent = "Submitting";
  submitButton.disabled = true;

  try {
    const result = await fetch("/api/releases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: packet.value
    });

    const text = await result.text();
    const parsed = text ? JSON.parse(text) : {};
    show({
      httpStatus: result.status,
      endpoint: "/api/releases",
      ...parsed
    });
    latency.textContent = `${Math.round(performance.now() - started)} ms`;
  } catch (error) {
    show({ error: error.message });
    latency.textContent = "Failed";
  } finally {
    submitButton.disabled = false;
  }
}

packet.value = pretty(sample);
show({ ready: true, queue: "flight-release-desk" });

navLinks.forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const view = link.dataset.view;
    setView(view);
    history.replaceState(null, "", `#${view}`);
  });
});

sampleButton.addEventListener("click", () => {
  packet.value = pretty(sample);
  show({ sample: "loaded" });
  latency.textContent = "Idle";
});

submitButton.addEventListener("click", submitRelease);

const initialView = window.location.hash.replace("#", "") || "releases";
setView(document.querySelector(`[data-view-panel="${initialView}"]`) ? initialView : "releases");
