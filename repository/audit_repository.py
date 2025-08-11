import uuid
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from models import SessionLocal, AuditLog


def write_audit_log(
    method: str,
    path: str,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    status_code: Optional[int] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    action: Optional[str] = None,
    entity: Optional[str] = None,
    entity_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    db: Session = SessionLocal()
    try:
        log = AuditLog(
            id=str(uuid.uuid4()),
            method=method,
            path=path,
            user_id=user_id,
            email=email,
            status_code=status_code,
            ip=ip,
            user_agent=user_agent,
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=details or None,
        )
        db.add(log)
        db.commit()
    finally:
        db.close()


def list_audit_logs(
    limit: int = 100,
    offset: int = 0,
    user_email: Optional[str] = None,
    method: Optional[str] = None,
    path_query: Optional[str] = None,
    only_with_action: bool = True,
):
    db: Session = SessionLocal()
    try:
        query = db.query(AuditLog).order_by(AuditLog.timestamp.desc())
        if only_with_action:
            query = query.filter(AuditLog.action.isnot(None))
        if user_email:
            query = query.filter(AuditLog.email == user_email)
        if method:
            query = query.filter(AuditLog.method == method)
        if path_query:
            query = query.filter(AuditLog.path.ilike(f"%{path_query}%"))
        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return total, items
    finally:
        db.close()


