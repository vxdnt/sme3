(() => {
  let expiresAt = Date.now() + 15000;
  const qrImg = document.getElementById("qrImg");
  const qrProgress = document.getElementById("qrProgress");
  const qrStatus = document.getElementById("qrStatus");

  function applyToken(data) {
    if (!data || data.type !== "token") return;
    qrImg.src = data.qr || "";
    expiresAt = Number(data.expiresAt || Date.now() / 1000) * 1000;
    qrStatus.textContent = "Rotates every 15 seconds";
  }

  async function refreshQrToken() {
    try {
      const res = await fetch("/api/qr", { cache: "no-store" });
      if (!res.ok) return;
      applyToken(await res.json());
    } catch (_) {}
  }

  function startEventStream() {
    const es = new EventSource("/events");
    es.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "token") applyToken(data);
    };
    es.onerror = () => {
      refreshQrToken();
      es.close();
      setTimeout(startEventStream, 1500);
    };
  }

  setInterval(() => {
    const rem = Math.max(0, expiresAt - Date.now());
    qrProgress.style.width = (rem / 15000) * 100 + "%";
  }, 100);

  startEventStream();
  setInterval(refreshQrToken, 3000);
  refreshQrToken();
})();
