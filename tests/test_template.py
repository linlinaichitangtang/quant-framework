"""
v1.1 策略市场模块单元测试
"""
import json
import pytest
from datetime import datetime

from app import models, schemas
from app import crud


# ========== 模板 Schema 测试 ==========
class TestTemplateSchemas:
    def test_template_create(self):
        t = schemas.TemplateCreate(
            name="测试策略",
            description="一个测试策略模板",
            category=schemas.TemplateCategoryEnum.STOCK_SELECTION,
            config='{"type": "ml_picker", "params": {}}',
        )
        assert t.name == "测试策略"
        assert t.category == schemas.TemplateCategoryEnum.STOCK_SELECTION
        assert t.is_public is False

    def test_template_create_public(self):
        t = schemas.TemplateCreate(
            name="公开策略",
            is_public=True,
            config='{"type": "test"}',
        )
        assert t.is_public is True

    def test_template_create_validation(self):
        with pytest.raises(Exception):
            schemas.TemplateCreate(name="", config="{}")
        with pytest.raises(Exception):
            schemas.TemplateCreate(name="x", config="")

    def test_template_update_partial(self):
        u = schemas.TemplateUpdate(name="新名称")
        assert u.name == "新名称"
        assert u.description is None
        assert u.config is None

    def test_template_response(self):
        t = schemas.TemplateResponse(
            id=1, name="策略", category="stock_selection",
            author_name="admin", is_public=True,
            config='{"type": "test"}',
            install_count=10, rating_avg=4.5, rating_count=5,
            version=2, status="active",
            created_at=datetime.now(),
        )
        assert t.rating_avg == 4.5
        assert t.version == 2

    def test_market_template_response(self):
        m = schemas.MarketTemplateResponse(
            id=1, name="市场策略", category="signal",
            author_name="trader", install_count=100,
            rating_avg=4.8, rating_count=50,
            version=3, created_at=datetime.now(),
        )
        assert m.install_count == 100
        # 不含 config 字段
        assert not hasattr(m, 'config')

    def test_rate_request(self):
        r = schemas.TemplateRateRequest(score=5)
        assert r.score == 5

    def test_rate_request_validation(self):
        with pytest.raises(Exception):
            schemas.TemplateRateRequest(score=0)
        with pytest.raises(Exception):
            schemas.TemplateRateRequest(score=6)


