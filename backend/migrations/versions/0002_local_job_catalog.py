"""Make sample jobs independent of recruiter accounts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0002_local_job_catalog"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    job_columns = {column["name"]: column for column in inspector.get_columns("jobs")}
    if "source" not in job_columns:
        op.add_column("jobs", sa.Column("source", sa.String(length=40), nullable=False, server_default="local"))
    if "recruiter_id" in job_columns:
        for constraint in inspector.get_foreign_keys("jobs"):
            if constraint.get("constrained_columns") == ["recruiter_id"] and constraint.get("name"):
                op.drop_constraint(constraint["name"], "jobs", type_="foreignkey")
        op.drop_column("jobs", "recruiter_id")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "role" in user_columns:
        connection.execute(text("UPDATE users SET is_active = false WHERE role <> 'candidate'"))
        op.drop_column("users", "role")
    application_columns = {column["name"] for column in inspector.get_columns("applications")}
    if "internal_note" in application_columns:
        op.drop_column("applications", "internal_note")

def downgrade():
    inspector = inspect(op.get_bind())
    job_columns = {column["name"]: column for column in inspector.get_columns("jobs")}
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    application_columns = {column["name"] for column in inspector.get_columns("applications")}
    if "source" in job_columns:
        op.drop_column("jobs", "source")
    if "recruiter_id" not in job_columns:
        op.add_column("jobs", sa.Column("recruiter_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_jobs_recruiter_id_users", "jobs", "users", ["recruiter_id"], ["id"])
    if "role" not in user_columns:
        op.add_column("users", sa.Column("role", sa.String(length=20), nullable=False, server_default="candidate"))
    if "internal_note" not in application_columns:
        op.add_column("applications", sa.Column("internal_note", sa.Text(), nullable=False, server_default=""))
