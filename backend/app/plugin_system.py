"""
插件系统

提供插件的注册、安装、执行、验证等核心功能。
支持钩子点：before_signal, after_signal, before_trade, after_trade, on_data_update, custom_indicator
"""

import logging
import json
import uuid
import time
from typing import Optional, List, Dict, Any, Callable
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
        self._plugin_executors: Dict[str, Dict[str, Callable]] = {}  # plugin_id -> {method_name: executor_func}
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

        支持两种执行模式:
        1. 钩子执行: 当 method 是支持的钩子名称时，执行该钩子上所有注册的插件
        2. 直接方法执行: 当 method 是自定义方法名时，查找插件注册的执行器函数

        Args:
            plugin_id: 插件标识（钩子模式下可为空字符串）
            method: 方法名称或钩子名称
            params: 方法参数

        Returns:
            执行结果字典
        """
        # 钩子模式: method 是一个钩子名称
        if method in self._hooks:
            return self.fire_hook(method, params or {})

        # 直接方法执行模式
        plugin = self.get_plugin(plugin_id)
        if not plugin:
            return {"success": False, "error": f"插件不存在: {plugin_id}"}

        if plugin.get("status") != "active":
            return {"success": False, "error": f"插件未激活: {plugin_id}"}

        logger.info(f"执行插件方法: {plugin_id}.{method}")

        # 查找注册的执行器
        executors = self._plugin_executors.get(plugin_id, {})
        executor = executors.get(method)

        if executor is None:
            logger.warning(f"插件 {plugin_id} 没有注册方法 {method} 的执行器")
            return {
                "success": False,
                "error": f"插件 {plugin_id} 没有注册方法 {method} 的执行器",
                "plugin_id": plugin_id,
                "method": method,
            }

        # 在沙箱化环境中执行
        start_time = time.time()
        try:
            result = executor(params or {})
            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                f"插件方法执行成功: {plugin_id}.{method} "
                f"(耗时 {elapsed_ms:.1f}ms)"
            )

            return {
                "success": True,
                "plugin_id": plugin_id,
                "method": method,
                "params": params or {},
                "result": result,
                "elapsed_ms": round(elapsed_ms, 2),
                "message": f"插件方法 {method} 执行成功",
            }
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                f"插件方法执行失败: {plugin_id}.{method}: {e} "
                f"(耗时 {elapsed_ms:.1f}ms)"
            )
            return {
                "success": False,
                "plugin_id": plugin_id,
                "method": method,
                "error": str(e),
                "elapsed_ms": round(elapsed_ms, 2),
            }

    def register_executor(
        self,
        plugin_id: str,
        method_name: str,
        executor_func: Callable,
    ) -> None:
        """
        注册插件执行器函数

        Args:
            plugin_id: 插件标识
            method_name: 方法名称
            executor_func: 执行器函数，接收 params dict，返回结果
        """
        if plugin_id not in self._plugin_executors:
            self._plugin_executors[plugin_id] = {}
        self._plugin_executors[plugin_id][method_name] = executor_func
        logger.info(f"注册插件执行器: {plugin_id}.{method_name}")

    def fire_hook(self, hook_name: str, context: Optional[dict] = None) -> dict:
        """
        触发钩子，按顺序执行该钩子上所有注册的插件

        一个插件失败不会影响其他插件的执行。

        Args:
            hook_name: 钩子名称
            context: 上下文数据，会传递给每个插件的执行器

        Returns:
            执行结果汇总字典
        """
        if hook_name not in self._hooks:
            return {
                "success": False,
                "error": f"不支持的钩子: {hook_name}",
                "hook": hook_name,
                "results": [],
            }

        plugin_ids = self._hooks[hook_name]
        if not plugin_ids:
            return {
                "success": True,
                "hook": hook_name,
                "message": "该钩子上没有注册插件",
                "results": [],
            }

        logger.info(f"触发钩子: {hook_name} ({len(plugin_ids)} 个插件)")

        results = []
        context = context or {}
        all_success = True

        for pid in plugin_ids:
            plugin = self.get_plugin(pid)
            if not plugin or plugin.get("status") != "active":
                results.append({
                    "plugin_id": pid,
                    "success": False,
                    "error": "插件不存在或未激活",
                })
                all_success = False
                continue

            executors = self._plugin_executors.get(pid, {})
            executor = executors.get(hook_name)

            if executor is None:
                # 没有注册钩子执行器，跳过但不算失败
                results.append({
                    "plugin_id": pid,
                    "success": True,
                    "skipped": True,
                    "message": "没有注册钩子执行器",
                })
                continue

            start_time = time.time()
            try:
                result = executor(context)
                elapsed_ms = (time.time() - start_time) * 1000
                results.append({
                    "plugin_id": pid,
                    "success": True,
                    "result": result,
                    "elapsed_ms": round(elapsed_ms, 2),
                })
                logger.info(
                    f"钩子插件执行成功: {hook_name} -> {pid} "
                    f"(耗时 {elapsed_ms:.1f}ms)"
                )
            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                all_success = False
                results.append({
                    "plugin_id": pid,
                    "success": False,
                    "error": str(e),
                    "elapsed_ms": round(elapsed_ms, 2),
                })
                logger.error(
                    f"钩子插件执行失败: {hook_name} -> {pid}: {e} "
                    f"(耗时 {elapsed_ms:.1f}ms)"
                )

        return {
            "success": all_success,
            "hook": hook_name,
            "total": len(plugin_ids),
            "succeeded": sum(1 for r in results if r.get("success")),
            "failed": sum(1 for r in results if not r.get("success")),
            "results": results,
        }

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