# ========== 模板 CRUD 测试 ==========
class TestTemplateCRUD:
    def test_create_template(self, db_session):
        t = crud.create_template(
            db_session,
            name="CRUD测试",
            description="测试描述",
            category=models.TemplateCategory.STOCK_SELECTION,
            author_id=1,
            author_name="admin",
            config='{"type": "test"}',
        )
        assert t.id is not None
        assert t.name == "CRUD测试"
        assert t.version == 1
        assert t.status == "active"

    def test_create_template_creates_version(self, db_session):
        t = crud.create_template(
            db_session, name="版本测试",
            author_id=1, config='{"v": 1}',
        )
        versions = db_session.query(models.TemplateVersion).filter(
            models.TemplateVersion.template_id == t.id
        ).all()
        assert len(versions) == 1
        assert versions[0].version == 1
        assert versions[0].changelog == "初始版本"

    def test_get_template(self, db_session):
        t = crud.create_template(
            db_session, name="获取测试",
            author_id=1, config='{}',
        )
        found = crud.get_template(db_session, t.id)
        assert found is not None
        assert found.name == "获取测试"

    def test_get_template_not_found(self, db_session):
        found = crud.get_template(db_session, 99999)
        assert found is None

    def test_get_my_templates(self, db_session):
        crud.create_template(db_session, name="T1", author_id=1, config='{}')
        crud.create_template(db_session, name="T2", author_id=1, config='{}')
        crud.create_template(db_session, name="T3", author_id=2, config='{}')

        results = crud.get_my_templates(db_session, author_id=1)
        assert len(results) == 2

    def test_get_my_templates_with_category(self, db_session):
        crud.create_template(
            db_session, name="选股策略",
            author_id=1, category=models.TemplateCategory.STOCK_SELECTION, config='{}'
        )
        crud.create_template(
            db_session, name="风控策略",
            author_id=1, category=models.TemplateCategory.RISK_CONTROL, config='{}'
        )

        results = crud.get_my_templates(db_session, author_id=1, category=models.TemplateCategory.STOCK_SELECTION)
        assert len(results) == 1
        assert results[0].name == "选股策略"

    def test_update_template(self, db_session):
        t = crud.create_template(db_session, name="原始", author_id=1, config='{"v": 1}')
        updated = crud.update_template(db_session, t.id, name="更新后")
        assert updated.name == "更新后"

    def test_update_template_config_creates_new_version(self, db_session):
        t = crud.create_template(db_session, name="V测试", author_id=1, config='{"v": 1}')
        updated = crud.update_template(db_session, t.id, config='{"v": 2}')
        assert updated.version == 2

        versions = db_session.query(models.TemplateVersion).filter(
            models.TemplateVersion.template_id == t.id
        ).order_by(models.TemplateVersion.version).all()
        assert len(versions) == 2
        assert versions[0].config == '{"v": 1}'
        assert versions[1].config == '{"v": 2}'

    def test_delete_template_archives(self, db_session):
        t = crud.create_template(db_session, name="删除测试", author_id=1, config='{}')
        result = crud.delete_template(db_session, t.id)
        assert result.status == "archived"

        # 归档后 get_template 不应找到
        found = crud.get_template(db_session, t.id)
        assert found is None

    def test_market_templates_only_public(self, db_session):
        crud.create_template(
            db_session, name="公开", author_id=1, is_public=True, config='{}'
        )
        crud.create_template(
            db_session, name="私有", author_id=1, is_public=False, config='{}'
        )

        results = crud.get_market_templates(db_session)
        assert len(results) == 1
        assert results[0].name == "公开"

    def test_market_templates_search(self, db_session):
        crud.create_template(
            db_session, name="ML选股策略", author_id=1, is_public=True, config='{}'
        )
        crud.create_template(
            db_session, name="风控模型", author_id=1, is_public=True, config='{}'
        )

        results = crud.get_market_templates(db_session, search="ML")
        assert len(results) == 1
        assert results[0].name == "ML选股策略"

    def test_market_templates_sort_by_rating(self, db_session):
        crud.create_template(
            db_session, name="低分", author_id=1, is_public=True,
            config='{}', rating_avg=3.0, rating_count=10
        )
        crud.create_template(
            db_session, name="高分", author_id=1, is_public=True,
            config='{}', rating_avg=4.8, rating_count=50
        )

        results = crud.get_market_templates(db_session, sort_by="rating")
        assert results[0].name == "高分"

    def test_install_template_increments_count(self, db_session):
        t = crud.create_template(
            db_session, name="安装测试", author_id=1, is_public=True, config='{}'
        )
        assert t.install_count == 0

        crud.install_template(db_session, t.id)
        crud.install_template(db_session, t.id)
        crud.install_template(db_session, t.id)

        found = crud.get_template(db_session, t.id)
        assert found.install_count == 3

    def test_rate_template(self, db_session):
        t = crud.create_template(
            db_session, name="评分测试", author_id=1, is_public=True, config='{}'
        )
        assert t.rating_avg == 0
        assert t.rating_count == 0

        crud.rate_template(db_session, t.id, 5)
        crud.rate_template(db_session, t.id, 3)

        found = crud.get_template(db_session, t.id)
        assert found.rating_count == 2
        assert found.rating_avg == 4.0  # (5+3)/2

    def test_count_my_templates(self, db_session):
        crud.create_template(db_session, name="T1", author_id=1, config='{}')
        crud.create_template(db_session, name="T2", author_id=1, config='{}')
        crud.create_template(db_session, name="T3", author_id=2, config='{}')

        count = crud.count_my_templates(db_session, author_id=1)
        assert count == 2

    def test_count_market_templates(self, db_session):
        crud.create_template(db_session, name="公开1", author_id=1, is_public=True, config='{}')
        crud.create_template(db_session, name="公开2", author_id=1, is_public=True, config='{}')
        crud.create_template(db_session, name="私有", author_id=1, is_public=False, config='{}')

        count = crud.count_market_templates(db_session)
        assert count == 2
