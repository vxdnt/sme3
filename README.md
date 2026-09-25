# SortMyEntries (SME) & Dynamic QR Ticketing System

SortMyEntries is an event listing and ticketing platform designed to help organizers create, manage, and check in event attendees seamlessly. This repository combines the **SortMyEntries corporate web portal** with the **Dynamic QR (DQR) Anti-Fraud Ticketing & Check-In System**.

---

## Features

- **SortMyEntries Corporate Web Portal**:
  - Landing page, Careers portal, Privacy Policy, Terms of Service.
  - SEO-optimized with curated `robots.txt`, dynamic `sitemap.xml`, and web manifest.
- **Dynamic Anti-Fraud QR Check-In**:
  - 15-second rotating cryptographic QR tokens to prevent ticket sharing, duplicate entry, or screenshot fraud.
  - Server-Sent Events (SSE) live updates for instant scanner validation.
- **Organizer Check-In Dashboard**:
  - Real-time attendee check-in log with search, ticket category tags (`Male Stag`, `Female Stag`, `Couple`, `Group of Four`), and quantity tracking.
  - Camera-based attendee verification and dynamic QR display modal.
- **Attendee Ticket Web App**:
  - Clean mobile-first design with interactive event details, flyer graphics, venue maps integration, and device scanner.
- **Email Delivery with Resend**:
  - Automated HTML email dispatch upon ticket generation.
  - One-click resend capability directly from the organizer dashboard.
- **Dual Database Support**:
  - Cloud PostgreSQL via **Neon DB** for production.
  - Automatic zero-config fallback to local **SQLite** (`database.db`) for offline development.

---

## Directory Structure

```text
DQR-main/
├── main.py                  # App entry (uvicorn main:app)
├── requirements.txt
├── render.yaml
├── .env.example
├── README.md
│
├── app/                     # FastAPI application package
│   ├── factory.py           # create_app(), static mounts, routers
│   ├── config.py            # Env vars and project paths
│   ├── db.py                # PostgreSQL / SQLite access
│   ├── qr.py                # Rotating QR tokens
│   ├── email_service.py     # Resend ticket emails
│   └── routes/
│       ├── sme.py           # Marketing site pages
│       ├── pages.py         # Check-in, ticket, generator HTML
│       ├── api.py           # /api/* JSON endpoints
│       └── events.py        # SSE stream and /scan/{token}
│
├── frontend/                # Ticketing HTML views
│   ├── check-in.html
│   ├── ticket.html
│   ├── generator.html
│   ├── 404.html
│   └── expired.html
│
├── static/                  # CSS, JS, and event images
│   ├── css/
│   ├── js/
│   └── images/
│
└── sme/                     # SortMyEntries corporate website
    ├── index.html
    ├── careers/index.html
    ├── privacy/index.html
    └── terms/index.html
```

---

## Getting Started

### 1. Prerequisites
- Python 3.10+ installed
- Git

### 2. Installation
```powershell
# Clone the repository
git clone <your-repo-url>
cd DQR-main

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the `.env.example` template to `.env`:
```powershell
Copy-Item .env.example .env
```

Configure your secrets inside `.env`:
```env
# Neon PostgreSQL connection string (Leave blank to use local SQLite)
DATABASE_URL=postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require

# Resend API Key (https://resend.com/api-keys)
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxx

# Sender email address
FROM_EMAIL=onboarding@resend.dev
```

### 4. Run Locally
```powershell
python main.py
```

The server will start on `http://0.0.0.0:8000`:
- **Website Homepage**: `http://localhost:8000/`
- **Careers Page**: `http://localhost:8000/careers`
- **Organizer Check-in**: `http://localhost:8000/checkin`
- **Dynamic QR Display**: `http://localhost:8000/generator`
- **Attendee Ticket**: `http://localhost:8000/ticket?email=attendee@example.com&name=Attendee`

---

## Route & SEO Guide

| Endpoint | Access | Indexing | Description |
|---|---|---|---|
| `/` | Public | **Indexed** | SortMyEntries company homepage |
| `/careers` | Public | **Indexed** | SortMyEntries careers & open roles |
| `/privacy` | Public | Noindex | Privacy policy |
| `/terms` | Public | Noindex | Terms of service |
| `/robots.txt` | Public | — | Directs web crawlers to allow marketing pages and block app portals |
| `/sitemap.xml` | Public | — | Search engine index list |
| `/checkin` | Organizers | **Noindex** (`X-Robots-Tag: noindex, nofollow`) | Admin dashboard for attendee check-ins |
| `/ticket` | Attendees | **Noindex** (`X-Robots-Tag: noindex, nofollow`) | Attendee ticket view |
| `/generator` | Organizers | **Noindex** (`X-Robots-Tag: noindex, nofollow`) | Full-screen dynamic QR projector screen |
| `/api/attendees` | Backend | **Noindex** | Attendee creation and list API |
| `/api/checkin` | Backend | **Noindex** | Check-in verification API |

---

## Deployment (Render)

The project includes [`render.yaml`](file:///c:/Users/Vedant/Downloads/DQR-main/DQR-main/render.yaml) for 1-click deployment on Render:
1. Connect your GitHub repository to Render.
2. Add environment variables `DATABASE_URL`, `RESEND_API_KEY`, and `FROM_EMAIL` in the Render dashboard.
3. Deploy! The service runs via `uvicorn main:app --host 0.0.0.0 --port $PORT`.

---

## License
Proprietary &copy; SortMyEntries. All rights reserved.
