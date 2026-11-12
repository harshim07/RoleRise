from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import CandidateProfile, Job
from .job_alerts import notify_saved_search_matches

def is_expired(expires_at):
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


class JobCatalog(Protocol):
    """Replaceable boundary for mock ATS job data or a future vendor adapter."""

    def search(
        self,
        db: Session,
        *,
        query: str = "",
        location: str = "",
        employment_type: str = "",
        experience: str = "",
        skill: str = "",
        sort: str = "newest",
        profile: CandidateProfile | None = None,
        page: int = 1,
        limit: int = 12,
    ) -> tuple[list[Job], int]: ...

    def get(self, db: Session, job_id: int) -> Job | None: ...

    def recommend(self, db: Session, profile: CandidateProfile | None, limit: int) -> list[Job]: ...

    def match_tags(self, job: Job, profile: CandidateProfile | None) -> list[str]: ...

    def match_score(self, job: Job, profile: CandidateProfile | None) -> int: ...


class LocalPostgresJobCatalog:
    def search(
        self,
        db: Session,
        *,
        query: str = "",
        location: str = "",
        employment_type: str = "",
        experience: str = "",
        skill: str = "",
        sort: str = "newest",
        profile: CandidateProfile | None = None,
        page: int = 1,
        limit: int = 12,
    ) -> tuple[list[Job], int]:
        statement = select(Job).where(
            Job.is_open.is_(True),
            or_(Job.expires_at.is_(None), Job.expires_at > func.now()),
        )
        if query:
            term = f"%{query.strip()}%"
            statement = statement.where(
                or_(
                    Job.title.ilike(term),
                    Job.company.ilike(term),
                    Job.description.ilike(term),
                    Job.skills.ilike(term),
                )
            )
        if location:
            statement = statement.where(Job.location.ilike(f"%{location.strip()}%"))
        if employment_type:
            statement = statement.where(Job.employment_type == employment_type)
        if experience:
            statement = statement.where(Job.experience.ilike(f"%{experience.strip()}%"))
        if skill:
            statement = statement.where(Job.skills.ilike(f"%{skill.strip()}%"))
        if sort == "oldest":
            statement = statement.order_by(Job.created_at.asc())
        elif sort == "company":
            statement = statement.order_by(Job.company.asc())
        elif sort != "recommended" or not profile:
            statement = statement.order_by(Job.created_at.desc())
        total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        if sort == "recommended" and profile:
            ranked = sorted(db.scalars(statement).all(), key=lambda job: (self.match_score(job, profile), job.created_at), reverse=True)
            jobs = ranked[(page - 1) * limit:page * limit]
        else:
            jobs = db.scalars(statement.offset((page - 1) * limit).limit(limit)).all()
        return jobs, total

    def get(self, db: Session, job_id: int) -> Job | None:
        job = db.get(Job, job_id)
        if not job or not job.is_open or is_expired(job.expires_at):
            return None
        return job

    def recommend(self, db: Session, profile: CandidateProfile | None, limit: int) -> list[Job]:
        statement = select(Job).where(
            Job.is_open.is_(True),
            or_(Job.expires_at.is_(None), Job.expires_at > func.now()),
        ).order_by(Job.created_at.desc())
        jobs = db.scalars(statement).all()
        jobs.sort(key=lambda job: (self.match_score(job, profile), job.created_at), reverse=True)
        return jobs[:limit]

    def match_tags(self, job: Job, profile: CandidateProfile | None) -> list[str]:
        if not profile:
            return []
        job_text = f"{job.title} {job.skills}".casefold()
        tags = [skill.name for skill in profile.skill_items if skill.name.casefold() in job_text]
        tags.extend(skill.strip() for skill in profile.skills.split(",") if skill.strip() and skill.strip().casefold() in job_text)
        roles = [role.strip() for role in profile.preferred_roles.split(",") if role.strip()]
        tags.extend(role for role in roles if role.casefold() in job.title.casefold())
        mode = profile.work_mode.casefold()
        location = job.location.casefold()
        if mode and ((mode == "remote" and "remote" in location) or
                     (mode == "hybrid" and "hybrid" in location) or
                     (mode == "onsite" and "remote" not in location and "hybrid" not in location)):
            tags.append(f"{profile.work_mode} work")
        return list(dict.fromkeys(tags))[:5]

    def match_score(self, job: Job, profile: CandidateProfile | None) -> int:
        tags = self.match_tags(job, profile)
        return len(tags)


job_catalog: JobCatalog = LocalPostgresJobCatalog()


def ingest_local_job(db: Session, listing: dict[str, str], source: str = "mock-ats") -> tuple[Job, bool]:
    existing = db.scalar(
        select(Job).where(Job.title == listing["title"], Job.company == listing["company"])
    )
    if existing:
        return existing, False
    job = Job(**listing, source=source)
    db.add(job)
    db.flush()
    notify_saved_search_matches(db, job)
    return job, True
