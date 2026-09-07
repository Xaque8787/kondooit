"""Add playback preference columns to profiles table.

Revision ID: 0007_profile_playback_preferences
Revises: 0006_watch_progress
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("max_resolution", sa.Integer(), nullable=False, server_default="2160"))
    op.add_column("profiles", sa.Column("allow_direct_play", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("profiles", sa.Column("allow_remux", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("profiles", sa.Column("allow_transcode", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("profiles", sa.Column("auto_play", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("profiles", sa.Column("client_video_codecs", sa.String(), nullable=False, server_default=""))
    op.add_column("profiles", sa.Column("client_audio_codecs", sa.String(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("profiles", "client_audio_codecs")
    op.drop_column("profiles", "client_video_codecs")
    op.drop_column("profiles", "auto_play")
    op.drop_column("profiles", "allow_transcode")
    op.drop_column("profiles", "allow_remux")
    op.drop_column("profiles", "allow_direct_play")
    op.drop_column("profiles", "max_resolution")
