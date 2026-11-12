from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=10, max_length=128)

class ProfileIn(BaseModel):
    full_name: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=40)
    contact_email: EmailStr | None = None
    location: str = Field(default="", max_length=160)
    summary: str = Field(default="", max_length=5000)
    skills: str = Field(default="", max_length=2000)
    linkedin_url: str = Field(default="", max_length=500)
    github_url: str = Field(default="", max_length=500)
    portfolio_url: str = Field(default="", max_length=500)
    preferred_roles: str = Field(default="", max_length=1000)
    work_mode: str = Field(default="", max_length=30)
    expected_salary: str = Field(default="", max_length=100)
    notice_period: str = Field(default="", max_length=80)

    @field_validator("contact_email", mode="before")
    @classmethod
    def blank_email_to_none(cls, value):
        return value or None

class ApplyIn(BaseModel):
    cover_letter: str = Field(default="", max_length=5000)
    screening_answers: dict[str, str] = Field(default_factory=dict)

class SavedSearchIn(BaseModel):
    query: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=160)
    skill: str = Field(default="", max_length=160)
    employment_type: str = Field(default="", max_length=40)
    experience: str = Field(default="", max_length=80)

class InterviewBookingIn(BaseModel):
    scheduled_at: datetime

class EducationIn(BaseModel):
    institution: str = Field(min_length=2, max_length=200)
    degree: str = Field(default="", max_length=160)
    field_of_study: str = Field(default="", max_length=160)
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)

class ExperienceIn(BaseModel):
    company: str = Field(min_length=2, max_length=200)
    title: str = Field(min_length=2, max_length=160)
    location: str = Field(default="", max_length=160)
    start_date: str = Field(default="", max_length=20)
    end_date: str = Field(default="", max_length=20)
    description: str = Field(default="", max_length=4000)
