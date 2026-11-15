"use strict";
const status = document.querySelector(".copy-status");
let statusTimer;
document.querySelectorAll("button[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      button.textContent = "Copied";
      status.textContent = "Command copied to clipboard.";
      status.classList.add("visible");
      clearTimeout(statusTimer);
      statusTimer = setTimeout(() => {
        status.classList.remove("visible");
      }, 2400);
      setTimeout(() => {
        button.textContent = "Copy";
      }, 1800);
    } catch {
      status.textContent =
        "Clipboard unavailable. Select and copy the command directly.";
      status.classList.add("visible");
    }
  });
});
