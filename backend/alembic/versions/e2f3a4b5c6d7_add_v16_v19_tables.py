"""add v1.6 ~ v1.9 tables (community, multi_market, ha, algo_engine)

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = 'e2f3a4b5c6d7'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==================== V1.6 社区表（7 张）====================

    # user_profiles
    op.create_table(
        'user_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('expertise', sa.String(200), nullable=True),
        sa.Column('risk_preference', sa.String(50), nullable=True, default='medium'),
        sa.Column('total_trades', sa.Integer(), nullable=True, default=0),
        sa.Column('win_rate', sa.Float(), nullable=True, default=0.0),
        sa.Column('total_pnl', sa.Float(), nullable=True, default=0.0),
        sa.Column('followers_count', sa.Integer(), nullable=True, default=0),
        sa.Column('following_count', sa.Integer(), nullable=True, default=0),
        sa.Column('posts_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # user_follows
    op.create_table(
        'user_follows',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('follower_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('following_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('follower_id', 'following_id', name='uq_follower_following'),
    )

    # discussion_posts
    op.create_table(
        'discussion_posts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(50), nullable=True, default='general'),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('likes_count', sa.Integer(), nullable=True, default=0),
        sa.Column('comments_count', sa.Integer(), nullable=True, default=0),
        sa.Column('views_count', sa.Integer(), nullable=True, default=0),
        sa.Column('is_pinned', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_featured', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # post_comments
    op.create_table(
        'post_comments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('discussion_posts.id'), nullable=False),
        sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('post_comments.id'), nullable=True),
        sa.Column('likes_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # post_likes
    op.create_table(
        'post_likes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('discussion_posts.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('post_id', 'user_id', name='uq_post_user_like'),
    )

    # trade_shares
    op.create_table(
        'trade_shares',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('is_anonymous', sa.Boolean(), nullable=True, default=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('market', sa.String(20), nullable=True, default='A'),
        sa.Column('side', sa.String(10), nullable=True),
        sa.Column('entry_price', sa.Float(), nullable=True),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('pnl', sa.Float(), nullable=True),
        sa.Column('pnl_pct', sa.Float(), nullable=True),
        sa.Column('strategy_name', sa.String(100), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('likes_count', sa.Integer(), nullable=True, default=0),
        sa.Column('comments_count', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # private_messages
    op.create_table(
        'private_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sender_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('receiver_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # ==================== V1.7 多市场表（4 张）====================

    # futures_contracts
    op.create_table(
        'futures_contracts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('exchange', sa.String(20), nullable=True),
        sa.Column('underlying', sa.String(20), nullable=True),
        sa.Column('contract_month', sa.String(10), nullable=True),
        sa.Column('multiplier', sa.Float(), nullable=True),
        sa.Column('margin_rate', sa.Float(), nullable=True),
        sa.Column('tick_size', sa.Float(), nullable=True),
        sa.Column('last_price', sa.Float(), nullable=True),
        sa.Column('change_pct', sa.Float(), nullable=True),
        sa.Column('volume', sa.BigInteger(), nullable=True),
        sa.Column('open_interest', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # crypto_markets
    op.create_table(
        'crypto_markets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('base_currency', sa.String(20), nullable=True),
        sa.Column('quote_currency', sa.String(20), nullable=True),
        sa.Column('last_price', sa.Float(), nullable=True),
        sa.Column('change_24h', sa.Float(), nullable=True),
        sa.Column('high_24h', sa.Float(), nullable=True),
        sa.Column('low_24h', sa.Float(), nullable=True),
        sa.Column('volume_24h', sa.Float(), nullable=True),
        sa.Column('market_cap', sa.BigInteger(), nullable=True),
        sa.Column('circulating_supply', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # etf_info
    op.create_table(
        'etf_info',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('market', sa.String(20), nullable=True),
        sa.Column('nav', sa.Float(), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('premium_rate', sa.Float(), nullable=True),
        sa.Column('total_assets', sa.Float(), nullable=True),
        sa.Column('expense_ratio', sa.Float(), nullable=True),
        sa.Column('tracking_index', sa.String(100), nullable=True),
        sa.Column('top_holdings', sa.Text(), nullable=True),
        sa.Column('sector_allocation', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # arbitrage_opportunities
    op.create_table(
        'arbitrage_opportunities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol_a', sa.String(50), nullable=False),
        sa.Column('market_a', sa.String(20), nullable=True),
        sa.Column('symbol_b', sa.String(50), nullable=False),
        sa.Column('market_b', sa.String(20), nullable=True),
        sa.Column('spread', sa.Float(), nullable=True),
        sa.Column('spread_pct', sa.Float(), nullable=True),
        sa.Column('z_score', sa.Float(), nullable=True),
        sa.Column('is_profitable', sa.Boolean(), nullable=True, default=False),
        sa.Column('estimated_pnl', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # ==================== V1.8 高可用表（4 张）====================

    # database_backups
    op.create_table(
        'database_backups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('backup_id', sa.String(100), nullable=False, unique=True),
        sa.Column('backup_type', sa.String(20), nullable=True, default='full'),
        sa.Column('status', sa.String(20), nullable=True, default='pending'),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('tables_count', sa.Integer(), nullable=True),
        sa.Column('rows_count', sa.BigInteger(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # cluster_nodes
    op.create_table(
        'cluster_nodes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('node_id', sa.String(100), nullable=False, unique=True),
        sa.Column('node_type', sa.String(20), nullable=True),
        sa.Column('host', sa.String(200), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='online'),
        sa.Column('role', sa.String(20), nullable=True),
        sa.Column('replication_lag', sa.Integer(), nullable=True, default=0),
        sa.Column('region', sa.String(50), nullable=True),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # alert_rules
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('metric', sa.String(50), nullable=True),
        sa.Column('condition', sa.String(20), nullable=True),
        sa.Column('threshold', sa.Float(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('severity', sa.String(20), nullable=True, default='warning'),
        sa.Column('is_enabled', sa.Boolean(), nullable=True, default=True),
        sa.Column('notify_channels', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # system_alerts
    op.create_table(
        'system_alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rule_id', sa.Integer(), sa.ForeignKey('alert_rules.id'), nullable=True),
        sa.Column('rule_name', sa.String(100), nullable=True),
        sa.Column('severity', sa.String(20), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='active'),
        sa.Column('acknowledged_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # ==================== V1.9 算法交易表（2 张）====================

    # algo_orders
    op.create_table(
        'algo_orders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.String(100), nullable=False, unique=True),
        sa.Column('algo_type', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='pending'),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('market', sa.String(20), nullable=True, default='A'),
        sa.Column('side', sa.String(10), nullable=True),
        sa.Column('total_quantity', sa.Float(), nullable=False),
        sa.Column('filled_quantity', sa.Float(), nullable=True, default=0),
        sa.Column('avg_fill_price', sa.Float(), nullable=True, default=0),
        sa.Column('target_price', sa.Float(), nullable=True),
        sa.Column('params', sa.Text(), nullable=True),
        sa.Column('child_orders', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )

    # algo_executions
    op.create_table(
        'algo_executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('algo_order_id', sa.Integer(), sa.ForeignKey('algo_orders.id'), nullable=False),
        sa.Column('child_order_id', sa.String(100), nullable=True),
        sa.Column('symbol', sa.String(50), nullable=True),
        sa.Column('side', sa.String(10), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('fill_price', sa.Float(), nullable=True),
        sa.Column('fill_time', sa.DateTime(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('slippage', sa.Float(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='pending'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    # V1.9 算法交易表（逆序删除，先删依赖表）
    op.drop_table('algo_executions')
    op.drop_table('algo_orders')

    # V1.8 高可用表（先删依赖表 system_alerts）
    op.drop_table('system_alerts')
    op.drop_table('alert_rules')
    op.drop_table('cluster_nodes')
    op.drop_table('database_backups')

    # V1.7 多市场表
    op.drop_table('arbitrage_opportunities')
    op.drop_table('etf_info')
    op.drop_table('crypto_markets')
    op.drop_table('futures_contracts')

    # V1.6 社区表（先删依赖表）
    op.drop_table('private_messages')
    op.drop_table('post_likes')
    op.drop_table('post_comments')
    op.drop_table('trade_shares')
    op.drop_table('discussion_posts')
    op.drop_table('user_follows')
    op.drop_table('user_profiles')
