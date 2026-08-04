"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const statusBadge = document.getElementById("nav-status");
  const apiStatus = document.getElementById("api-status");
  const subscribeForm = document.getElementById("subscribe-form");
  const subscribeResult = document.getElementById("subscribe-result");
  const subscribeButton = subscribeForm?.querySelector('button[type="submit"]');

  function setSubscriptionMessage(message, type = "") {
    if (!subscribeResult) return;
    subscribeResult.textContent = message;
    subscribeResult.classList.remove("success", "error");
    if (type) subscribeResult.classList.add(type);
  }

  async function checkHealth() {
    try {
      const response = await fetch("/health", {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`Health check returned HTTP ${response.status}`);
      }

      const data = await response.json();
      if (statusBadge) {
        statusBadge.textContent = "All systems operational";
        statusBadge.classList.remove("offline");
      }
      if (apiStatus) apiStatus.textContent = data.status === "healthy" ? "Healthy" : data.status;
    } catch (error) {
      if (statusBadge) {
        statusBadge.textContent = "Service unavailable";
        statusBadge.classList.add("offline");
      }
      if (apiStatus) apiStatus.textContent = "Unavailable";
      console.error("Health check failed:", error);
    }
  }

  async function subscribe(event) {
    event.preventDefault();
    if (!subscribeForm) return;

    const formData = new FormData(subscribeForm);
    const email = String(formData.get("email") || "").trim();
    const company = String(formData.get("company") || "").trim();
    const consent = formData.get("consent") === "on";

    if (!email || !consent) {
      setSubscriptionMessage("Enter a valid work email and accept the consent option.", "error");
      return;
    }

    if (subscribeButton) {
      subscribeButton.disabled = true;
      subscribeButton.textContent = "Subscribing...";
    }
    setSubscriptionMessage("Saving your subscription...");

    try {
      const response = await fetch("/subscriptions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          email,
          company: company || null,
          source: "enterprise_landing_page",
          consent,
        }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Unable to save your subscription.");
      }

      setSubscriptionMessage(data.message || "Subscription saved.", "success");
      subscribeForm.reset();
    } catch (error) {
      setSubscriptionMessage(error.message || "Unable to subscribe right now.", "error");
    } finally {
      if (subscribeButton) {
        subscribeButton.disabled = false;
        subscribeButton.textContent = "Subscribe";
      }
    }
  }

  subscribeForm?.addEventListener("submit", subscribe);
  checkHealth();
});
