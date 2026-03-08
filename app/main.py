from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import engine, Base
from app.routes import register, recognize, attendance_routes, members, auth_routes, import_routes, visitor_routes, meeting_routes, analytics_routes, branch_routes, registration_field_routes

# Create all DB tables
Base.metadata.create_all(bind=engine)

# Import new models so they get created
from app.models.organization import Organization, Admin  # noqa
from app.models.visitor import Visitor  # noqa
from app.models.meeting import Meeting  # noqa
from app.models.branch import Branch, BranchAdmin, JointService, JointServiceBranch  # noqa
from app.models.registration_field import RegistrationField, MemberCustomData  # noqa

# Recreate tables including new ones
Base.metadata.create_all(bind=engine)

# Auto-migrate: add new columns to existing tables if they don't exist (SQLite)
import sqlalchemy
import uuid as _uuid

def _migrate_add_column(conn, inspector, table, column, col_type, default=None):
    """Helper to add a column only if it doesn't exist yet."""
    cols = [c["name"] for c in inspector.get_columns(table)]
    if column not in cols:
        default_clause = f" DEFAULT {default}" if default is not None else ""
        conn.execute(sqlalchemy.text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"))
        conn.commit()

with engine.connect() as conn:
    inspector = sqlalchemy.inspect(engine)

    # --- attendance table ---
    _migrate_add_column(conn, inspector, "attendance", "uid", "VARCHAR")
    _migrate_add_column(conn, inspector, "attendance", "profile_photo", "VARCHAR")
    _migrate_add_column(conn, inspector, "attendance", "member_type", "VARCHAR", "'member'")
    _migrate_add_column(conn, inspector, "attendance", "meeting_id", "INTEGER")
    _migrate_add_column(conn, inspector, "attendance", "meeting_name", "VARCHAR")
    _migrate_add_column(conn, inspector, "attendance", "user_id", "INTEGER")
    _migrate_add_column(conn, inspector, "attendance", "visitor_id", "INTEGER")
    _migrate_add_column(conn, inspector, "attendance", "branch_id", "INTEGER")
    _migrate_add_column(conn, inspector, "attendance", "marked_at_branch_id", "INTEGER")
    _migrate_add_column(conn, inspector, "attendance", "is_late", "BOOLEAN", "0")
    _migrate_add_column(conn, inspector, "attendance", "late_minutes", "INTEGER", "0")
    _migrate_add_column(conn, inspector, "attendance", "is_joint_service", "BOOLEAN", "0")
    _migrate_add_column(conn, inspector, "attendance", "joint_service_id", "INTEGER")

    # --- users table ---
    _migrate_add_column(conn, inspector, "users", "uid", "VARCHAR")
    _migrate_add_column(conn, inspector, "users", "branch_id", "INTEGER")
    _migrate_add_column(conn, inspector, "users", "is_global", "BOOLEAN", "1")

    # --- visitors table ---
    _migrate_add_column(conn, inspector, "visitors", "uid", "VARCHAR")

    # --- meetings table ---
    _migrate_add_column(conn, inspector, "meetings", "uid", "VARCHAR")
    _migrate_add_column(conn, inspector, "meetings", "branch_id", "INTEGER")
    _migrate_add_column(conn, inspector, "meetings", "late_after_minutes", "INTEGER", "15")

    # Backfill UIDs for existing rows that don't have one
    for table in ["users", "attendance", "visitors", "meetings"]:
        try:
            rows = conn.execute(sqlalchemy.text(f"SELECT id FROM {table} WHERE uid IS NULL")).fetchall()
            for row in rows:
                conn.execute(sqlalchemy.text(f"UPDATE {table} SET uid = :uid WHERE id = :id"),
                             {"uid": _uuid.uuid4().hex, "id": row[0]})
            if rows:
                conn.commit()
        except Exception:
            pass

app = FastAPI(
    title="@ttend - Smart Attendance System",
    description="AI-powered face recognition attendance system",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_routes.router, prefix="/api")
app.include_router(register.router, prefix="/api")
app.include_router(recognize.router, prefix="/api")
app.include_router(attendance_routes.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(import_routes.router, prefix="/api")
app.include_router(visitor_routes.router, prefix="/api")
app.include_router(meeting_routes.router, prefix="/api")
app.include_router(analytics_routes.router, prefix="/api")
app.include_router(branch_routes.router, prefix="/api")
app.include_router(registration_field_routes.router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Church Attendance System is running"}


@app.get("/api/sms/status")
def sms_status():
    from app.services.sms_service import is_sms_configured, SMS_PROVIDER
    return {
        "configured": is_sms_configured(),
        "provider": SMS_PROVIDER if is_sms_configured() else None,
    }


@app.get("/")
async def landing():
    return FileResponse("app/static/landing.html")


@app.get("/app")
async def dashboard():
    return FileResponse("app/static/app.html")


@app.get("/admin")
async def admin_console():
    return FileResponse("app/static/admin.html")


# Mount static files last
app.mount("/static", StaticFiles(directory="app/static"), name="static")

