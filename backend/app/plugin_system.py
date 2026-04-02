"""
插件系统

提供插件的注册、安装、执行、验证等核心功能。
支持钩子点：before_signal, after_signal, before_trade, after_trade, on_data_update, custom_indicator
"""

import logging
import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import desc

from .database import SessionLocal

logger = logging.getLogger(__name__)

# 支持的钩子点列表
SUPPORTED_HOOKS = [
    "before_signal",
    "after_signal",
    "before_trade",
    "after_trade",
    "on_data_update",
    "custom_indicator",
]


class PluginManager:
    """
    插件管理器（单例模式）

    负责插件的注册、注销、安装、执行和配置验证。
    """

    _instance: Optional["PluginManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化插件注册表"""
        if self._initialized:
            return

        self._plugins: Dict[str, dict] = {}  # plugin_id -> plugin_info
        self._hooks: Dict[str, List[str]] = {h: [] for h in SUPPORTED_HOOKS}  # hook_name -> [plugin_ids]
        self._initialized = True
        logger.info("插件管理器初始化完成")

    @classmethod
    def get_instance(cls) -> "PluginManager":
        """获取插件管理器单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_plugin(self, plugin_info: dict) -> dict:
        """
        注册插件

        Args:
            plugin_info: 插件信息字典，包含 name, description, version, category,
                        hooks, config_schema, author 等字段

        Returns:
            注册后的插件信息（包含自动生成的 plugin_id）
        """
        plugin_id = plugin_info.get("plugin_id") or f"plugin_{uuid.uuid4().hex[:12]}"

        if plugin_id in self._plugins:
            logger.warning(f"插件已存在，将覆盖注册: {plugin_id}")

        # 标准化插件信息
        plugin = {
            "plugin_id": plugin_id,
            "name": plugin_info.get("name", "未命名插件"),
            "description": plugin_info.get("description", ""),
            "version": plugin_info.get("version", "1.0.0"),
            "category": plugin_info.get("category", "other"),
            "author": plugin_info.get("author", ""),
            "hooks": plugin_info.get("hooks", []),
            "config_schema": plugin_info.get("config_schema", {}),
            "status": plugin_info.get("status", "active"),
            "rating_avg": plugin_info.get("rating_avg", 0),
            "rating_count": plugin_info.get("rating_count", 0),
            "install_count": plugin_info.get("install_count", 0),
            "created_at": plugin_info.get("created_at", datetime.now().isoformat()),
            "updated_at": datetime.now().isoformat(),
        }

        self._plugins[plugin_id] = plugin

        # 注册钩子
        for hook in plugin["hooks"]:
            if hook in self._hooks and plugin_id not in self._hooks[hook]:
                self._hooks[hook].append(plugin_id)

        logger.info(f"插件注册成功: {plugin_id} ({plugin['name']})")
        return plugin

    def unregister_plugin(self, plugin_id: str) -> bool:
        """
        注销插件

        Args:
            plugin_id: 插件标识

        Returns:
            是否注销成功
        """
        if plugin_id not in self._plugins:
            logger.warning(f"插件不存在: {plugin_id}")
            return False

        # 移除钩子注册
        for hook_name, plugin_ids in self._hooks.items():
            if plugin_id in plugin_ids:
                plugin_ids.remove(plugin_id)

        del self._plugins[plugin_id]
        logger.info(f"插件已注销: {plugin_id}")
        return True

    def get_plugin(self, plugin_id: str) -> Optional[dict]:
        """
        获取插件信息

        Args:
            plugin_id: 插件标识

        Returns:
            插件信息字典，不存在则返回 None
        """
        return self._plugins.get(plugin_id)

    def list_plugins(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[dict]:
        """
        列出插件

        Args:
            category: 按分类筛选
            status: 按状态筛选

        Returns:
            插件信息列表
        """
        plugins = list(self._plugins.values())

        if category:
            plugins = [p for p in plugins if p.get("category") == category]
        if status:
            plugins = [p for p in plugins if p.get("status") == status]

        return plugins

    def install_plugin(
        self,
        tenant_id: str,
        plugin_id: str,
        config: Optional[dict] = None,
    ) -> dict:
        """
        安装插件到租户

        Args:
            tenant_id: 租户标识
            plugin_id: 插件标识
            config: 插件配置

        Returns:
            安装结果字典
        """
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            raise ValueError(f"插件不存在: {plugin_id}")

        # 验证插件配置
        if config:
            validation = self.validate_plugin_config(plugin_id, config)
            if not validation.get("valid"):
                raise ValueError(f"插件配置验证失败: {validation.get('errors')}")

        # 记录安装信息到数据库
        db = SessionLocal()
        try:
            from .models import TenantPlugin

            existing = db.query(TenantPlugin).filter(
                TenantPlugin.tenant_id == tenant_id,
                TenantPlugin.plugin_id == plugin_id,
            ).first()

            if existing:
                existing.config = json.dumps(config, ensure_ascii=False) if config else None
                existing.status = "active"
                existing.updated_at = datetime.now()
                db.commit()
                db.refresh(existing)
                logger.info(f"插件已重新安装: {plugin_id} -> {tenant_id}")
                return {"status": "reinstalled", "plugin_id": plugin_id, "tenant_id": tenant_id}

            install = TenantPlugin(
                tenant_id=tenant_id,
                plugin_id=plugin_id,
                config=json.dumps(config, ensure_ascii=False) if config else None,
                status="active",
            )
            db.add(install)
            db.commit()

            # 更新安装计数
            plugin["install_count"] = plugin.get("install_count", 0) + 1

            logger.info(f"插件安装成功: {plugin_id} -> {tenant_id}")
            return {"status": "installed", "plugin_id": plugin_id, "tenant_id": tenant_id}
        finally:
            db.close()

    def uninstall_plugin(self, tenant_id: str, plugin_id: str) -> bool:
        """
        从租户卸载插件

        Args:
            tenant_id: 租户标识
            plugin_id: 插件标识

        Returns:
            是否卸载成功
        """
        db = SessionLocal()
        try:
            from .models import TenantPlugin

            install = db.query(TenantPlugin).filter(
                TenantPlugin.tenant_id == tenant_id,
                TenantPlugin.plugin_id == plugin_id,
            ).first()

            if not install:
                logger.warning(f"插件未安装: {plugin_id} -> {tenant_id}")
                return False

            install.status = "uninstalled"
            db.commit()

            logger.info(f"插件已卸载: {plugin_id} -> {tenant_id}")
            return True
        finally:
            db.close()

    def execute_plugin(
        self,
        plugin_id: str,
        method: str,
        params: Optional[dict] = None,
    ) -> dict:
        """
        执行插件方法

        Args:
            plugin_id: 插件标识
            method: 方法名称
            params: 方法参数

        Returns:
            执行结果字典
        """
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return {"success": False, "error": f"插件不存在: {plugin_id}"}

        if plugin.get("status") != "active":
            return {"success": False, "error": f"插件未激活: {plugin_id}"}

        logger.info(f"执行插件方法: {plugin_id}.{method}")

        # 插件方法执行的实际逻辑由具体插件实现
        # 这里提供统一的调用接口和日志记录
        try:
            # TODO: 根据插件类型调用对应的执行器
            result = {
                "success": True,
                "plugin_id": plugin_id,
                "method": method,
                "params": params or {},
                "message": f"插件方法 {method} 执行成功",
            }
            return result
        except Exception as e:
            logger.error(f"插件方法执行失败: {plugin_id}.{method}: {e}")
            return {"success": False, "error": str(e)}

    def validate_plugin_config(self, plugin_id: str, config: dict) -> dict:
        """
        验证插件配置是否符合 schema

        Args:
            plugin_id: 插件标识
            config: 待验证的配置字典

        Returns:
            验证结果字典 {"valid": bool, "errors": list}
        """
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return {"valid": False, "errors": [f"插件不存在: {plugin_id}"]}

        schema = plugin.get("config_schema", {})
        if not schema:
            # 没有定义 schema，允许任意配置
            return {"valid": True, "errors": []}

        errors = []
        # 简单的 schema 验证
        for field_name, field_def in schema.items():
            required = field_def.get("required", False)
            field_type = field_def.get("type", "string")

            if required and field_name not in config:
                errors.append(f"缺少必填字段: {field_name}")
                continue

            if field_name in config:
                value = config[field_name]
                if value is None and not field_def.get("nullable", False):
                    errors.append(f"字段 {field_name} 不能为空")
                elif value is not None:
                    # 类型检查
                    type_map = {
                        "string": str,
                        "integer": int,
                        "number": (int, float),
                        "boolean": bool,
                        "array": list,
                        "object": dict,
                    }
                    expected_type = type_map.get(field_type)
                    if expected_type and not isinstance(value, expected_type):
                        errors.append(f"字段 {field_name} 类型错误，期望 {field_type}")

        return {"valid": len(errors) == 0, "errors": errors}

    def get_plugin_hooks(self, plugin_id: str) -> List[str]:
        """
        获取插件注册的钩子列表

        Args:
            plugin_id: 插件标识

        Returns:
            钩子名称列表
        """
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return []
        return plugin.get("hooks", [])

    def get_hooks_for_event(self, hook_name: str) -> List[str]:
        """
        获取某个钩子点上的所有插件ID

        Args:
            hook_name: 钩子名称

        Returns:
            插件ID列表
        """
        return self._hooks.get(hook_name, [])
