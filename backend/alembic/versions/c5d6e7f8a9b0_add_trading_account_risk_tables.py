"""add_trading_account_risk_tables

Revision ID: c5d6e7f8a9b0
Revises: a3f1b2c4d5e6
Create Date: 2026-04-01 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'a3f1b2c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 交易账户表
    op.create_table(
        'trading_accounts',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(100), nullable=False, comment='账户名称'),
        sa.Column('market', sa.Enum('A', 'HK', 'US', name='markettype'), nullable=False, comment='市场'),
        sa.Column('fmz_account_id', sa.Integer(), comment='FMZ 账户ID'),
        sa.Column('fmz_api_key', sa.String(200), comment='FMZ API Key'),
        sa.Column('fmz_secret_key', sa.String(200), comment='FMZ Secret Key'),
        sa.Column('status', sa.String(20), server_default='active', comment='状态 active/disabled'),
        sa.Column('is_default', sa.Boolean(), server_default='0', comment='是否默认账户'),
        sa.Column('risk_params', sa.Text(), comment='风控参数(JSON)'),
        sa.Column('total_pnl', sa.Float(), server_default='0', comment='累计盈亏'),
        sa.Column('today_pnl', sa.Float(), server_default='0', comment='今日盈亏'),
        sa.Column('total_trades', sa.Integer(), server_default='0', comment='总交易次数'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), comment='更新时间'),
        comment='FMZ交易账户表'
    )
    op.create_index('ix_trading_accounts_created_at', 'trading_accounts', ['created_at'])

    # 风控规则表
    op.create_table(
        'risk_rules',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(200), nullable=False, comment='规则名称'),
        sa.Column('rule_type', sa.String(50), nullable=False, comment='规则类型'),
        sa.Column('market', sa.Enum('A', 'HK', 'US', name='markettype'), nullable=False, comment='适用市场'),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('trading_accounts.id'), nullable=True, comment='绑定账户ID'),
        sa.Column('params', sa.Text(), nullable=False, comment='规则参数(JSON)'),
        sa.Column('is_enabled', sa.Boolean(), server_default='1', comment='是否启用'),
        sa.Column('priority', sa.Integer(), server_default='0', comment='优先级'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), comment='更新时间'),
        comment='风控规则表'
    )

    # 风控事件记录表
    op.create_table(
        'risk_events',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('rule_id', sa.Integer(), nullable=True, comment='触发的规则ID'),
        sa.Column('rule_name', sa.String(200), comment='规则名称'),
        sa.Column('rule_type', sa.String(50), comment='规则类型'),
        sa.Column('market', sa.Enum('A', 'HK', 'US', name='markettype'), nullable=False, comment='市场'),
        sa.Column('account_id', sa.Integer(), nullable=True, comment='账户ID'),
        sa.Column('severity', sa.String(20), server_default='warning', comment='严重级别'),
        sa.Column('action', sa.String(50), comment='执行动作'),
        sa.Column('message', sa.Text(), comment='事件描述'),
        sa.Column('detail', sa.Text(), comment='详细信息(JSON)'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), comment='触发时间'),
        comment='风控事件记录表'
    )
    op.create_index('ix_risk_events_created_at', 'risk_events', ['created_at'])


def downgrade() -> None:
    op.drop_table('risk_events')
    op.drop_table('risk_rules')
    op.drop_table('trading_accounts')
