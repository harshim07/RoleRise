import os
import secrets
import hashlib
import io
import json
import smtplib
import zipfile
import xml.etree.ElementTree as ET
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated
import jwt
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .models import Application, ApplicationAction, CandidateProfile, CandidateSkill, Education, Experience, Job, Notification, PasswordResetToken, SavedJob, SavedSearch, User
from .schemas import ApplyIn, EducationIn, ExperienceIn, InterviewBookingIn, LoginIn, PasswordResetConfirm, PasswordResetRequest, ProfileIn, RegisterIn, SavedSearchIn
from .services.ats import ats_adapter
from .services.resumes import parse_resume_text
from .services.jobs import is_expired, job_catalog
from .security import create_access_token, decode_access_token, password_hash

app = FastAPI(title="RoleRise API", version="1.0.0")
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]
def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: DB):
    if not credentials:
        raise HTTPException(401, "Authentication required")
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Invalid or expired token")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Account is unavailable")
    if claims.get("ver") != user.token_version:
        raise HTTPException(401, "Session is no longer valid")
    return user

CurrentUser = Annotated[User, Depends(current_user)]

def optional_current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], db: DB):
    return current_user(credentials, db) if credentials else None

OptionalUser = Annotated[User | None, Depends(optional_current_user)]

DEFAULT_SCREENING_QUESTIONS = [
    {"id": "notice_period", "label": "What is your notice period?", "type": "select", "required": True,
     "options": ["Immediate", "2 weeks", "1 month", "2+ months"]},
    {"id": "work_authorization", "label": "What is your work authorization status?", "type": "select", "required": True,
     "options": ["Authorized to work", "Will require sponsorship", "Prefer not to say"]},
]

def public_job(job: Job):
    screening_questions = json.loads(job.screening_questions or "[]") or DEFAULT_SCREENING_QUESTIONS
    return {"id": job.id, "title": job.title, "company": job.company, "location": job.location,
            "employment_type": job.employment_type, "experience": job.experience, "salary_range": job.salary_range,
            "skills": job.skills, "description": job.description, "is_open": job.is_open,
            "created_at": job.created_at, "expires_at": job.expires_at,
            "screening_questions": screening_questions}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterIn, db: DB):
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, password_hash=password_hash.hash(payload.password))
    user.profile = CandidateProfile(full_name=payload.full_name)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists")
    db.refresh(user)
    return {"access_token": create_access_token(user.id, user.token_version), "token_type": "bearer", "user": {"id": user.id, "email": user.email}}

