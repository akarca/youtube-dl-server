const SERVER_URL = "https://youtubedl.nameocean.org/youtube-dl/cookies";
const TOKEN = "Kgueb5a-g4dbdHz_PoMTEbONKgkuJy1Y9yHMCa1YjyA";
const INTERVAL_MINUTES = 1;

async function syncCookies() {
  try {
    const stores = await browser.cookies.getAllCookieStores();
    const cookieMap = new Map();

    for (const store of stores) {
      const cookies = await browser.cookies.getAll({
        domain: ".youtube.com",
        storeId: store.id,
      });
      for (const c of cookies) {
        cookieMap.set(c.domain + "|" + c.name, c);
      }
    }

    const allCookies = Array.from(cookieMap.values());

    if (allCookies.length === 0) {
      await browser.storage.local.set({
        lastError: new Date().toLocaleTimeString() + " — No YouTube cookies found",
      });
      return;
    }

    const resp = await fetch(SERVER_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + TOKEN,
      },
      body: JSON.stringify({ cookies: allCookies }),
    });

    const ts = new Date().toLocaleTimeString();
    if (resp.ok) {
      const data = await resp.json();
      await browser.storage.local.set({
        lastSync: ts + " — " + data.count + " cookies synced",
        lastError: "",
      });
    } else {
      const data = await resp.json().catch(() => ({}));
      await browser.storage.local.set({
        lastError: ts + " — " + (data.error || resp.statusText),
      });
    }
  } catch (err) {
    await browser.storage.local.set({
      lastError: new Date().toLocaleTimeString() + " — " + err.message,
    });
  }
}

browser.runtime.onMessage.addListener((msg) => {
  if (msg.action === "sync_now") syncCookies();
});

syncCookies();
browser.alarms.create("cookie-sync", { periodInMinutes: INTERVAL_MINUTES });
browser.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "cookie-sync") syncCookies();
});
