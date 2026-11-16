"use strict";
const copyStatus = document.querySelector(".copy-status");

document.querySelectorAll("button[data-copy]").forEach((button) => {
  let resetTimer;
  button.addEventListener("click", async () => {
    clearTimeout(resetTimer);
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
      button.textContent = "Copied";
      copyStatus.textContent = `Copied ${button.dataset.copy}.`;
      resetTimer = setTimeout(() => {
        button.textContent = "Copy";
      }, 1800);
    } catch {
      button.textContent = "Copy";
      copyStatus.textContent =
        "Copy failed. Select the command and copy it manually.";
    }
  });
});
