# ⛪ Church Attendance System

A face recognition-based attendance tracking system for churches. Members register once with a photo, then attendance is automatically recorded by recognizing faces from camera captures or uploaded group photos.

## Features

- **Face Recognition** — Automatically identify church members from photos
- **Camera Support** — Use your webcam to capture group photos for attendance
- **Photo Upload** — Upload group photos to mark multiple attendees at once
- **Dashboard** — Overview of attendance stats, trends, and top attendees
- **Member Management** — Register/remove church members with face photos
- **Attendance Records** — Search, filter, and manage attendance history

## Tech Stack

- **Backend**: Python + FastAPI + SQLAlchemy + SQLite
- **Face Recognition**: dlib + face_recognition library
- **Frontend**: Next.js 16 + TypeScript + Tailwind CSS

## Project Structure

```
attendance_system/
├── app/                    # Backend (FastAPI)
│   ├── main.py            # App entry point
│   ├── database.py        # DB configuration
│   ├── models/            # SQLAlchemy models
│   │   ├── user.py        # Member model
│   │   └── attendance.py  # Attendance model
│   ├── routes/            # API endpoints
│   │   ├── register.py    # Member registration
│   │   ├── recognize.py   # Face recognition
│   │   ├── attendance_routes.py  # Attendance CRUD
│   │   └── members.py     # Member management
│   └── services/          # Business logic
├── frontend/              # Next.js UI
│   └── src/
│       ├── app/           # Pages (Dashboard, Recognize, Members, Records)
│       ├── components/    # UI components (Sidebar)
│       └── lib/           # API client
├── run.py                 # Backend entry point
└── requirements.txt       # Python dependencies
```

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- cmake (`brew install cmake` on macOS)

### Backend

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install dlib face_recognition

# Start the server
python run.py
```

The API runs at **http://localhost:8000**. API docs at http://localhost:8000/docs.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI runs at **http://localhost:3000**.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/register` | Register a new member |
| POST | `/api/recognize` | Recognize faces & mark attendance |
| GET | `/api/members` | List all members |
| DELETE | `/api/members/{id}` | Remove a member |
| GET | `/api/attendance` | Get attendance records |
| GET | `/api/attendance/today` | Today's attendance |
| GET | `/api/attendance/stats` | Attendance statistics |
| DELETE | `/api/attendance/{id}` | Delete a record |

## Usage

1. **Register Members**: Go to Members page → Register a member with their name and a clear face photo
2. **Take Attendance**: Go to Take Attendance → Use camera or upload a group photo
3. **View Records**: Dashboard shows overview; Records page shows detailed history
