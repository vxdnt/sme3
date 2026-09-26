let logData     = [];
  let expiresAt   = Date.now() + 15000;
  let isPaused    = false;
  let latestToken = null;
  let toastTimer  = null;

  const scanBtn          = document.getElementById('scanBtn');
  const qrModalBackdrop  = document.getElementById('qrModalBackdrop');
  const closeQrModalBtn  = document.getElementById('closeQrModalBtn');
  const modalQrImg       = document.getElementById('modalQrImg');
  const modalQrProgress  = document.getElementById('modalQrProgress');
  const modalQrStatus    = document.getElementById('modalQrStatus');

  const logTableBody     = document.getElementById('logTableBody');
  const tableCount       = document.getElementById('tableCount');
  const searchInput      = document.getElementById('searchInput');
  const noResults        = document.getElementById('noResults');

  const form             = document.getElementById('ticketForm');
  const nameInput        = document.getElementById('nameInput');
  const emailInput       = document.getElementById('emailInput');
  const categorySelect   = document.getElementById('categorySelect');
  const quantitySelect   = document.getElementById('quantitySelect');
  const sendBtn          = document.getElementById('sendBtn');
  const msg              = document.getElementById('msg');
  const ticketPreviewBox = document.getElementById('ticketPreviewBox');
  const ticketLinkInput  = document.getElementById('ticketLinkInput');
  const copyLinkBtn      = document.getElementById('copyLinkBtn');
  const openLinkBtn      = document.getElementById('openLinkBtn');

  const scanAlertToast   = document.getElementById('scanAlertToast');
  const toastTitle       = document.getElementById('toastTitle');
  const toastDetail      = document.getElementById('toastDetail');

  if (scanBtn) {
    scanBtn.addEventListener('click', async function () {
      qrModalBackdrop.classList.add('open');
      await refreshQrToken();
    });
  }

  if (closeQrModalBtn) {
    closeQrModalBtn.addEventListener('click', function () {
      qrModalBackdrop.classList.remove('open');
    });
  }

  if (qrModalBackdrop) {
    qrModalBackdrop.addEventListener('click', function (e) {
      if (e.target === qrModalBackdrop) {
        qrModalBackdrop.classList.remove('open');
      }
    });
  }

  setInterval(function () {
    if (!isPaused) {
      const rem = Math.max(0, expiresAt - Date.now());
      modalQrProgress.style.width = ((rem / 15000) * 100) + '%';
    }
  }, 100);

  function applyQrToken(data) {
    if (!data || data.type !== 'token') return;
    latestToken = data;
    const count = Number(data.activeCount || 1);
    const tokenPreview = document.getElementById('qrTokenPreview');
    const sessionCount = document.getElementById('qrSessionCount');
    if (sessionCount) {
      sessionCount.textContent = String(count || 1);
    }
    if (tokenPreview) {
      const tokenText = data.token ? String(data.token).slice(0, 12) : '—';
      tokenPreview.textContent = 'Current: ' + tokenText;
    }
    if (!isPaused) {
      modalQrImg.src = data.qr || '';
      expiresAt = Number(data.expiresAt || Date.now() + 15000) * 1000;
    }
    const statusText = 'Rotates every 15 seconds • Active QR sessions: ' + String(count || 1);
    if (modalQrStatus) {
      modalQrStatus.textContent = statusText;
    }
  }

  async function refreshQrToken() {
    try {
      const res = await fetch('/api/qr', { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      applyQrToken(data);
    } catch (_) {}
  }

  let es = null;

  function startEventStream() {
    if (es) {
      es.close();
    }

    es = new EventSource('/events');
    es.onopen = function () {
      console.log('[check-in] SSE connected');
    };
    es.onmessage = function (e) {
      const data = JSON.parse(e.data);
      console.log('[check-in] SSE event:', data.type, data);
      if (data.type === 'token') {
        applyQrToken(data);
      } else if (data.type === 'approved' || data.type === 'already_approved') {
        showScanToast(data);
        showVerifiedPopup(data);
        const key = data.ticketId || data.email || 'unknown';
        if (scanCounts && key) {
          scanCounts[key] = data.timesScanned != null
            ? parseInt(data.timesScanned) || (scanCounts[key] || 0) + 1
            : (scanCounts[key] || 0) + 1;
        }
        loadAttendees();
      }
    };
    es.onerror = function (e) {
      console.warn('[check-in] SSE error/disconnected, will reconnect in 1.5s', e);
      refreshQrToken();
      setTimeout(startEventStream, 1500);
    };
  }

  startEventStream();
  setInterval(refreshQrToken, 15000);
  refreshQrToken();

  // Always DD-MM-YYYY HH:MM:SS in IST. Never throws — falls back to the raw value.
  function formatIstTimestamp(value) {
    if (!value) return '—';
    try {
      const raw = String(value).trim();
      const iso = raw.includes('T') ? raw : raw.replace(' ', 'T');
      const hasOffset = /[+-]\d{2}:?\d{2}$|Z$/i.test(iso);
      const date = new Date(hasOffset ? iso : iso + '+05:30');
      if (Number.isNaN(date.getTime())) return raw;
      const parts = new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }).formatToParts(date);
      const get = t => parts.find(p => p.type === t)?.value || '00';
      return `${get('day')}-${get('month')}-${get('year')} ${get('hour')}:${get('minute')}:${get('second')}`;
    } catch (_) {
      return String(value);
    }
  }

  // Short, unmistakable confirmation beep. Fails silently if audio isn't allowed yet.
  function playVerifiedBeep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.28);
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
      osc.onended = function () { ctx.close(); };
    } catch (_) { /* audio not available, ignore */ }
  }

  const verifiedPopupBackdrop = document.getElementById('verifiedPopupBackdrop');
  const verifiedPopup         = document.getElementById('verifiedPopup');
  const verifiedTitle         = document.getElementById('verifiedTitle');
  const verifiedName          = document.getElementById('verifiedName');
  const verifiedEmail         = document.getElementById('verifiedEmail');
  const verifiedTime          = document.getElementById('verifiedTime');
  const verifiedCloseBtn      = document.getElementById('verifiedCloseBtn');
  let verifiedPopupTimer = null;

  function maskTicketId(value) {
    const raw = String(value || '').trim();
    if (!raw) return '—';
    const prefix = raw.split('/')[0] || raw;
    const suffix = raw.includes('/') ? raw.split('/').slice(1).join('/') : '';
    if (suffix) {
      const visible = suffix.slice(0, 4);
      const hidden = '*'.repeat(Math.max(4, Math.min(10, suffix.length - 4)));
      return `${prefix}/${visible}${hidden}`;
    }
    if (raw.length <= 6) return raw.slice(0, 2) + '*'.repeat(Math.max(2, raw.length - 2));
    return raw.slice(0, 4) + '*'.repeat(Math.max(2, raw.length - 4));
  }

  function showVerifiedPopup(data) {
    const isRescan = data.type === 'already_approved';
    verifiedPopup.classList.toggle('rescan', isRescan);
    verifiedTitle.textContent = isRescan ? 'Already Verified (Re-scan)' : 'Verified';
    verifiedName.textContent = data.name || 'Guest';
    verifiedEmail.textContent = maskTicketId(data.ticketId || data.email || '—');
    const timeValue = data.approvedAt || data.newScan || data.approvedAtRaw || '';
    verifiedTime.textContent = formatIstTimestamp(timeValue);
    verifiedPopupBackdrop.classList.add('show');
    playVerifiedBeep();

    if (verifiedPopupTimer) clearTimeout(verifiedPopupTimer);
    verifiedPopupTimer = setTimeout(function () {
      verifiedPopupBackdrop.classList.remove('show');
    }, 4000);
  }

  if (verifiedCloseBtn) {
    verifiedCloseBtn.addEventListener('click', function () {
      if (verifiedPopupTimer) clearTimeout(verifiedPopupTimer);
      verifiedPopupBackdrop.classList.remove('show');
    });
  }
  if (verifiedPopupBackdrop) {
    verifiedPopupBackdrop.addEventListener('click', function (e) {
      if (e.target === verifiedPopupBackdrop) {
        if (verifiedPopupTimer) clearTimeout(verifiedPopupTimer);
        verifiedPopupBackdrop.classList.remove('show');
      }
    });
  }

  function showScanToast(data) {
    const isRescan = data.type === 'already_approved';
    toastTitle.textContent = isRescan ? 'Re-Scan Detected' : 'Scan Verified!';
    const timeValue = data.approvedAt || data.newScan || data.approvedAtRaw || '';
    const secureId = maskTicketId(data.ticketId || data.email || 'Guest');
    toastDetail.textContent = (data.name || 'Guest') + ' · ' + secureId + ' · ' + formatIstTimestamp(timeValue);
    scanAlertToast.classList.add('show');

    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      scanAlertToast.classList.remove('show');
    }, 6000);
  }

  categorySelect.addEventListener('change', function () {
    const cat = categorySelect.value;
    if (cat === 'Couple') {
      quantitySelect.value = '2';
    } else if (cat === 'Group of Four') {
      quantitySelect.value = '4';
    } else {
      quantitySelect.value = '1';
    }
  });

  function renderTable(rows) {
    logTableBody.innerHTML = '';
    tableCount.textContent = rows.length + ' attendee' + (rows.length === 1 ? '' : 's');

    if (rows.length === 0) {
      noResults.style.display = 'block';
      return;
    }
    noResults.style.display = 'none';

    rows.forEach(function (row, i) {
      const tr = document.createElement('tr');
      const scans = parseInt(row.times_scanned) || 0;
      const badgeClass = scans > 0 ? 'active' : 'zero';
      const attendeeName = row.name || '—';
      const attendeeTicketId = maskTicketId(row.ticket_id || '—');
      const attendeeCat = row.category || 'Male Stag';
      const attendeeQty = row.quantity || 1;
      const checkedInAt = row.first_scan ? formatIstTimestamp(row.first_scan) : '—';
      const lastScannedAt = row.last_scan ? formatIstTimestamp(row.last_scan) : '—';
      const tUrl = '/ticket?ticket_id=' + encodeURIComponent(attendeeTicketId);

      tr.innerHTML =
        '<td>' + (i + 1) + '</td>' +
        '<td><strong>' + esc(attendeeName) + '</strong></td>' +
        '<td>' + esc(attendeeTicketId) + '</td>' +
        '<td><span class="badge-cat-table">' + esc(attendeeCat) + '</span></td>' +
        '<td>' + esc(attendeeQty) + '</td>' +
        '<td>' + esc(checkedInAt) + '</td>' +
        '<td>' + esc(lastScannedAt) + '</td>' +
        '<td><span class="badge ' + badgeClass + '">' + scans + '</span></td>';
      logTableBody.appendChild(tr);
    });
  }

  window.resendAttendeeEmail = async function (email, btn) {
    const origText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '…';
    try {
      const res = await fetch('/api/attendees/resend-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email })
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'Failed to send email');
      btn.textContent = 'Sent ✓';
      setTimeout(function () {
        btn.disabled = false;
        btn.textContent = '✉ Resend';
      }, 2500);
      loadAttendees();
    } catch (err) {
      alert('Email send failed: ' + err.message);
      btn.disabled = false;
      btn.textContent = origText;
    }
  };

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  async function loadAttendees() {
    try {
      const res = await fetch('/api/attendees');
      if (!res.ok) return;
      const data = await res.json();
      logData = data.attendees || [];
      filterAndRender();
      checkForNewScans(logData);
    } catch (_) {}
  }

  // ── Polling fallback: guarantees the popup fires even if the SSE push
  // connection is down, dropped, or missed the event for any reason. ──
  let scanCounts = null; // ticketId -> times_scanned, seeded on first load

  function checkForNewScans(attendees) {
    if (scanCounts === null) {
      // First load: just seed the baseline, don't fire popups for history.
      scanCounts = {};
      attendees.forEach(function (a) {
        const key = a.ticket_id || a.email || 'unknown';
        scanCounts[key] = parseInt(a.times_scanned) || 0;
      });
      return;
    }
    attendees.forEach(function (a) {
      const key = a.ticket_id || a.email || 'unknown';
      const count = parseInt(a.times_scanned) || 0;
      const prevCount = scanCounts.hasOwnProperty(key) ? scanCounts[key] : 0;
      if (count > prevCount) {
        console.log('[check-in] Polling detected new scan for', key);
        const payload = {
          type: prevCount > 0 ? 'already_approved' : 'approved',
          name: a.name,
          email: a.email,
          ticketId: a.ticket_id,
          approvedAt: a.last_scan
        };
        showScanToast(payload);
        showVerifiedPopup(payload);
      }
      scanCounts[key] = count;
    });
  }

  setInterval(loadAttendees, 3000);

  function filterAndRender() {
    const query = searchInput.value.trim().toLowerCase();
    const filtered = query
      ? logData.filter(function (row) {
          return (row.email || '').toLowerCase().includes(query) ||
                 (row.ticket_id || '').toLowerCase().includes(query) ||
                 (row.name || '').toLowerCase().includes(query) ||
                 (row.category || '').toLowerCase().includes(query);
        })
      : logData;
    renderTable(filtered);
  }

  if (searchInput) {
    searchInput.addEventListener('input', filterAndRender);
  }
  loadAttendees();

  function isValidEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  if (form) {
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      const name = nameInput.value.trim();
      const email = emailInput.value.trim();
      const category = categorySelect.value;
      const quantity = parseInt(quantitySelect.value) || 1;
      msg.className = 'msg';
      msg.textContent = '';
      if (ticketPreviewBox) ticketPreviewBox.classList.remove('show');

    if (!name) {
      msg.classList.add('error');
      msg.textContent = 'Please enter your full name.';
      return;
    }

    if (!isValidEmail(email)) {
      msg.classList.add('error');
      msg.textContent = 'Please enter a valid email address.';
      return;
    }

if (sendBtn) sendBtn.disabled = true;
      if (sendBtn) sendBtn.textContent = 'Sending…';

      try {
        const res = await fetch('/api/attendees', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email, name: name, quantity: quantity, category: category })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Failed to send ticket');

        if (sendBtn) sendBtn.disabled = false;
        if (sendBtn) sendBtn.textContent = 'Send ticket';
        msg.classList.add('success');
        if (data.emailSent) {
          msg.textContent = 'Ticket generated & emailed to ' + email + ' (' + category + ', Qty: ' + quantity + ')! 🎉';
        } else if (data.emailError) {
          msg.textContent = 'Ticket generated (' + category + ', Qty: ' + quantity + '), but email failed: ' + data.emailError;
        } else {
          msg.textContent = 'Ticket generated for ' + name + ' (' + email + ') — ' + category + ' (Qty: ' + quantity + ')!';
        }

        const rawTicketId = (data.attendee && data.attendee.ticket_id) ? data.attendee.ticket_id : '';
        const ticketUrl = window.location.origin + '/ticket?ticket_id=' + encodeURIComponent(rawTicketId);
        if (ticketLinkInput) ticketLinkInput.value = ticketUrl;
        if (openLinkBtn) openLinkBtn.href = ticketUrl;
        if (ticketPreviewBox) ticketPreviewBox.classList.add('show');

        form.reset();
        if (categorySelect) categorySelect.value = 'Male Stag';
        if (quantitySelect) quantitySelect.value = '1';
        loadAttendees();
      } catch (err) {
        if (sendBtn) sendBtn.disabled = false;
        if (sendBtn) sendBtn.textContent = 'Send ticket';
        msg.classList.add('error');
        msg.textContent = err.message;
      }
    });
  }

  if (copyLinkBtn) {
    copyLinkBtn.addEventListener('click', function () {
      if (ticketLinkInput) ticketLinkInput.select();
      if (ticketLinkInput && navigator.clipboard) {
        navigator.clipboard.writeText(ticketLinkInput.value);
      }
      copyLinkBtn.textContent = 'Copied!';
      setTimeout(function () { copyLinkBtn.textContent = 'Copy'; }, 2000);
    });
  }
