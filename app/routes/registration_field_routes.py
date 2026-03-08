"""Routes for managing custom registration fields per organization."""

import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.registration_field import RegistrationField, MemberCustomData
from app.models.organization import Admin
from app.auth import get_current_admin

router = APIRouter(prefix="/registration-fields", tags=["Registration Fields"])


class FieldCreate(BaseModel):
    field_name: str
    field_label: str
    field_type: str = "text"  # text, email, phone, date, select, textarea
    is_required: bool = False
    options: Optional[List[str]] = None  # for select type
    field_order: int = 0


class FieldUpdate(BaseModel):
    field_label: Optional[str] = None
    field_type: Optional[str] = None
    is_required: Optional[bool] = None
    options: Optional[List[str]] = None
    field_order: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/")
def get_fields(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get all registration fields for this org."""
    fields = (
        db.query(RegistrationField)
        .filter(RegistrationField.org_id == admin.org_id, RegistrationField.is_active == True)
        .order_by(RegistrationField.field_order, RegistrationField.id)
        .all()
    )
    return {
        "fields": [
            {
                "id": f.id,
                "field_name": f.field_name,
                "field_label": f.field_label,
                "field_type": f.field_type,
                "is_required": f.is_required,
                "options": json.loads(f.options) if f.options else [],
                "field_order": f.field_order,
            }
            for f in fields
        ]
    }


@router.post("/", status_code=201)
def create_field(
    field: FieldCreate,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Create a new custom registration field."""
    if admin.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owners/admins can manage registration fields")

    valid_types = ("text", "email", "phone", "date", "select", "textarea", "number")
    if field.field_type not in valid_types:
        raise HTTPException(400, f"Invalid field_type. Must be one of: {', '.join(valid_types)}")

    new_field = RegistrationField(
        org_id=admin.org_id,
        field_name=field.field_name,
        field_label=field.field_label,
        field_type=field.field_type,
        is_required=field.is_required,
        options=json.dumps(field.options) if field.options else None,
        field_order=field.field_order,
    )
    db.add(new_field)
    db.commit()
    db.refresh(new_field)
    return {"id": new_field.id, "message": f"Field '{field.field_label}' created"}


@router.put("/{field_id}")
def update_field(
    field_id: int,
    update: FieldUpdate,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Update a custom registration field."""
    if admin.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owners/admins can manage registration fields")

    f = db.query(RegistrationField).filter(
        RegistrationField.id == field_id, RegistrationField.org_id == admin.org_id
    ).first()
    if not f:
        raise HTTPException(404, "Field not found")

    data = update.model_dump(exclude_unset=True)
    if "options" in data:
        data["options"] = json.dumps(data["options"]) if data["options"] else None
    for k, v in data.items():
        setattr(f, k, v)

    db.commit()
    return {"message": "Field updated"}


@router.delete("/{field_id}")
def delete_field(
    field_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a custom field (soft delete)."""
    if admin.role not in ("owner", "admin"):
        raise HTTPException(403, "Only owners/admins can manage registration fields")

    f = db.query(RegistrationField).filter(
        RegistrationField.id == field_id, RegistrationField.org_id == admin.org_id
    ).first()
    if not f:
        raise HTTPException(404, "Field not found")

    f.is_active = False
    db.commit()
    return {"message": f"Field '{f.field_label}' removed"}


@router.get("/member/{user_id}")
def get_member_custom_data(
    user_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Get all custom field values for a member."""
    data = (
        db.query(MemberCustomData, RegistrationField)
        .join(RegistrationField, RegistrationField.id == MemberCustomData.field_id)
        .filter(
            MemberCustomData.user_id == user_id,
            MemberCustomData.org_id == admin.org_id,
            RegistrationField.is_active == True,
        )
        .all()
    )
    return {
        "fields": [
            {
                "field_id": d.id,
                "field_name": f.field_name,
                "field_label": f.field_label,
                "value": d.value,
            }
            for d, f in data
        ]
    }
