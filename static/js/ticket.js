// ── 1. Read URL Parameters & Cache ──
    const params = new URLSearchParams(window.location.search);
    let userEmail = (params.get('email') || '').trim();
    let userName = (params.get('name') || '').trim();
    let userQty = (params.get('qty') || '').trim();
    let userCat = (params.get('cat') || params.get('category') || '').trim();
    const urlToken = (params.get('token') || '').trim();

    if (userEmail) {
      localStorage.setItem('ticket_email', userEmail);
      if (userName) localStorage.setItem('ticket_name', userName);
      if (userQty) localStorage.setItem('ticket_qty', userQty);
      if (userCat) localStorage.setItem('ticket_category', userCat);
    } else {
      userEmail = localStorage.getItem('ticket_email') || 'attendee@example.com';
      userName = localStorage.getItem('ticket_name') || 'Attendee Name';
      userQty = localStorage.getItem('ticket_qty') || '1';
      userCat = localStorage.getItem('ticket_category') || 'Male Stag';
    }

    const ticket = {
      attendeeName: userName || 'Attendee Name',
      email: userEmail || 'attendee@example.com',
      quantity: userQty || '1',
      category: userCat || 'Male Stag',
      eventName: 'Big Fat Indian Scam Sangeet',
      eventDescription: 'Tap Open Scanner below to check in at the entrance.',
      date: '27 Sep 2026',
      time: '6:00 PM',
      location: 'Eumsik Garden Restaurant'
    };

    document.getElementById('eventName').textContent = ticket.eventName;
    document.getElementById('eventDesc').textContent = ticket.eventDescription;
    document.getElementById('eventDate').textContent = ticket.date;
    document.getElementById('eventTime').textContent = ticket.time;
    document.getElementById('eventLocation').innerHTML = '<a href="https://maps.app.goo.gl/PEXN9a42ppobr7sv7" target="_blank" style="color:inherit;text-decoration:underline;text-underline-offset:2px;display:inline-flex;align-items:center;gap:4px;"><span>' + ticket.location + '</span><i class="fa-solid fa-arrow-up-right-from-square" style="font-size:0.75em;opacity:0.85;"></i></a>';
    document.getElementById('attendeeName').textContent = ticket.attendeeName;
    document.getElementById('attendeeEmail').textContent = ticket.email;
    document.getElementById('ticketQty').textContent = ticket.quantity;
    document.getElementById('ticketCategory').textContent = ticket.category;

    const lastCheckedLine = document.getElementById('lastCheckedLine');
    const lastCheckedTime = document.getElementById('lastCheckedTime');

    // Always DD-MM-YYYY HH:MM:SS in IST. Never throws — falls back to the raw value,
    // so a formatting hiccup can never suppress the "verified" confirmation below.
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

    function showLastCheckedIn(timeStr) {
      if (!timeStr) return;
      const formatted = formatIstTimestamp(timeStr);
      lastCheckedLine.innerHTML = '✓ Ticket verified at <strong>' + formatted + '</strong>';
      lastCheckedLine.classList.add('show');
      const badge = document.getElementById('ticketCategory');
      badge.textContent = ticket.category + ' · ✓ Checked In';
      badge.classList.add('checked');
    }

    // ── 2. Check initial attendee status from backend ──
    async function fetchAttendeeStatus() {
      if (!ticket.email || ticket.email === 'attendee@example.com') return;
      try {
        const res = await fetch('/api/attendee?email=' + encodeURIComponent(ticket.email));
        if (!res.ok) return;
        const data = await res.json();
        if (data.ok && data.attendee) {
          if (data.attendee.name) {
            document.getElementById('attendeeName').textContent = data.attendee.name;
          }
          if (data.attendee.quantity) {
            document.getElementById('ticketQty').textContent = data.attendee.quantity;
          }
          if (data.attendee.category) {
            ticket.category = data.attendee.category;
            document.getElementById('ticketCategory').textContent = data.attendee.category;
          }
          const scans = parseInt(data.attendee.times_scanned) || 0;
          if (scans > 0) {
            showLastCheckedIn(data.attendee.last_scan || data.attendee.first_scan);
          }
        }
      } catch (_) { }
    }
    fetchAttendeeStatus();

    // ── 3. Handle direct /scan/<token> redirect ──
    if (urlToken && ticket.email && ticket.email !== 'attendee@example.com') {
      processCheckIn(urlToken);
    }

    // ── 4. Camera Scanner & jsQR ──
    const openScannerBtn = document.getElementById('openScannerBtn');
    const closeScannerBtn = document.getElementById('closeScannerBtn');
    const scannerModal = document.getElementById('scannerModal');
    const scannerVideo = document.getElementById('scannerVideo');
    const scannerCanvas = document.getElementById('scannerCanvas');
    const scannerStatus = document.getElementById('scannerStatus');
    const scanResult = document.getElementById('scanResult');

    let stream = null;
    let scanning = false;
    let rafId = null;
    let closeTimeout = null;

    async function openScanner() {
      scanResult.style.display = 'none';
      scannerStatus.textContent = 'Point the camera at the organizer\'s QR code…';
      scannerModal.classList.add('open');

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        scannerStatus.textContent = 'Camera access is not supported in this browser. Please use Chrome, Edge, or Safari on a secure page (HTTPS or localhost) and allow camera permission.';
        return;
      }

      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' } }
        });
        scannerVideo.srcObject = stream;
        await scannerVideo.play();
        scanning = true;
        requestAnimationFrame(tick);
      } catch (err) {
        const message = err && err.message ? err.message : 'permission denied.';
        scannerStatus.textContent = 'Camera unavailable: ' + message;
      }
    }

    function tick() {
      if (!scanning) return;
      if (!window.jsQR) {
        scannerStatus.textContent = 'QR scanner library failed to load. Please refresh the page and try again.';
        scanning = false;
        stopStream();
        return;
      }
      const ctx = scannerCanvas.getContext('2d');
      if (scannerVideo.readyState === scannerVideo.HAVE_ENOUGH_DATA) {
        scannerCanvas.width = scannerVideo.videoWidth;
        scannerCanvas.height = scannerVideo.videoHeight;
        ctx.drawImage(scannerVideo, 0, 0, scannerCanvas.width, scannerCanvas.height);
        const imageData = ctx.getImageData(0, 0, scannerCanvas.width, scannerCanvas.height);
        const code = window.jsQR(imageData.data, imageData.width, imageData.height);
        if (code && code.data) {
          onScanSuccess(code.data);
          return;
        }
      }
      rafId = requestAnimationFrame(tick);
    }

    async function onScanSuccess(rawValue) {
      scanning = false;
      stopStream();

      // Extract token from scanned URL or raw string
      let token = rawValue;
      try {
        const url = new URL(rawValue);
        const parts = url.pathname.split('/').filter(Boolean);
        if (parts.length >= 2 && parts[0] === 'scan') {
          token = parts[1];
        }
      } catch (_) { }

      await processCheckIn(token);
    }

    async function processCheckIn(token) {
      scannerStatus.textContent = 'Verifying check-in…';

      try {
        const res = await fetch('/api/checkin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: token, email: ticket.email })
        });
        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.detail || data.error || 'Check-in failed');
        }

        // The server confirmed the check-in — show "verified" immediately.
        // Everything below is cosmetic (timestamp formatting, badge text) and
        // is isolated so it can never fall back to an "Error" state once we're here.
        scannerStatus.textContent = 'Ticket verified';
        scanResult.style.display = 'block';

        const rawTime = data.scannedAt || data.scannedAtRaw;
        let displayTime = rawTime || '';
        try {
          displayTime = formatIstTimestamp(rawTime);
        } catch (_) { /* keep raw value */ }
        scanResult.textContent = 'Ticket verified at ' + displayTime;

        try {
          showLastCheckedIn(rawTime);
          lastCheckedLine.classList.add('show');
        } catch (_) { /* non-critical */ }

        // Close modal and return to the ticket page after 2 seconds
        if (closeTimeout) clearTimeout(closeTimeout);
        closeTimeout = setTimeout(function () {
          closeScanner();
        }, 2000);

      } catch (err) {
        scannerStatus.textContent = 'Error: ' + err.message;
        scanResult.style.display = 'none';
      }
    }

    function stopStream() {
      if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
      if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
    }

    function closeScanner() {
      scanning = false;
      stopStream();
      if (closeTimeout) { clearTimeout(closeTimeout); closeTimeout = null; }
      scannerModal.classList.remove('open');
    }

    openScannerBtn.addEventListener('click', openScanner);
    closeScannerBtn.addEventListener('click', closeScanner);
