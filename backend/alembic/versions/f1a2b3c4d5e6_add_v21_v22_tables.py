"""add v2.1 and v2.2 tables (push notifications + deep learning)

Revision ID: f1a2b3c4d5e6
Revises: d1e2f3a4b5c6
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    # ========== V2.2 深度学习表 ==========

    # 机器学习模型注册表
    op.create_table('ml_models',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('model_type', sa.String(50), nullable=False),
        sa.Column('version', sa.String(20), server_default='1.0.0'),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('file_path', sa.String(500)),
        sa.Column('metrics', sa.Text()),
        sa.Column('features', sa.Text()),
        sa.Column('hyperparams', sa.Text()),
        sa.Column('description', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # 模型训练记录表
    op.create_table('training_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('model_id', sa.Integer(), sa.ForeignKey('ml_models.id'), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('dataset_info', sa.Text()),
        sa.Column('train_metrics', sa.Text()),
        sa.Column('test_metrics', sa.Text()),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # 模型预测记录表
    op.create_table('prediction_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('model_id', sa.Integer(), sa.ForeignKey('ml_models.id'), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('market', sa.String(10), server_default='a_stock'),
        sa.Column('prediction_date', sa.DateTime(), nullable=False),
        sa.Column('predicted_return', sa.Float()),
        sa.Column('predicted_direction', sa.String(10)),
        sa.Column('confidence', sa.Float()),
        sa.Column('actual_return', sa.Float()),
        sa.Column('actual_direction', sa.String(10)),
        sa.Column('features_snapshot', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # ========== V2.1 推送通知表 ==========

    # 推送通知订阅表
    op.create_table('push_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('endpoint', sa.String(500), unique=True, nullable=False, index=True),
        sa.Column('keys_auth', sa.String(200), nullable=False),
        sa.Column('keys_p256dh', sa.String(200), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # 推送通知历史记录表
    op.create_table('push_notification_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('url', sa.String(500)),
        sa.Column('icon', sa.String(500)),
        sa.Column('status', sa.String(20), server_default='sent'),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade():
    # 按依赖关系逆序删除
    op.drop_table('push_notification_history')
    op.drop_table('push_subscriptions')
    op.drop_table('prediction_records')
    op.drop_table('training_records')
    op.drop_table('ml_models')
