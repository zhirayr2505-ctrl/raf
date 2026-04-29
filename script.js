/* global Telegram */

// ====== CONFIG ======
// Local time, example: 2026-05-25T18:00:00
const EVENT_ISO_LOCAL = "2026-05-25T18:00:00";
const EVENT_LABEL = "25 մայիսի 18:00";
const EVENT_PLACE = "Դրախտ";
const EVENT_ADDRESS = "Աճառյան 1/1";
const EVENT_QUERY = encodeURIComponent(`${EVENT_PLACE}, ${EVENT_ADDRESS}, Երևան`);
// ====================

function $(id) {
  return document.getElementById(id);
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

function parseLocalIso(isoLocal) {
  const [datePart, timePart] = isoLocal.split("T");
  const [y, mo, d] = datePart.split("-").map(Number);
  const [hh, mm, ss] = timePart.split(":").map(Number);
  return new Date(y, mo - 1, d, hh, mm, ss || 0, 0);
}

function updateCountdown(targetDate) {
  const now = new Date();
  let diff = targetDate.getTime() - now.getTime();
  if (diff < 0) diff = 0;

  const totalSeconds = Math.floor(diff / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  $("d").textContent = String(days);
  $("h").textContent = pad2(hours);
  $("m").textContent = pad2(mins);
  $("s").textContent = pad2(secs);
}

function startConfetti(durationMs = 1800) {
  const canvas = $("confetti");
  const ctx = canvas.getContext("2d");
  const colors = ["#ff7ab6", "#79c2ff", "#ffd36e", "#a7f3d0", "#c4b5fd"];
  const pieces = [];

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener("resize", resize, { passive: true });

  const count = Math.min(180, Math.floor((canvas.width * canvas.height) / 11000));
  for (let i = 0; i < count; i++) {
    pieces.push({
      x: Math.random() * canvas.width,
      y: -20 - Math.random() * canvas.height * 0.3,
      w: 6 + Math.random() * 7,
      h: 8 + Math.random() * 11,
      r: Math.random() * Math.PI,
      vx: -1.6 + Math.random() * 3.2,
      vy: 2.4 + Math.random() * 4.2,
      vr: -0.15 + Math.random() * 0.3,
      color: colors[(Math.random() * colors.length) | 0],
      alpha: 0.9,
    });
  }

  const start = performance.now();
  function frame(t) {
    const elapsed = t - start;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const fade = Math.max(0, 1 - elapsed / durationMs);

    for (const p of pieces) {
      p.x += p.vx;
      p.y += p.vy;
      p.r += p.vr;
      p.vy += 0.015;
      if (p.y > canvas.height + 30) p.y = -30;
      ctx.save();
      ctx.globalAlpha = p.alpha * fade;
      ctx.translate(p.x, p.y);
      ctx.rotate(p.r);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
      ctx.restore();
    }

    if (elapsed < durationMs) requestAnimationFrame(frame);
    else {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      window.removeEventListener("resize", resize);
    }
  }

  requestAnimationFrame(frame);
}

function initTelegramWebApp() {
  const tg = window.Telegram?.WebApp;
  if (!tg) return null;
  tg.ready();
  tg.expand();
  return tg;
}

function getTelegramUserName(tg) {
  const u = tg?.initDataUnsafe?.user;
  if (!u) return null;
  return u.first_name || u.username || null;
}

function openModal() {
  $("reasonModal").setAttribute("aria-hidden", "false");
  $("reasonInput").focus();
}

function closeModal() {
  $("reasonModal").setAttribute("aria-hidden", "true");
  $("reasonInput").value = "";
}

function openStatusModal(title, text) {
  $("statusTitle").textContent = title;
  $("statusText").textContent = text;
  $("statusModal").setAttribute("aria-hidden", "false");
}

function closeStatusModal() {
  $("statusModal").setAttribute("aria-hidden", "true");
}

function scheduleAutoClose(tg, seconds = 10) {
  if (!tg) return;
  setTimeout(() => {
    try {
      tg.close();
    } catch (_) {}
  }, seconds * 1000);
}

function openMapInNativeApp() {
  // Try to open default maps app:
  // - Android: geo:0,0?q=...
  // - iOS: maps://?q=...
  // Telegram WebView may block custom schemes; fallback to https.
  const geoUrl = `geo:0,0?q=${EVENT_QUERY}`;
  const iosUrl = `maps://?q=${EVENT_QUERY}`;
  const httpsUrl = `https://www.google.com/maps/search/?api=1&query=${EVENT_QUERY}`;

  const ua = navigator.userAgent || "";
  const isIOS = /iPad|iPhone|iPod/i.test(ua);

  const primary = isIOS ? iosUrl : geoUrl;
  const fallbackTimer = setTimeout(() => {
    window.open(httpsUrl, "_blank", "noreferrer");
  }, 700);

  // Use location change to trigger app open attempt
  window.location.href = primary;

  // If it succeeds, browser loses focus; timer won't matter.
  // If blocked, timer opens https.
  window.addEventListener(
    "pagehide",
    () => {
      clearTimeout(fallbackTimer);
    },
    { once: true }
  );
}

function main() {
  // Gate (sound preference)
  const soundToggle = $("soundToggle");
  const savedSound = localStorage.getItem("soundEnabled");
  soundToggle.checked = savedSound === null ? true : savedSound === "1";

  const tg = initTelegramWebApp();
  // Remove blue bottom button ASAP (Telegram may keep it from previous sessions)
  try {
    tg?.MainButton?.hide?.();
  } catch (_) {}

  $("continueBtn").addEventListener("click", async () => {
    localStorage.setItem("soundEnabled", soundToggle.checked ? "1" : "0");
    $("gate").setAttribute("aria-hidden", "true");
    try {
      tg?.MainButton?.hide?.(); // remove blue bottom button
    } catch (_) {}

    if (soundToggle.checked) {
      try {
        await $("voice").play();
        $("audioBtn").textContent = "Անջատել ձայնը";
      } catch (_) {
        // ignore; user can tap audio button later
      }
    }
  });

  // Event info block
  $("eventWhen").textContent = EVENT_LABEL;
  $("eventWhere").textContent = EVENT_PLACE;
  $("eventAddress").textContent = EVENT_ADDRESS;

  const embedUrl = `https://www.google.com/maps?q=${EVENT_QUERY}&output=embed`;
  $("mapFrame").src = embedUrl;
  $("openMapBtn").addEventListener("click", openMapInNativeApp);

  const target = parseLocalIso(EVENT_ISO_LOCAL);
  updateCountdown(target);
  setInterval(() => updateCountdown(target), 1000);

  startConfetti(1600);

  const name = getTelegramUserName(tg);
  if (name) $("helloTitle").textContent = `Բարև, ${name}։ Ես Ռաֆն եմ`;

  const voice = $("voice");
  $("audioBtn").addEventListener("click", async () => {
    try {
      if (voice.paused) {
        await voice.play();
        $("audioBtn").textContent = "Անջատել ձայնը";
      } else {
        voice.pause();
        $("audioBtn").textContent = "Ձայնը միացնե՞մ";
      }
    } catch (e) {
      $("audioHint").textContent =
        "Չստացվեց միացնել ձայնը։ Ստուգիր, որ ունես raf-voice.mp3 (ֆայլը հենց կայքի արմատում)";
      console.error(e);
    }
  });

  function setBusy(busy, text) {
    for (const id of ["yesBtn", "noBtn", "laterBtn"]) $(id).disabled = busy;
    $("hint").textContent = text;
  }

  function sendRsvp(status, reason = null) {
    const payload = {
      type: "rsvp",
      status,
      reason,
      event: { isoLocal: EVENT_ISO_LOCAL, label: EVENT_LABEL },
      ts: new Date().toISOString(),
    };

    if (tg) {
      setBusy(true, "Ուղարկում եմ բոտին…");
      try {
        tg.sendData(JSON.stringify(payload));
      } catch (e) {
        setBusy(false, "Չստացվեց ուղարկել։ Փորձիր կրկին։");
        console.error(e);
        return;
      }

      if (status === "yes") {
        startConfetti(2400);
        setBusy(true, "Շնորհակալ եմ, որ գալիս ես։ Կհանդիպենք շուտով։");
        openStatusModal("Հրաշալի է!", "Շնորհակալ եմ, որ գալիս ես։ Կհանդիպենք Դրախտ-ում։");
        scheduleAutoClose(tg, 10);
      } else if (status === "no") {
        setBusy(true, "Շնորհակալ եմ։ Կփոխանցեմ, որ այս անգամ չես կարող։");
        scheduleAutoClose(tg, 10);
      } else {
        setBusy(true, "Լավ, կհասկացնենք։ Ես էլ քեզ նորից կգրեմ։");
        openStatusModal("Լավ", "Ես կսպասեմ քո պատասխանին։ Հուսով եմ՝ դրական կլինի։");
        scheduleAutoClose(tg, 10);
      }
      return;
    }

    setBusy(false, "Բացիր սա Telegram-ի ներսում, որ պատասխանը գնա բոտին։");
    console.log("RSVP payload:", payload);
  }

  $("yesBtn").addEventListener("click", () => sendRsvp("yes"));
  $("laterBtn").addEventListener("click", () => sendRsvp("later"));
  $("noBtn").addEventListener("click", openModal);

  $("cancelNoBtn").addEventListener("click", closeModal);
  $("reasonModal").addEventListener("click", (e) => {
    if (e.target === $("reasonModal")) closeModal();
  });
  $("sendNoBtn").addEventListener("click", () => {
    const reason = $("reasonInput").value.trim();
    closeModal();
    sendRsvp("no", reason || null);
    openStatusModal("Հասկացա…", "Շնորհակալ եմ։ Պատճառն էլ փոխանցեցի։");
  });

  // Ensure MainButton stays hidden
  try {
    tg?.MainButton?.hide?.();
  } catch (_) {}

  $("statusOkBtn").addEventListener("click", closeStatusModal);
  $("backToChatBtn").addEventListener("click", () => {
    try {
      window.Telegram?.WebApp?.close();
    } catch (_) {}
  });
  $("statusModal").addEventListener("click", (e) => {
    if (e.target === $("statusModal")) closeStatusModal();
  });

  $("closeBtn").addEventListener("click", () => {
    const tg = window.Telegram?.WebApp;
    if (tg) tg.close();
    else window.close();
  });
}

main();