@app.post("/api/auth/login")
def login(payload: LoginIn, db: DB):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not password_hash.verify(payload.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    return {"access_token": create_access_token(user.id, user.token_version), "token_type": "bearer", "user": {"id": user.id, "email": user.email}}

@app.get("/api/auth/me")
def me(user: CurrentUser):
    return {"id": user.id, "email": user.email}

@app.post("/api/auth/logout")
def logout(user: CurrentUser, db: DB):
    user.token_version += 1
    db.commit()
    return {"message": "Signed out. Remove the access token from the client."}

@app.post("/api/auth/forgot-password")
def forgot_password(payload: PasswordResetRequest, db: DB):
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_from = os.getenv("SMTP_FROM", os.getenv("SMTP_USERNAME", ""))
    if not smtp_host or not smtp_from:
        raise HTTPException(503, "Password reset email is not configured")
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError as exc:
        raise HTTPException(503, "SMTP_PORT must be a valid port number") from exc
    user = db.scalar(select(User).where(User.email == payload.email.lower(), User.is_active.is_(True)))
    if user:
        token = secrets.token_urlsafe(32)
        token_row = PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.add(token_row)
        db.commit()
        message = EmailMessage()
        message["Subject"] = "Reset your RoleRise password"
        message["From"] = smtp_from
        message["To"] = user.email
        reset_url = f"{os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')}/reset?token={token}"
        message.set_content(f"Use this link within 30 minutes to reset your password:\n\n{reset_url}\n\nIf you did not request this, ignore this email.")
        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
                smtp.starttls()
                username = os.getenv("SMTP_USERNAME", "")
                if username:
                    smtp.login(username, os.getenv("SMTP_PASSWORD", ""))
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            db.delete(token_row)
            db.commit()
            raise HTTPException(503, "Password reset email could not be sent") from exc
    return {"message": "If that account exists, password reset instructions will be sent."}

@app.post("/api/auth/reset-password")
def reset_password(payload: PasswordResetConfirm, db: DB):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    token_row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    if not token_row or token_row.used_at or is_expired(token_row.expires_at):
        raise HTTPException(400, "Reset link is invalid or expired")
    user = db.get(User, token_row.user_id)
    if not user or not user.is_active:
        raise HTTPException(400, "Reset link is invalid or expired")
    user.password_hash = password_hash.hash(payload.password)
    user.token_version += 1
    token_row.used_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Password reset successfully. You can now sign in."}

@app.get("/api/profile")
def get_profile(user: CurrentUser, db: DB):
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        raise HTTPException(404, "Profile not found")
    completion = sum((
        bool(profile.full_name) * 8,
        bool(profile.phone) * 7,
        bool(profile.contact_email or user.email) * 7,
        bool(profile.location) * 4,
        bool(profile.summary) * 8,
        bool(profile.skills) * 8,
        bool(profile.linkedin_url or profile.github_url or profile.portfolio_url) * 4,
        bool(profile.experience) * 14,
        bool(profile.education) * 10,
        bool(profile.resume_path) * 10,
        bool(profile.preferred_roles) * 8,
        bool(profile.work_mode) * 5,
        bool(profile.expected_salary) * 4,
        bool(profile.notice_period) * 3,
    ))
    return {**{k: getattr(profile, k) for k in ("full_name", "phone", "location", "summary", "skills", "linkedin_url", "github_url", "portfolio_url", "resume_path")},
            **{k: getattr(profile, k) for k in ("contact_email", "resume_filename", "resume_content_type", "resume_uploaded_at", "preferred_roles", "work_mode", "expected_salary", "notice_period")},
            "resume_text": profile.resume_text[:12000],
            "education": [{"id": x.id, "institution": x.institution, "degree": x.degree, "field_of_study": x.field_of_study, "start_year": x.start_year, "end_year": x.end_year} for x in profile.education],
            "experience": [{"id": x.id, "company": x.company, "title": x.title, "location": x.location, "start_date": x.start_date, "end_date": x.end_date, "description": x.description} for x in profile.experience],
            "skill_items": [{"id": x.id, "name": x.name} for x in profile.skill_items],
            "email": user.email, "completion": completion}

def validate_education_dates(payload: EducationIn):
    if payload.start_year and payload.end_year and payload.end_year < payload.start_year:
        raise HTTPException(422, "Education end year must be the same as or later than the start year")

def validate_experience_dates(payload: ExperienceIn):
    def parse_date(value: str):
        if not value:
            return None
        for date_format in ("%Y-%m-%d", "%Y-%m"):
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                continue
        raise HTTPException(422, "Experience dates must use YYYY-MM or YYYY-MM-DD format")

    start = parse_date(payload.start_date)
    end = parse_date(payload.end_date)
    if start and end and end < start:
        raise HTTPException(422, "Experience end date must be the same as or later than the start date")

@app.post("/api/profile/education", status_code=201)
def add_education(payload: EducationIn, user: CurrentUser, db: DB):
    validate_education_dates(payload)
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    item = Education(profile_id=profile.id, **payload.model_dump())
    db.add(item)
    db.commit()
    return {"id": item.id}

@app.put("/api/profile/education/{education_id}")
def update_education(education_id: int, payload: EducationIn, user: CurrentUser, db: DB):
    validate_education_dates(payload)
    item = db.get(Education, education_id)
    if not item or item.profile.user_id != user.id:
        raise HTTPException(404, "Education record not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return {"message": "Education record updated"}

@app.delete("/api/profile/education/{education_id}")
def remove_education(education_id: int, user: CurrentUser, db: DB):
    item = db.get(Education, education_id)
    if not item or item.profile.user_id != user.id:
        raise HTTPException(404, "Education record not found")
    db.delete(item)
    db.commit()
    return {"message": "Education record removed"}

@app.post("/api/profile/experience", status_code=201)
def add_experience(payload: ExperienceIn, user: CurrentUser, db: DB):
    validate_experience_dates(payload)
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
        db.flush()
    item = Experience(profile_id=profile.id, **payload.model_dump())
    db.add(item)
    db.commit()
    return {"id": item.id}

@app.put("/api/profile/experience/{experience_id}")
def update_experience(experience_id: int, payload: ExperienceIn, user: CurrentUser, db: DB):
    validate_experience_dates(payload)
    item = db.get(Experience, experience_id)
    if not item or item.profile.user_id != user.id:
        raise HTTPException(404, "Experience record not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return {"message": "Experience record updated"}

@app.delete("/api/profile/experience/{experience_id}")
def remove_experience(experience_id: int, user: CurrentUser, db: DB):
    item = db.get(Experience, experience_id)
    if not item or item.profile.user_id != user.id:
        raise HTTPException(404, "Experience record not found")
    db.delete(item)
    db.commit()
    return {"message": "Experience record removed"}

@app.put("/api/profile")
def update_profile(payload: ProfileIn, user: CurrentUser, db: DB):
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
    for key, value in payload.model_dump().items():
        setattr(profile, key, "" if key == "contact_email" and value is None else value)
    unique_skills = {skill.strip().casefold(): skill.strip() for skill in payload.skills.split(",") if skill.strip()}
    existing_skills = {}
    removed_skills = []
    for skill_item in profile.skill_items:
        key = skill_item.name.strip().casefold()
        if key in unique_skills and key not in existing_skills:
            existing_skills[key] = skill_item
        else:
            removed_skills.append(skill_item)
    for skill_item in removed_skills:
        profile.skill_items.remove(skill_item)
    if removed_skills:
        db.flush()
    for key, name in unique_skills.items():
        if key in existing_skills:
            existing_skills[key].name = name
        else:
            profile.skill_items.append(CandidateSkill(name=name))
    db.commit()
    return {"message": "Profile saved"}

@app.post("/api/profile/resume")
async def upload_resume(user: CurrentUser, db: DB, file: UploadFile = File(...)):
    if not file.filename or Path(file.filename.replace("\\", "/")).suffix.lower() not in {".pdf", ".docx"}:
        raise HTTPException(400, "Resume must be a PDF or DOCX file")
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "Resume exceeds the 5 MB limit")
    extension = Path(file.filename.replace("\\", "/")).suffix.lower()
    content_type = "application/pdf" if extension == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(400, "PDF file is invalid")
        try:
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)[:50000]
        except (PdfReadError, FileNotDecryptedError, ValueError) as exc:
            raise HTTPException(400, "PDF could not be read; upload an unprotected PDF") from exc
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                document = ET.fromstring(archive.read("word/document.xml"))
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
            raise HTTPException(400, "DOCX file is invalid") from exc
        text = "\n".join(
            "".join(node.text or "" for node in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
            for paragraph in document.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p")
        )[:50000]
    parsed = parse_resume_text(text)
    filename = file.filename.replace("\\", "/").rsplit("/", 1)[-1][:255]
    directory = Path(os.getenv("UPLOAD_DIR", "uploads"))
    directory.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{user.id}-{secrets.token_hex(16)}{extension}"
    (directory / stored_filename).write_bytes(content)
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile:
        profile = CandidateProfile(user_id=user.id)
        db.add(profile)
    previous_path = profile.resume_path
    profile.resume_path = stored_filename
    profile.resume_filename = filename
    profile.resume_content_type = content_type
    profile.resume_uploaded_at = datetime.now(timezone.utc)
    profile.resume_text = text
    for field in ("full_name", "phone", "location", "summary", "skills"):
        if not getattr(profile, field) and parsed[field]:
            setattr(profile, field, parsed[field])
    if not profile.contact_email and parsed["email"]:
        profile.contact_email = parsed["email"]
    if parsed["skills"]:
        existing_skills = {skill.name.casefold() for skill in profile.skill_items}
        profile.skill_items.extend(
            CandidateSkill(name=skill.strip())
            for skill in parsed["skills"].split(",")
            if skill.strip() and skill.strip().casefold() not in existing_skills
        )
    db.commit()
    if previous_path and not db.scalar(select(Application.id).where(Application.resume_path == previous_path)):
        previous_file = directory / Path(previous_path).name
        if previous_file.is_file():
            previous_file.unlink()
    return {"message": "Resume uploaded and parsed", "parsed": parsed}

@app.get("/api/profile/resume")
def get_resume(user: CurrentUser, db: DB):
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile or not profile.resume_path:
        raise HTTPException(404, "No resume uploaded")
    path = Path(os.getenv("UPLOAD_DIR", "uploads")) / Path(profile.resume_path).name
    if not path.is_file():
        raise HTTPException(404, "Resume file is unavailable")
    return FileResponse(path, media_type=profile.resume_content_type or "application/octet-stream",
                        filename=profile.resume_filename or path.name, content_disposition_type="inline")

@app.delete("/api/profile/resume")
def remove_resume(user: CurrentUser, db: DB):
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if not profile or not profile.resume_path:
        raise HTTPException(404, "No resume uploaded")
    stored_path = profile.resume_path
    profile.resume_path = None
    profile.resume_filename = None
    profile.resume_content_type = None
    profile.resume_uploaded_at = None
    profile.resume_text = ""
    db.commit()
    if not db.scalar(select(Application.id).where(Application.resume_path == stored_path)):
        path = Path(os.getenv("UPLOAD_DIR", "uploads")) / Path(stored_path).name
        if path.is_file():
            path.unlink()
    return {"message": "Resume removed"}

@app.get("/api/jobs")
def list_jobs(db: DB, user: OptionalUser, q: str = "", location: str = "", employment_type: str = "", experience: str = "", skill: str = "",
              sort: str = "newest", page: int = Query(1, ge=1), limit: int = Query(12, ge=1, le=50)):
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id)) if user else None
    jobs, total = job_catalog.search(db, query=q, location=location, employment_type=employment_type,
                                     experience=experience, skill=skill, sort=sort, profile=profile, page=page, limit=limit)
    return {"items": [public_job(job) for job in jobs], "total": total, "page": page, "pages": (total + limit - 1) // limit}

@app.get("/api/jobs/{job_id}")
def job_detail(job_id: int, db: DB):
    job = job_catalog.get(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return public_job(job)

@app.get("/api/recommendations")
def recommended_jobs(user: CurrentUser, db: DB, limit: int = Query(6, ge=1, le=20)):
    profile = db.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    return [{**public_job(job), "match_tags": job_catalog.match_tags(job, profile),
             "match_score": job_catalog.match_score(job, profile)} for job in job_catalog.recommend(db, profile, limit)]

@app.post("/api/jobs/{job_id}/save")
def save_job(job_id: int, user: CurrentUser, db: DB):
    job = job_catalog.get(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not db.scalar(select(SavedJob).where(SavedJob.candidate_id == user.id, SavedJob.job_id == job_id)):
        db.add(SavedJob(candidate_id=user.id, job_id=job_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return {"saved": True}

@app.delete("/api/jobs/{job_id}/save")
def unsave_job(job_id: int, user: CurrentUser, db: DB):
    saved = db.scalar(select(SavedJob).where(SavedJob.candidate_id == user.id, SavedJob.job_id == job_id))
    if saved:
        db.delete(saved)
        db.commit()
    return {"saved": False}

@app.get("/api/saved-jobs")
def saved_jobs(user: CurrentUser, db: DB):
    saved = db.scalars(select(SavedJob).where(SavedJob.candidate_id == user.id)).all()
    return [public_job(item.job) for item in saved if item.job.is_open and not is_expired(item.job.expires_at)]

@app.get("/api/saved-searches")
def saved_searches(user: CurrentUser, db: DB):
    items = db.scalars(select(SavedSearch).where(SavedSearch.candidate_id == user.id).order_by(SavedSearch.created_at.desc())).all()
    return [{"id": item.id, "query": item.query, "location": item.location, "skill": item.skill,
             "employment_type": item.employment_type, "experience": item.experience, "is_active": item.is_active}
            for item in items]

@app.post("/api/saved-searches", status_code=201)
def create_saved_search(payload: SavedSearchIn, user: CurrentUser, db: DB):
    existing = db.scalar(select(SavedSearch).where(
        SavedSearch.candidate_id == user.id,
        SavedSearch.query == payload.query,
        SavedSearch.location == payload.location,
        SavedSearch.skill == payload.skill,
        SavedSearch.employment_type == payload.employment_type,
        SavedSearch.experience == payload.experience,
    ))
    if existing:
        existing.is_active = True
        db.commit()
        return {"id": existing.id, "is_active": True}
    item = SavedSearch(candidate_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    return {"id": item.id, "is_active": True}

@app.delete("/api/saved-searches/{search_id}")
def delete_saved_search(search_id: int, user: CurrentUser, db: DB):
    item = db.get(SavedSearch, search_id)
    if not item or item.candidate_id != user.id:
        raise HTTPException(404, "Saved search not found")
    db.delete(item)
    db.commit()
    return {"message": "Job alert removed"}

@app.post("/api/jobs/{job_id}/apply", status_code=201)
def apply(job_id: int, payload: ApplyIn, user: CurrentUser, db: DB):
    job = job_catalog.get(db, job_id)
    if not job:
        raise HTTPException(400, "This job is no longer accepting applications")
    questions = json.loads(job.screening_questions or "[]") or DEFAULT_SCREENING_QUESTIONS
    question_ids = {question["id"] for question in questions}
    expected_answers = {question["id"] for question in questions if question.get("required", True)}
    if expected_answers - payload.screening_answers.keys() or payload.screening_answers.keys() - question_ids:
        raise HTTPException(422, "Please answer all required screening questions")
    if len(payload.screening_answers) > 20 or any(len(answer) > 1000 for answer in payload.screening_answers.values()):
        raise HTTPException(422, "Screening answers are too long")
    application = ats_adapter.submit(db, user, job_id, payload.cover_letter, payload.screening_answers)
    return {"message": "Application submitted", "application_id": application.id,
            "status": application.status, "ats_source": ats_adapter.name}

def application_data(item: Application):
    return {"id": item.id, "job_id": item.job_id, "status": item.status, "cover_letter": item.cover_letter,
            "created_at": item.created_at, "candidate_email": item.candidate_email or "",
            "resume_filename": item.resume_filename, "screening_answers": json.loads(item.answers_json or "{}"),
            "job": public_job(item.job)}

@app.get("/api/applications")
def my_applications(user: CurrentUser, db: DB):
    applications = ats_adapter.list_applications(db, user.id)
    return [application_data(item) for item in applications]

@app.get("/api/applications/{application_id}/status")
def application_status(application_id: int, user: CurrentUser, db: DB):
    application = ats_adapter.get_application(db, user.id, application_id)
    return {"application_id": application.id, "status": application.status, "ats_source": ats_adapter.name}

@app.post("/api/applications/{application_id}/withdraw")
def withdraw(application_id: int, user: CurrentUser, db: DB):
    ats_adapter.withdraw(db, user, application_id)
    return {"message": "Application withdrawn"}

@app.get("/api/applications/{application_id}/history")
def application_history(application_id: int, user: CurrentUser, db: DB):
    events = ats_adapter.get_status_history(db, user.id, application_id)
    return [{"status": e.status, "note": e.note, "created_at": e.created_at} for e in events]

def action_data(action: ApplicationAction):
    application = action.application
    return {"id": action.id, "type": action.action_type, "status": action.status,
            "scheduled_at": action.scheduled_at, "meeting_url": action.meeting_url, "details": action.details,
            "application_id": application.id, "job_title": application.job.title, "company": application.job.company}

@app.get("/api/applications/actions")
def application_actions(user: CurrentUser, db: DB):
    actions = db.scalars(
        select(ApplicationAction)
        .join(Application, ApplicationAction.application_id == Application.id)
        .where(Application.candidate_id == user.id, ApplicationAction.status != "cancelled")
        .order_by(ApplicationAction.created_at.desc())
    ).all()
    return [action_data(action) for action in actions]

@app.put("/api/application-actions/{action_id}/book")
def book_interview(action_id: int, payload: InterviewBookingIn, user: CurrentUser, db: DB):
    action = ats_adapter.book_interview(db, user.id, action_id, payload.scheduled_at)
    return action_data(action)

@app.post("/api/application-actions/{action_id}/accept")
def accept_offer(action_id: int, user: CurrentUser, db: DB):
    ats_adapter.accept_offer(db, user.id, action_id)
    return {"message": "Offer accepted"}

@app.get("/api/notifications")
def notifications(user: CurrentUser, db: DB):
    items = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50)).all()
    return [{"id": n.id, "message": n.message, "is_read": n.is_read, "created_at": n.created_at} for n in items]

@app.post("/api/notifications/{notification_id}/read")
def read_notification(notification_id: int, user: CurrentUser, db: DB):
    item = db.get(Notification, notification_id)
    if not item or item.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    item.is_read = True
    db.commit()
    return {"message": "Marked as read"}

@app.post("/api/notifications/read-all")
def read_all_notifications(user: CurrentUser, db: DB):
    items = db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))).all()
    for item in items:
        item.is_read = True
    db.commit()
    return {"updated": len(items)}

@app.get("/api/dashboard")
def dashboard(user: CurrentUser, db: DB):
    items = ats_adapter.list_applications(db, user.id)
    return {"applications": len(items), "in_review": sum(a.status in {"Under Review", "Shortlisted", "Interview Scheduled"} for a in items),
            "selected": sum(a.status == "Selected" for a in items), "saved_jobs": len(db.scalars(select(SavedJob).where(SavedJob.candidate_id == user.id)).all())}
