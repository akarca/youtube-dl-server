document.addEventListener("DOMContentLoaded", async () => {
  const data = await browser.storage.local.get(["lastSync", "lastError"]);
  updateStatus(data);
});

browser.storage.onChanged.addListener(() => {
  browser.storage.local.get(["lastSync", "lastError"]).then(updateStatus);
});

function updateStatus(data) {
  const el = document.getElementById("status");
  let html = "";
  if (data.lastSync) html += `<div class="ok">${data.lastSync}</div>`;
  if (data.lastError) html += `<div class="err">${data.lastError}</div>`;
  if (!data.lastSync && !data.lastError) html = "Waiting for first sync...";
  el.innerHTML = html;
}

document.getElementById("sync").addEventListener("click", () => {
  browser.runtime.sendMessage({ action: "sync_now" });
  document.getElementById("status").innerHTML = '<div class="ok">Syncing...</div>';
});
