(function () {
  "use strict";

  const form = document.getElementById("quiz-form");
  const root = document.getElementById("anticheat-root");
  if (!form || !root) return;

  const REPORT_URL = root.dataset.reportUrl;
  const MAX_VIOLATIONS = parseInt(root.dataset.maxViolations, 10) || 3;

  const banner = document.getElementById("violation-banner");
  const badge = document.getElementById("violation-badge");
  const autoSubmittedInput = document.getElementById("auto-submitted-input");

  let localCount = 0;
  let submitted = false;
  let devtoolsOpen = false;

  function updateBadge() {
    if (!badge) return;
    badge.textContent = "Violations: " + localCount + "/" + MAX_VIOLATIONS;
    badge.classList.toggle("danger", localCount > 0);
  }

  function showBanner(message) {
    if (!banner) return;
    banner.textContent = message;
    banner.classList.add("show");
    clearTimeout(showBanner._t);
    showBanner._t = setTimeout(() => banner.classList.remove("show"), 4000);
  }

  function doAutoSubmit(reason) {
    if (submitted) return;
    submitted = true;
    showBanner("Too many violations detected — submitting your answers now.");
    if (autoSubmittedInput) autoSubmittedInput.value = "1";
    const btn = form.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; btn.textContent = "Submitting…"; }
    // Give the banner a beat to render, then submit for real.
    setTimeout(() => {
      if (typeof form.requestSubmit === "function") form.requestSubmit();
      else form.submit();
    }, 300);
  }

  function report(type, detail) {
    if (submitted) return;
    localCount += 1;
    updateBadge();

    fetch(REPORT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: type, detail: detail || "" }),
      keepalive: true,
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && typeof data.count === "number") {
          localCount = data.count;
          updateBadge();
          if (data.should_auto_submit) doAutoSubmit(type);
        } else if (localCount >= MAX_VIOLATIONS) {
          doAutoSubmit(type);
        }
      })
      .catch(() => {
        // Network hiccup: still enforce the client-side threshold so a
        // team can't dodge auto-submit by cutting their own connection.
        if (localCount >= MAX_VIOLATIONS) doAutoSubmit(type);
      });
  }

  // ---------- Tab switching detection ----------
  document.addEventListener("visibilitychange", function () {
    if (document.hidden && !submitted) {
      showBanner("Warning: switching tabs is being recorded (" + (localCount + 1) + "/" + MAX_VIOLATIONS + ").");
      report("tab_hidden");
    }
  });

  window.addEventListener("blur", function () {
    // Blur fires for alt-tab and for devtools focus alike; only count it
    // if the page isn't already counted as hidden (avoid double-counting
    // the same tab-switch event across both listeners).
    if (!document.hidden && !submitted) {
      report("window_blur");
    }
  });

  // ---------- Copy protection ----------
  ["copy", "cut", "paste"].forEach(function (evt) {
    document.addEventListener(evt, function (e) {
      e.preventDefault();
      showBanner("Copy/paste is disabled during the quiz.");
      report(evt + "_attempt");
    });
  });

  document.addEventListener("contextmenu", function (e) {
    e.preventDefault();
    report("context_menu");
  });

  document.addEventListener("selectstart", function (e) {
    // Allow selection inside normal text inputs (e.g. none in this quiz,
    // but keep it generically safe) — otherwise block.
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA") return;
    e.preventDefault();
  });

  document.addEventListener("keydown", function (e) {
    const key = e.key ? e.key.toLowerCase() : "";
    const ctrlOrCmd = e.ctrlKey || e.metaKey;

    // Copy / cut / paste / select-all / view-source shortcuts.
    if (ctrlOrCmd && ["c", "x", "v", "u", "s", "p"].includes(key)) {
      e.preventDefault();
      report("devtools_shortcut", "ctrl+" + key);
      showBanner("That keyboard shortcut is disabled during the quiz.");
      return;
    }
    // DevTools open shortcuts: F12, Ctrl+Shift+I/J/C.
    if (key === "f12" || (ctrlOrCmd && e.shiftKey && ["i", "j", "c"].includes(key))) {
      e.preventDefault();
      report("devtools_shortcut", key);
      showBanner("Developer tools are disabled during the quiz.");
    }
  });

  // ---------- Heuristic devtools-open detection ----------
  // Not foolproof (nothing client-side can be), but catches the common
  // case of an undocked devtools panel resizing the viewport.
  const DEVTOOLS_THRESHOLD = 160;
  setInterval(function () {
    const widthGap = window.outerWidth - window.innerWidth;
    const heightGap = window.outerHeight - window.innerHeight;
    const likelyOpen = widthGap > DEVTOOLS_THRESHOLD || heightGap > DEVTOOLS_THRESHOLD;
    if (likelyOpen && !devtoolsOpen) {
      devtoolsOpen = true;
      report("devtools_open");
      showBanner("Developer tools appear to be open — please close them.");
    } else if (!likelyOpen) {
      devtoolsOpen = false;
    }
  }, 1500);

  updateBadge();
})();
