"use strict";

// Clipboard is optional. Selecting the visible text works on file:// and offline.
const copyStatus = document.getElementById("copy-status");
document.querySelectorAll("[data-copy]").forEach((button) => {
  const originalLabel = button.getAttribute("aria-label");
  const idle = document.createElement("span");
  idle.className = "copy-label";
  idle.append(...button.childNodes);
  const done = document.createElement("span");
  done.className = "copy-done";
  done.textContent = "✓ Copied";
  done.setAttribute("aria-hidden", "true");
  button.append(idle, done);
  let resetTimer;
  let copying = false;
  const reset = () => {
    button.classList.remove("is-copied");
    idle.removeAttribute("aria-hidden");
    done.setAttribute("aria-hidden", "true");
    if (originalLabel === null) button.removeAttribute("aria-label");
    else button.setAttribute("aria-label", originalLabel);
  };
  button.addEventListener("click", async () => {
    if (copying) return;
    copying = true;
    clearTimeout(resetTimer);
    reset();
    const status = document.getElementById(button.dataset.copyStatus) || copyStatus;
    const source = document.getElementById(button.dataset.copy);
    const text = source instanceof HTMLTextAreaElement ? source.value : source.textContent;
    try {
      if (!navigator.clipboard || !window.isSecureContext) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(text);
      button.classList.add("is-copied");
      idle.setAttribute("aria-hidden", "true");
      done.removeAttribute("aria-hidden");
      button.setAttribute("aria-label", "Copied");
      const announcement = document.createElement("span");
      announcement.className = "copy-announcement";
      announcement.textContent = "Copied to clipboard.";
      status.replaceChildren(announcement);
      resetTimer = setTimeout(reset, 2400);
    } catch {
      if (source instanceof HTMLTextAreaElement) {
        source.focus();
        source.select();
      } else {
        const range = document.createRange();
        range.selectNodeContents(source);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      }
      status.textContent = "Text selected. Use your device’s Copy action, or press Command+C / Ctrl+C.";
    } finally {
      copying = false;
    }
  });
});

// Dataset examples are static HTML. Without JavaScript, every labeled group stays visible.
const filters = document.querySelector(".dataset-filters");
const filterButtons = [...document.querySelectorAll("[data-dataset-filter]")];
const datasetViews = [...document.querySelectorAll("[data-dataset-view]")];
const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
const activeAnimations = new Set();

function motion(element, frames, options = {}) {
  if (motionPreference.matches || typeof element.animate !== "function") return null;
  const animation = element.animate(frames, {
    duration: 420,
    easing: "cubic-bezier(.22, 1, .36, 1)",
    ...options,
  });
  activeAnimations.add(animation);
  const clean = () => activeAnimations.delete(animation);
  animation.finished.then(clean, clean);
  return animation;
}

function showDataset(value, animate = true) {
  filterButtons.forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.datasetFilter === value));
  });
  datasetViews.forEach(view => {
    view.getAnimations?.().forEach(animation => animation.cancel());
    view.hidden = view.dataset.datasetView !== value;
    if (!view.hidden && animate) {
      motion(view, [{ opacity: .5, transform: "translateY(5px)" }, { opacity: 1, transform: "translateY(0)" }], { duration: 220 });
    }
  });
}
if (filters && filterButtons.length && datasetViews.length) {
  filters.hidden = false;
  showDataset("2026", false);
  filterButtons.forEach(button => {
    button.addEventListener("click", () => showDataset(button.dataset.datasetFilter));
  });
}

// Entrances run once; content is never hidden by CSS or dependent on an observer.
const entrances = document.querySelectorAll(
  ".hero > *, .section-heading, .setup-step, .review-note, .dataset-heading, .dataset-intro, .dataset-sources, .research-chart, .dataset-filters, .dataset-details, .dataset-actions, .privacy, footer"
);
if (!motionPreference.matches && "IntersectionObserver" in window) {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      observer.unobserve(entry.target);
      motion(entry.target, [
        { opacity: 0, transform: "translateY(12px)" },
        { opacity: 1, transform: "translateY(0)" },
      ]);
    });
  }, { rootMargin: "0px 0px 40px 0px", threshold: 0 });
  entrances.forEach(element => observer.observe(element));
  motionPreference.addEventListener("change", event => {
    if (event.matches) observer.disconnect();
  });
}

document.querySelectorAll(".dataset-details").forEach(details => {
  details.addEventListener("toggle", () => {
    if (!details.open) return;
    [...details.children].filter(child => child.tagName !== "SUMMARY").forEach(child => {
      motion(child, [{ opacity: .3 }, { opacity: 1 }], { duration: 180 });
    });
  });
});

// Respect a preference change even when motion was disabled on the initial load.
motionPreference.addEventListener("change", event => {
  if (event.matches) activeAnimations.forEach(animation => animation.cancel());
});
