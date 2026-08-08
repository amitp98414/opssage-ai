const $ = (id) => document.getElementById(id);

const apiKeyInput = $("api-key");
const promptInput = $("prompt");
const modeInput = $("mode");
const form = $("agent-form");
const runButton = $("run-button");
const statusText = $("form-status");
const responseBox = $("response");

const savedKey = sessionStorage.getItem("opssage_api_key");
if (savedKey) apiKeyInput.value = savedKey;

function setStatus(message, type = "") {
  statusText.textContent = message;
  statusText.className = `form-status ${type}`.trim();
}

function renderEvents(events) {
  const container = $("events");
  if (!events.length) {
    container.innerHTML = '<div class="event"><span class="time">--:--:--</span><span class="message">No agent activity yet.</span><span class="status">standby</span></div>';
    return;
  }

  container.innerHTML = events.map((event) => {
    const time = new Date(event.timestamp).toLocaleTimeString([], { hour12: false });
    const css = event.status === "failed" ? "event failed" : "event";
    const agent = event.agent ? `${event.agent}: ` : "";
    return `<div class="${css}"><span class="time">${time}</span><span class="message">${agent}${event.message}</span><span class="status">${event.status}</span></div>`;
  }).join("");
}

async function refreshControlCenter() {
  try {
    const [statusResponse, eventsResponse] = await Promise.all([
      fetch("/control/status", { cache: "no-store" }),
      fetch("/control/events?limit=50", { cache: "no-store" }),
    ]);

    if (!statusResponse.ok || !eventsResponse.ok) throw new Error("Control Center API unavailable");

    const status = await statusResponse.json();
    const events = await eventsResponse.json();

    $("system-status").textContent = status.system === "online" ? "SYSTEM ONLINE" : "SYSTEM DEGRADED";
    $("active-agent").textContent = status.active_agent || "STANDBY";
    $("event-count").textContent = status.event_count ?? 0;
    $("metric-control").textContent = status.system === "online" ? "READY" : "DEGRADED";
    renderEvents(events.events || []);
  } catch (error) {
    $("system-status").textContent = "SYSTEM UNAVAILABLE";
    $("metric-control").textContent = "OFFLINE";
    setStatus(error.message, "error");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const apiKey = apiKeyInput.value.trim();
  const prompt = promptInput.value.trim();
  const mode = modeInput.value;

  if (!apiKey) {
    setStatus("Execution API key is required for agent execution.", "error");
    apiKeyInput.focus();
    return;
  }
  if (prompt.length < 3) {
    setStatus("Command must contain at least 3 characters.", "error");
    promptInput.focus();
    return;
  }

  sessionStorage.setItem("opssage_api_key", apiKey);
  runButton.disabled = true;
  setStatus("Agent is executing...", "");
  responseBox.className = "response";
  responseBox.textContent = "OPSAGE CORE / EXECUTING\n\nRouting request to the selected agent...";

  try {
    const response = await fetch("/agent/run", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify({ prompt, mode }),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Agent request failed (${response.status})`);

    responseBox.textContent = `${data.agent || "Agent"}\n\n${data.answer || "No response returned."}`;
    setStatus(`Task ${data.task_id || "completed"} finished.`, "success");
    await refreshControlCenter();
  } catch (error) {
    responseBox.textContent = `EXECUTION ERROR\n\n${error.message}`;
    setStatus(error.message, "error");
  } finally {
    runButton.disabled = false;
  }
});

$("clear-key").addEventListener("click", () => {
  sessionStorage.removeItem("opssage_api_key");
  apiKeyInput.value = "";
  setStatus("Execution key cleared from this browser session.");
});

$("refresh").addEventListener("click", refreshControlCenter);

refreshControlCenter();
setInterval(refreshControlCenter, 4000);
