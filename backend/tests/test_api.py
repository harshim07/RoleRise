import hashlib
import io
import zipfile
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import ApplicationAction, Job, PasswordResetToken, User
from app.seed import SAMPLE_JOBS
from app.services.jobs import ingest_local_job

SCREENING_ANSWERS = {
    "notice_period": "2 weeks",
    "work_authorization": "Authorized to work",
}


def test_seed_catalog_has_a_broad_searchable_role_selection():
    titles = {job["title"] for job in SAMPLE_JOBS}
    assert len(SAMPLE_JOBS) == 27
    assert len({(job["title"], job["company"]) for job in SAMPLE_JOBS}) == len(SAMPLE_JOBS)
    assert {
        "Frontend Engineer",
        "Data Analyst",
        "Product Manager",
        "Marketing Manager",
        "Customer Success Manager",
        "Cybersecurity Analyst",
        "Software Engineering Intern",
    } <= titles
    assert all(job["skills"] and job["description"] for job in SAMPLE_JOBS)


def register(client, email="candidate@example.com"):
    response = client.post("/api/auth/register", json={
        "email": email,
        "password": "CandidateTest!123",
        "full_name": "Taylor Candidate",
    })
    assert response.status_code == 201
    return response.json()["access_token"]


def create_job(client):
    engine = app.dependency_overrides[get_db].engine
    with Session(engine) as db:
        job = Job(
            source="local-sample",
            title="Python Engineer",
            company="Example Co",
            location="Remote",
            skills="Python, FastAPI",
            description="Build and maintain reliable APIs for our growing product team.",
        )
        db.add(job)
        db.commit()
        return job.id


