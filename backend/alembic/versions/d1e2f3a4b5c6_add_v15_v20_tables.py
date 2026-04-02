"""add v1.5 and v2.0 tables

Revision ID: d1e2f3a4b5c6
Revises: c5d6e7f8a9b0
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1e2f3a4b5c6'
down_revision = 'c5d6e7f8a9b0'
branch_labels = None
depends_on = None

def upgrade():
    # V1.5 表
    op.create_table('ai_chat_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(200)),
        sa.Column('market', sa.String(10)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table('ai_chat_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.String(50), sa.ForeignKey('ai_chat_sessions.session_id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table('market_sentiments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('market', sa.String(10), nullable=False, index=True),
        sa.Column('sentiment_score', sa.Float()),
        sa.Column('sentiment_label', sa.String(20)),
        sa.Column('news_count', sa.Integer(), default=0),
        sa.Column('positive_count', sa.Integer(), default=0),
        sa.Column('negative_count', sa.Integer(), default=0),
        sa.Column('analysis_result', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    op.create_table('anomaly_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('market', sa.String(10), nullable=False),
        sa.Column('anomaly_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), default='medium'),
        sa.Column('description', sa.Text()),
        sa.Column('detail', sa.Text()),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    op.create_table('strategy_attributions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('strategy_id', sa.String(50), nullable=False, index=True),
        sa.Column('strategy_name', sa.String(100)),
        sa.Column('market', sa.String(10)),
        sa.Column('total_return', sa.Float()),
        sa.Column('alpha', sa.Float()),
        sa.Column('beta_return', sa.Float()),
        sa.Column('timing_return', sa.Float()),
        sa.Column('sector_contribution', sa.Text()),
        sa.Column('risk_contribution', sa.Text()),
        sa.Column('timing_analysis', sa.Text()),
        sa.Column('full_report', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # V2.0 表
    op.create_table('tenants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('slug', sa.String(50), unique=True, index=True),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('plan', sa.String(20), default='free'),
        sa.Column('max_users', sa.Integer(), default=5),
        sa.Column('max_strategies', sa.Integer(), default=10),
        sa.Column('max_api_calls', sa.Integer(), default=10000),
        sa.Column('brand_name', sa.String(200)),
        sa.Column('brand_logo', sa.String(500)),
        sa.Column('primary_color', sa.String(20), default='#304156'),
        sa.Column('custom_domain', sa.String(200)),
        sa.Column('custom_css', sa.Text()),
        sa.Column('current_users', sa.Integer(), default=0),
        sa.Column('current_api_calls', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime()),
    )

    op.create_table('plugins',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plugin_id', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('version', sa.String(20), default='1.0.0'),
        sa.Column('author', sa.String(100)),
        sa.Column('category', sa.String(50)),
        sa.Column('entry_point', sa.String(200)),
        sa.Column('config_schema', sa.Text()),
        sa.Column('permissions', sa.Text()),
        sa.Column('is_public', sa.Boolean(), default=False),
        sa.Column('is_verified', sa.Boolean(), default=False),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('install_count', sa.Integer(), default=0),
        sa.Column('rating_avg', sa.Float(), default=0),
        sa.Column('rating_count', sa.Integer(), default=0),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table('plugin_installations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plugin_id', sa.Integer(), sa.ForeignKey('plugins.id'), nullable=False),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('config', sa.Text()),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('installed_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table('openapi_keys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key_name', sa.String(200), nullable=False),
        sa.Column('api_key', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('api_secret_hash', sa.String(255)),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('permissions', sa.Text()),
        sa.Column('rate_limit', sa.Integer(), default=60),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('last_used_at', sa.DateTime()),
        sa.Column('total_calls', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime()),
    )

    op.create_table('api_call_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('api_key_id', sa.Integer(), sa.ForeignKey('openapi_keys.id')),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id')),
        sa.Column('endpoint', sa.String(200), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('status_code', sa.Integer()),
        sa.Column('response_time_ms', sa.Integer()),
        sa.Column('ip_address', sa.String(50)),
        sa.Column('user_agent', sa.String(500)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    op.create_table('subscription_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plan_id', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('price_monthly', sa.Float(), default=0),
        sa.Column('price_yearly', sa.Float(), default=0),
        sa.Column('max_users', sa.Integer(), default=5),
        sa.Column('max_strategies', sa.Integer(), default=10),
        sa.Column('max_api_calls', sa.Integer(), default=10000),
        sa.Column('features', sa.Text()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table('subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('plan_id', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('billing_cycle', sa.String(10), default='monthly'),
        sa.Column('current_period_start', sa.DateTime(), nullable=False),
        sa.Column('current_period_end', sa.DateTime(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('trial_end', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table('usage_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('metric', sa.String(50), nullable=False),
        sa.Column('value', sa.Integer(), default=1),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), server_default=sa.func.now()),
    )

def downgrade():
    # 按依赖关系逆序删除
    op.drop_table('usage_records')
    op.drop_table('subscriptions')
    op.drop_table('subscription_plans')
    op.drop_table('api_call_logs')
    op.drop_table('openapi_keys')
    op.drop_table('plugin_installations')
    op.drop_table('plugins')
    op.drop_table('tenants')
    op.drop_table('strategy_attributions')
    op.drop_table('anomaly_records')
    op.drop_table('market_sentiments')
    op.drop_table('ai_chat_messages')
    op.drop_table('ai_chat_sessions')
