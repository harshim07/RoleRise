from fastapi import HTTPException
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Application, ApplicationAction, ApplicationEvent, CandidateProfile, Notification, User
from .jobs import job_catalog


def submit_application(db: Session, candidate: User, job_id: int, cover_letter: str, screening_answers: dict[str, str]) -> Application:
    job = job_catalog.get(db, job_id)
    if not job:
        raise HTTPException(400, "This job is no longer accepting applications")
    if db.scalar(
        select(Application).where(
            Application.candidate_id == candidate.id,
            Application.job_id == job_id,
        )
    ):
        raise HTTPException(409, "You have already applied to this job")
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == candidate.id))
    application = Application(
        candidate_id=candidate.id,
        job_id=job_id,
        cover_letter=cover_letter,
        resume_path=profile.resume_path if profile else None,
        resume_filename=profile.resume_filename if profile else None,
        candidate_email=(profile.contact_email or candidate.email) if profile else candidate.email,
        answers_json=json.dumps(screening_answers),
    )
    db.add(application)
    db.flush()
    db.add(ApplicationEvent(application_id=application.id, actor_id=candidate.id, status="Applied"))
    db.add(Notification(user_id=candidate.id, message=f"Your application for {job.title} was submitted."))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "You have already applied to this job")
    db.refresh(application)
    return application


def withdraw_application(db: Session, candidate: User, application_id: int) -> None:
    application = db.get(Application, application_id)
    if not application or application.candidate_id != candidate.id:
        raise HTTPException(404, "Application not found")
    if application.status in {"Selected", "Rejected", "Withdrawn"}:
        raise HTTPException(400, "This application cannot be withdrawn")
    application.status = "Withdrawn"
    pending_actions = db.scalars(
        select(ApplicationAction).where(
            ApplicationAction.application_id == application.id,
            ApplicationAction.status == "action_required",
        )
    ).all()
    for action in pending_actions:
        action.status = "cancelled"
    db.add(ApplicationEvent(application_id=application.id, actor_id=candidate.id, status="Withdrawn"))
    db.add(Notification(user_id=candidate.id, message=f"Your application for {application.job.title} was withdrawn."))
    db.commit()