def test_registration_login_and_profile(client):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    profile = client.get("/api/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Taylor Candidate"
    login = client.post("/api/auth/login", json={"email": "candidate@example.com", "password": "CandidateTest!123"})
    assert login.status_code == 200
    assert set(login.json()["user"]) == {"id", "email"}
    assert client.post("/api/auth/login", json={"email": "candidate@example.com", "password": "wrong"}).status_code == 401


def test_job_search_pagination_and_no_job_management_api(client):
    token = register(client)
    job_id = create_job(client)
    results = client.get("/api/jobs?q=python&page=1&limit=1")
    assert results.status_code == 200
    assert results.json()["total"] == 1
    assert results.json()["items"][0]["id"] == job_id
    filtered = client.get("/api/jobs?experience=Any&skill=FastAPI")
    assert filtered.json()["total"] == 1
    assert client.post("/api/jobs", headers={"Authorization": f"Bearer {token}"}, json={}).status_code == 404


def test_duplicate_application_history_and_candidate_privacy(client):
    candidate_token = register(client)
    job_id = create_job(client)
    candidate_headers = {"Authorization": f"Bearer {candidate_token}"}
    first = client.post(f"/api/jobs/{job_id}/apply", headers=candidate_headers, json={
        "cover_letter": "I am excited to apply.",
        "screening_answers": SCREENING_ANSWERS,
    })
    assert first.status_code == 201
    assert first.json()["ats_source"] == "mock"
    application_id = first.json()["application_id"]
    assert client.get(f"/api/applications/{application_id}/status", headers=candidate_headers).json()["status"] == "Applied"
    duplicate = client.post(f"/api/jobs/{job_id}/apply", headers=candidate_headers, json={"screening_answers": SCREENING_ANSWERS})
    assert duplicate.status_code == 409
    history = client.get(
        f"/api/applications/{first.json()['application_id']}/history",
        headers=candidate_headers,
    )
    assert history.status_code == 200
    assert [event["status"] for event in history.json()] == ["Applied"]
    other_token = register(client, "other@example.com")
    private_history = client.get(
        f"/api/applications/{first.json()['application_id']}/history",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert private_history.status_code == 404
    private_status = client.get(
        f"/api/applications/{first.json()['application_id']}/status",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert private_status.status_code == 404


def test_application_rejected_for_closed_job(client):
    token = register(client)
    job_id = create_job(client)
    engine = app.dependency_overrides[get_db].engine
    with Session(engine) as db:
        job = db.get(Job, job_id)
        job.is_open = False
        db.commit()
    response = client.post(f"/api/jobs/{job_id}/apply", headers={"Authorization": f"Bearer {token}"}, json={})
    assert response.status_code == 400


def test_candidate_can_withdraw_and_receives_owned_notification(client):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    job_id = create_job(client)
    applied = client.post(f"/api/jobs/{job_id}/apply", headers=headers, json={"screening_answers": SCREENING_ANSWERS})
    application_id = applied.json()["application_id"]
    engine = app.dependency_overrides[get_db].engine
    with Session(engine) as db:
        db.add(ApplicationAction(application_id=application_id, action_type="interview"))
        db.commit()
    withdrawn = client.post(f"/api/applications/{application_id}/withdraw", headers=headers)
    assert withdrawn.status_code == 200
    assert client.get("/api/applications", headers=headers).json()[0]["status"] == "Withdrawn"
    assert client.get("/api/applications/actions", headers=headers).json() == []
    assert any("withdrawn" in notice["message"] for notice in client.get("/api/notifications", headers=headers).json())


def test_resume_upload_rejects_non_pdf(client):
    token = register(client)
    response = client.post(
        "/api/profile/resume",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("resume.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400


def test_docx_resume_upload_parses_contact_details_and_can_be_removed(client):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    document = b"""<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
      <w:p><w:r><w:t>Jordan Candidate</w:t></w:r></w:p>
      <w:p><w:r><w:t>jordan@example.com</w:t></w:r></w:p>
      <w:p><w:r><w:t>+1 415 555 0198</w:t></w:r></w:p>
      <w:p><w:r><w:t>Location: Seattle, WA</w:t></w:r></w:p>
      <w:p><w:r><w:t>Professional Summary</w:t></w:r></w:p>
      <w:p><w:r><w:t>Build robust services.</w:t></w:r></w:p>
      <w:p><w:r><w:t>Skills</w:t></w:r></w:p>
      <w:p><w:r><w:t>Python, FastAPI</w:t></w:r></w:p>
    </w:body></w:document>"""
    contents = io.BytesIO()
    with zipfile.ZipFile(contents, "w") as archive:
        archive.writestr("word/document.xml", document)

    uploaded = client.post(
        "/api/profile/resume",
        headers=headers,
        files={"file": ("jordan.docx", contents.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["parsed"] == {
        "full_name": "Jordan Candidate",
        "email": "jordan@example.com",
        "phone": "+1 415 555 0198",
        "location": "Seattle, WA",
        "summary": "Build robust services.",
        "skills": "Python, FastAPI",
    }
    profile = client.get("/api/profile", headers=headers).json()
    assert profile["full_name"] == "Taylor Candidate"
    assert profile["contact_email"] == "jordan@example.com"
    assert profile["phone"] == "+1 415 555 0198"
    assert profile["location"] == "Seattle, WA"
    assert profile["summary"] == "Build robust services."
    assert profile["skills"] == "Python, FastAPI"
    job_id = create_job(client)
    recommendation = client.get("/api/recommendations", headers=headers).json()[0]
    assert recommendation["id"] == job_id
    assert {"Python", "FastAPI"} <= set(recommendation["match_tags"])
    assert client.get("/api/profile/resume", headers=headers).status_code == 200
    assert client.delete("/api/profile/resume", headers=headers).status_code == 200


def test_profile_preferences_and_strength_are_persisted(client):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    saved = client.put("/api/profile", headers=headers, json={
        "full_name": "Taylor Candidate",
        "contact_email": "",
        "phone": "555-0101",
        "location": "Remote",
        "summary": "Product-minded engineer.",
        "skills": "Python, FastAPI",
        "linkedin_url": "https://linkedin.com/in/taylor",
        "preferred_roles": "Python Engineer",
        "work_mode": "Remote",
        "expected_salary": "$120k",
        "notice_period": "2 weeks",
    })
    assert saved.status_code == 200
    profile = client.get("/api/profile", headers=headers).json()
    assert profile["contact_email"] == ""
    assert profile["preferred_roles"] == "Python Engineer"
    assert profile["completion"] == 66
    same_profile_saved_again = client.put("/api/profile", headers=headers, json={
        "full_name": "Taylor Candidate",
        "contact_email": "",
        "phone": "555-0101",
        "location": "Remote",
        "summary": "Product-minded engineer.",
        "skills": "Python, FastAPI",
        "linkedin_url": "https://linkedin.com/in/taylor",
        "preferred_roles": "Python Engineer",
        "work_mode": "Remote",
        "expected_salary": "$120k",
        "notice_period": "2 weeks",
    })
    assert same_profile_saved.status_code == 200
    changed_skills = client.put("/api/profile", headers=headers, json={
        "skills": "Python, SQL",
    })
    assert changed_skills.status_code == 200
    assert {skill["name"] for skill in client.get("/api/profile", headers=headers).json()["skill_items"]} == {"Python", "SQL"}


def test_candidate_can_book_only_their_own_interview_action(client):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    job_id = create_job(client)
    submitted = client.post(
        f"/api/jobs/{job_id}/apply",
        headers=headers,
        json={"screening_answers": SCREENING_ANSWERS},
    )
    application_id = submitted.json()["application_id"]
    engine = app.dependency_overrides[get_db].engine
    with Session(engine) as db:
        action = ApplicationAction(application_id=application_id, action_type="interview")
        db.add(action)
        db.commit()
        action_id = action.id
    booking = {"scheduled_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()}
    booked = client.put(f"/api/application-actions/{action_id}/book", headers=headers, json=booking)
    assert booked.status_code == 200
    assert booked.json()["meeting_url"].startswith("https://meet.example.com/mock-interview/")
    assert client.get("/api/applications", headers=headers).json()[0]["status"] == "Interview Scheduled"
    assert client.get(f"/api/applications/{application_id}/status", headers=headers).json()["ats_source"] == "mock"

    other_headers = {"Authorization": f"Bearer {register('other@example.com')}"}
    assert client.put(f"/api/application-actions/{action_id}/book", headers=other_headers, json=booking).status_code == 404


def test_saved_search_and_mark_all_read_are_candidate_scoped(client):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    search = {"query": "Python", "location": "Remote", "skill": "", "employment_type": "", "experience": ""}
    created = client.post("/api/saved-searches", headers=headers, json=search)
    assert created.status_code == 201
    duplicate = client.post("/api/saved-searches", headers=headers, json=search)
    assert duplicate.json()["id"] == created.json()["id"]
    job_id = create_job(client)
    client.post(f"/api/jobs/{job_id}/apply", headers=headers, json={"screening_answers": SCREENING_ANSWERS})
    assert client.post("/api/notifications/read-all", headers=headers).json()["updated"] == 1
    assert client.get("/api/notifications", headers=headers).json()[0]["is_read"] is True
    other_headers = {"Authorization": f"Bearer {register('other@example.com')}"}
    assert client.delete(f"/api/saved-searches/{created.json()['id']}", headers=other_headers).status_code == 404


def test_mock_ats_offer_acceptance_updates_status_history(client):
    headers = {"Authorization": f"Bearer {register()}"}
    job_id = create_job(client)
    application_id = client.post(
        f"/api/jobs/{job_id}/apply",
        headers=headers,
        json={"screening_answers": SCREENING_ANSWERS},
    ).json()["application_id"]
    engine = app.dependency_overrides[get_db].engine
    with Session(engine) as db:
        action = ApplicationAction(application_id=application_id, action_type="offer")
        db.add(action)
        db.commit()
        action_id = action.id

    accepted = client.post(f"/api/application-actions/{action_id}/accept", headers=headers)
    assert accepted.status_code == 200
    assert client.get(f"/api/applications/{application_id}/status", headers=headers).json()["status"] == "Offer Accepted"
    history = client.get(f"/api/applications/{application_id}/history", headers=headers).json()
    assert [event["status"] for event in history] == ["Applied", "Offer Accepted"]


def test_new_mock_ats_jobs_notify_matching_saved_searches_once(client):
    headers = {"Authorization": f"Bearer {register()}"}
    search = {"query": "Python", "location": "Remote", "skill": "FastAPI", "employment_type": "", "experience": ""}
    assert client.post("/api/saved-searches", headers=headers, json=search).status_code == 201
    listing = {
        "title": "Python Engineer",
        "company": "Alert Systems",
        "location": "Remote",
        "employment_type": "Full-time",
        "experience": "3+ years",
        "salary_range": "$120k",
        "skills": "Python, FastAPI",
        "description": "Build APIs.",
    }
    engine = app.dependency_overrides[get_db].engine
    with Session(engine) as db:
        _, created = ingest_local_job(db, listing)
        db.commit()
        assert created is True
        _, created_again = ingest_local_job(db, listing)
        db.commit()
        assert created_again is False
    notices = client.get("/api/notifications", headers=headers).json()
    assert len(notices) == 1
    assert "Python Engineer" in notices[0]["message"]


def test_password_reset_revokes_existing_sessions(client):
    token = register(client)
    reset_token = "one-time-reset-token-with-enough-entropy"
    engine = app.dependency_overrides[get_db].engine
    with Session(engine) as db:
        user = db.query(User).filter_by(email="candidate@example.com").one()
        db.add(PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(reset_token.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        ))
        db.commit()
    result = client.post("/api/auth/reset-password", json={"token": reset_token, "password": "NewCandidatePass!234"})
    assert result.status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "candidate@example.com", "password": "NewCandidatePass!234"}).status_code == 200


def test_candidate_can_edit_owned_education_and_experience_with_valid_dates(client):
    token = register()
    headers = {"Authorization": f"Bearer {token}"}
    education_id = client.post("/api/profile/education", headers=headers, json={
        "institution": "Example University",
        "degree": "Bachelor of Science",
        "field_of_study": "Computer Science",
        "start_year": 2018,
        "end_year": 2022,
    }).json()["id"]
    experience_id = client.post("/api/profile/experience", headers=headers, json={
        "company": "Example Co",
        "title": "Engineer",
        "start_date": "2022-01",
        "end_date": "2024-12",
    }).json()["id"]

    updated_education = client.put(f"/api/profile/education/{education_id}", headers=headers, json={
        "institution": "Example Institute",
        "degree": "Master of Science",
        "field_of_study": "Data Science",
        "start_year": 2022,
        "end_year": 2024,
    })
    updated_experience = client.put(f"/api/profile/experience/{experience_id}", headers=headers, json={
        "company": "New Company",
        "title": "Senior Engineer",
        "location": "Remote",
        "start_date": "2025-01-15",
        "end_date": "",
        "description": "Leading platform work.",
    })
    assert updated_education.status_code == 200
    assert updated_experience.status_code == 200

    profile = client.get("/api/profile", headers=headers).json()
    assert profile["education"][0]["institution"] == "Example Institute"
    assert profile["education"][0]["start_year"] == 2022
    assert profile["experience"][0]["title"] == "Senior Engineer"
    assert profile["experience"][0]["start_date"] == "2025-01-15"
    assert profile["experience"][0]["end_date"] == ""

    invalid_education = client.put(f"/api/profile/education/{education_id}", headers=headers, json={
        "institution": "Example Institute",
        "start_year": 2025,
        "end_year": 2024,
    })
    invalid_experience = client.put(f"/api/profile/experience/{experience_id}", headers=headers, json={
        "company": "New Company",
        "title": "Senior Engineer",
        "start_date": "2025-09",
        "end_date": "2025-01",
    })
    assert invalid_education.status_code == 422
    assert invalid_experience.status_code == 422

    other_headers = {"Authorization": f"Bearer {register('other@example.com')}"}
    assert client.put(f"/api/profile/education/{education_id}", headers=other_headers, json={
        "institution": "Not yours",
    }).status_code == 404


def test_recruiting_endpoints_are_not_part_of_the_candidate_api(client):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/recruiter/applications", headers=headers).status_code == 404
    assert client.get("/api/recruiter/jobs", headers=headers).status_code == 404


def test_logout_revokes_the_current_token(client):
    token = register(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
