"""add_user_role_and_token_tracking

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str]] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add role to users, ip_address and user_agent to token tables."""
    # Add role column to users with default 'viewer'
    op.add_column('users', sa.Column('role', sa.String(), nullable=False, server_default='viewer'))

    # Add tracking columns to refresh_tokens
    op.add_column('refresh_tokens', sa.Column('ip_address', sa.String(), nullable=True))
    op.add_column('refresh_tokens', sa.Column('user_agent', sa.String(), nullable=True))

    # Add tracking columns to password_reset_tokens
    op.add_column('password_reset_tokens', sa.Column('ip_address', sa.String(), nullable=True))
    op.add_column('password_reset_tokens', sa.Column('user_agent', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove role from users, ip_address and user_agent from token tables."""
    op.drop_column('password_reset_tokens', 'user_agent')
    op.drop_column('password_reset_tokens', 'ip_address')
    op.drop_column('refresh_tokens', 'user_agent')
    op.drop_column('refresh_tokens', 'ip_address')
    op.drop_column('users', 'role')
