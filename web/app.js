"use strict";

const command = document.getElementById("install-command");
const platformTabs = Array.from(document.querySelectorAll("[data-platform]"));

function selectPlatform(platform, focus = false) {
  if (!command) return;
  const download = new URL(
    `downloads/${command.dataset.wheel}`,
    document.baseURI,
  );
  download.hash = `sha256=${command.dataset.sha}`;
  const requirement = `scrip-companion[desktop] @ ${download.href}`;
  command.textContent =
    platform === "windows"
      ? `python -m venv .scrip-env\n.scrip-env\\Scripts\\python.exe -m pip install "${requirement}"\n.scrip-env\\Scripts\\scrip.exe desktop --demo`
      : `python3 -m venv .scrip-env\n.scrip-env/bin/python -m pip install "${requirement}"\n.scrip-env/bin/scrip desktop --demo`;
  const program =
    platform === "windows"
      ? ".scrip-env\\Scripts\\scrip.exe"
      : ".scrip-env/bin/scrip";
  const local = `${program} --data-dir .scrip-dev`;
  document.getElementById("service-command").textContent =
    `${local} init --port 18765\n${local} serve --port 18765`;
  document.getElementById("desktop-command").textContent =
    `${local} desktop\n${local} status`;
  document.getElementById("adapter-command").textContent =
    `${local} adapter capabilities --adapter claude-code\n${local} adapter config --adapter claude-code\n${local} adapter config --adapter antigravity`;
  for (const tab of platformTabs) {
    const selected = tab.dataset.platform === platform;
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected) {
      document
        .getElementById("install-panel")
        .setAttribute("aria-labelledby", tab.id);
      if (focus) tab.focus();
    }
  }
}

for (const tab of platformTabs) {
  tab.addEventListener("click", () => selectPlatform(tab.dataset.platform));
  tab.addEventListener("keydown", (event) => {
    if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const platform =
        event.key === "Home"
          ? "windows"
          : event.key === "End"
            ? "unix"
            : tab.dataset.platform === "windows"
              ? "unix"
              : "windows";
      selectPlatform(platform, true);
    }
  });
}
selectPlatform(/Win/i.test(navigator.platform) ? "windows" : "unix");

for (const button of document.querySelectorAll("[data-copy]")) {
  button.addEventListener("click", async () => {
    const source = document.getElementById(button.dataset.copy);
    const status = document.getElementById("copy-status");
    try {
      await navigator.clipboard.writeText(source.textContent);
      status.textContent =
        "Copied. Review the commands before running them in a terminal.";
    } catch {
      status.textContent =
        "Clipboard is unavailable. Select and copy the commands above.";
    }
  });
}
