"""Add candidate preferences, resume metadata, and self-service actions."""
from alembic import op
import sqlalchemy as sa

revision = "0003_candidate_ats_workflows"
down_revision = "0002_local_job_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidate_profiles", sa.Column("resume_filename", sa.String(length=255), nullable=True))
    op.add_column("candidate_profiles", sa.Column("contact_email", sa.String(length=255), nullable=False, server_default=""))
    op.add_column("candidate_profiles", sa.Column("resume_content_type", sa.String(length=120), nullable=True))
    op.add_column("candidate_profiles", sa.Column("resume_uploaded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("candidate_profiles", sa.Column("resume_text", sa.Text(), nullable=False, server_default=""))
    op.add_column("candidate_profiles", sa.Column("preferred_roles", sa.Text(), nullable=False, server_default=""))
    op.add_column("candidate_profiles", sa.Column("work_mode", sa.String(length=30), nullable=False, server_default=""))
    op.add_column("candidate_profiles", sa.Column("expected_salary", sa.String(length=100), nullable=False, server_default=""))
    op.add_column("candidate_profiles", sa.Column("notice_period", sa.String(length=80), nullable=False, server_default=""))
    op.add_column("jobs", sa.Column("screening_questions", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("applications", sa.Column("resume_filename", sa.String(length=255), nullable=True))
    op.add_column("applications", sa.Column("answers_json", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("applications", sa.Column("candidate_email", sa.String(length=255), nullable=False, server_default=""))
    op.create_table(
        "application_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="action_required"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meeting_url", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("details", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_application_actions_application_id", "application_actions", ["application_id"])
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("location", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("skill", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("employment_type", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("experience", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saved_searches_candidate_id", "saved_searches", ["candidate_id"])


def downgrade():
    op.drop_index("ix_saved_searches_candidate_id", table_name="saved_searches")
    op.drop_table("saved_searches")
    op.drop_index("ix_application_actions_application_id", table_name="application_actions")
    op.drop_table("application_actions")
    op.drop_column("applications", "answers_json")
    op.drop_column("applications", "candidate_email")
    op.drop_column("applications", "resume_filename")
    op.drop_column("jobs", "screening_questions")
    op.drop_column("candidate_profiles", "notice_period")
    op.drop_column("candidate_profiles", "expected_salary")
    op.drop_column("candidate_profiles", "work_mode")
    op.drop_column("candidate_profiles", "preferred_roles")
    op.drop_column("candidate_profiles", "resume_text")
    op.drop_column("candidate_profiles", "resume_uploaded_at")
    op.drop_column("candidate_profiles", "resume_content_type")
    op.drop_column("candidate_profiles", "resume_filename")
    op.drop_column("candidate_profiles", "contact_email")
