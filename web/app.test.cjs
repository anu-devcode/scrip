const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function page() {
  const nodes = new Map();
  function node(id, dataset = {}) {
    const item = { id, dataset, textContent: "", attrs: {}, handlers: {}, tabIndex: 0,
      setAttribute(name, value) { this.attrs[name] = value; },
      addEventListener(name, handler) { this.handlers[name] = handler; },
      focus() { this.focused = true; } };
    nodes.set(id, item);
    return item;
  }
  const install = node("install-command", {wheel: "scrip_companion-0.1.0a1-py3-none-any.whl", sha: "a".repeat(64)});
  const tabs = [node("tab-windows", {platform: "windows"}), node("tab-unix", {platform: "unix"})];
  for (const id of ["install-panel", "service-command", "desktop-command", "adapter-command", "copy-status"]) node(id);
  const copy = node("copy", {copy: "install-command"});
  const writes = [];
  const context = {
    URL,
    navigator: {platform: "Win32", clipboard: {async writeText(text) { writes.push(text); }}},
    document: {baseURI: "https://scrip.example/quickstart.html", getElementById(id) { return nodes.get(id); },
      querySelectorAll(selector) { return selector === "[data-platform]" ? tabs : [copy]; }},
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "app.js"), "utf8"), context);
  return {nodes, tabs, copy, writes, install};
}

test("Windows installer uses the public versioned wheel, hash and real command line breaks", () => {
  const {install, nodes, writes} = page();
  const lines = install.textContent.split("\n");
  assert.equal(lines.length, 3);
  assert.equal(lines[0], "python -m venv .scrip-env");
  assert.ok(lines[1].startsWith(".scrip-env\\Scripts\\python.exe -m pip install"));
  assert.ok(lines[1].includes("https://scrip.example/downloads/scrip_companion-0.1.0a1-py3-none-any.whl#sha256=" + "a".repeat(64)));
  assert.equal(lines[2], ".scrip-env\\Scripts\\scrip.exe desktop --demo");
  assert.ok(nodes.get("service-command").textContent.startsWith(".scrip-env\\Scripts\\scrip.exe"));
  assert.deepEqual(writes, []);
});

test("Keyboard platform selection changes commands and copy requires the user's click", async () => {
  const {install, nodes, tabs, copy, writes} = page();
  tabs[0].handlers.keydown({key: "ArrowRight", preventDefault() {}});
  assert.equal(tabs[1].attrs["aria-selected"], "true");
  assert.equal(tabs[1].focused, true);
  assert.ok(install.textContent.startsWith("python3 -m venv"));
  assert.ok(nodes.get("desktop-command").textContent.startsWith(".scrip-env/bin/scrip"));
  assert.deepEqual(writes, []);
  await copy.handlers.click();
  assert.deepEqual(writes, [install.textContent]);
  assert.match(nodes.get("copy-status").textContent, /^Copied/);
});
