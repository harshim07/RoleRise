from datetime import datetime, timezone
from typing import Protocol

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Application, ApplicationAction, ApplicationEvent, User
from .applications import submit_application, withdraw_application


class ATSAdapter(Protocol):
    name: str

    def submit(self, db: Session, candidate: User, job_id: int, cover_letter: str, screening_answers: dict[str, str]) -> Application: ...
    def list_applications(self, db: Session, candidate_id: int) -> list[Application]: ...
    def get_application(self, db: Session, candidate_id: int, application_id: int) -> Application: ...
    def get_status_history(self, db: Session, candidate_id: int, application_id: int) -> list[ApplicationEvent]: ...
    def withdraw(self, db: Session, candidate: User, application_id: int) -> None: ...
    def book_interview(self, db: Session, candidate_id: int, action_id: int, scheduled_at: datetime) -> ApplicationAction: ...
    def accept_offer(self, db: Session, candidate_id: int, action_id: int) -> None: ...


class MockATSService:
    name = "mock"

    def submit(self, db: Session, candidate: User, job_id: int, cover_letter: str, screening_answers: dict[str, str]) -> Application:
        return submit_application(db, candidate, job_id, cover_letter, screening_answers)

    def list_applications(self, db: Session, candidate_id: int) -> list[Application]:
        return db.scalars(
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .order_by(Application.created_at.desc())
        ).all()

    def get_application(self, db: Session, candidate_id: int, application_id: int) -> Application:
        application = db.scalar(
            select(Application).where(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            )
        )
        if not application:
            raise HTTPException(404, "Application not found")
        return application

    def get_status_history(self, db: Session, candidate_id: int, application_id: int) -> list[ApplicationEvent]:
        application = self.get_application(db, candidate_id, application_id)
        return db.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application.id)
            .order_by(ApplicationEvent.created_at)
        ).all()

    def withdraw(self, db: Session, candidate: User, application_id: int) -> None:
        withdraw_application(db, candidate, application_id)

    def book_interview(self, db: Session, candidate_id: int, action_id: int, scheduled_at: datetime) -> ApplicationAction:
        action = db.get(ApplicationAction, action_id)
        if not action or action.application.candidate_id != candidate_id or action.action_type != "interview":
            raise HTTPException(404, "Interview action not found")
        if action.status != "action_required":
            raise HTTPException(409, "This interview is no longer available to book")
        if scheduled_at.tzinfo is None or scheduled_at <= datetime.now(timezone.utc):
            raise HTTPException(422, "Choose a future interview time with a timezone")
        action.scheduled_at = scheduled_at
        action.status = "booked"
        if not action.meeting_url:
            action.meeting_url = f"https://meet.example.com/mock-interview/{action.id}"
        action.application.status = "Interview Scheduled"
        db.add(ApplicationEvent(
            application_id=action.application_id,
            actor_id=candidate_id,
            status="Interview Scheduled",
            note="Interview time selected",
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
        return action

    def accept_offer(self, db: Session, candidate_id: int, action_id: int) -> None:
        action = db.get(ApplicationAction, action_id)
        if not action or action.application.candidate_id != candidate_id or action.action_type != "offer":
            raise HTTPException(404, "Offer action not found")
        if action.status != "action_required":
            raise HTTPException(409, "This offer is no longer available")
        action.status = "accepted"
        action.application.status = "Offer Accepted"
        db.add(ApplicationEvent(
            application_id=action.application_id,
            actor_id=candidate_id,
            status="Offer Accepted",
            note="Offer accepted by candidate",
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()


ats_adapter: ATSAdapter = MockATSService()
