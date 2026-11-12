from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Job, Notification, SavedSearch


def notify_saved_search_matches(db: Session, job: Job) -> int:
    if not job.is_open:
        return 0
    searches = db.scalars(
        select(SavedSearch).where(SavedSearch.is_active.is_(True))
    ).all()
    searchable_text = f"{job.title} {job.company} {job.description} {job.skills}".casefold()
    notified_candidates: set[int] = set()
    created = 0
    for saved_search in searches:
        if saved_search.candidate_id in notified_candidates:
            continue
        if saved_search.query.strip() and saved_search.query.casefold().strip() not in searchable_text:
            continue
        if saved_search.location.strip() and saved_search.location.casefold().strip() not in job.location.casefold():
            continue
        if saved_search.skill.strip() and saved_search.skill.casefold().strip() not in job.skills.casefold():
            continue
        if saved_search.employment_type and saved_search.employment_type != job.employment_type:
            continue
        if saved_search.experience.strip() and saved_search.experience.casefold().strip() not in job.experience.casefold():
            continue
        message = f"New job match: {job.title} at {job.company}."
        already_notified = db.scalar(
            select(Notification.id).where(
                Notification.user_id == saved_search.candidate_id,
                Notification.message == message,
            )
        )
        if already_notified:
            notified_candidates.add(saved_search.candidate_id)
            continue
        db.add(Notification(user_id=saved_search.candidate_id, message=message))
        notified_candidates.add(saved_search.candidate_id)
        created += 1
    return created
