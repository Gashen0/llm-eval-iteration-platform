"""Prompt 版本管理：基于 Git + YAML 的结构化版本控制。"""

from typing import Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import yaml
import hashlib
import time
import re

# TODO: 接入 GitPython 进行版本化操作
# import git


@dataclass
class PromptVersion:
    """单个 Prompt 版本的完整元数据。"""
    id: str  # 唯一标识，格式: {name}_v{major}.{minor}.{patch}
    name: str  # Prompt 名称（如 sql_generator）
    content: str  # Prompt 正文
    variables: list[str]  # 从 content 中提取的变量插槽列表
    version: str  # 语义化版本号
    parent_id: Optional[str]  # 父版本 ID，用于构建版本树
    created_at: str  # ISO 格式时间戳
    author: str = "default"
    change_motive: str = ""  # 本次修改的动机说明
    evaluation_id: Optional[str] = None  # 关联的评估实验 ID
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        """Prompt 内容的 SHA-256 哈希，用于快速比对。"""
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]

    @property
    def variable_slots(self) -> list[str]:
        """从 content 中自动提取 {{variable}} 格式的变量插槽。"""
        return re.findall(r"\{\{(\w+)\}\}", self.content)


class PromptVersionManager:
    """Prompt 版本管理器。

    核心设计思路：
    - 每个 Prompt 存储为独立的 YAML 文件，文件名包含版本号
    - 通过文件系统 + Git 实现版本控制，而非数据库
    - 支持版本树遍历、diff 比较、回滚操作
    - 变量插槽自动提取，避免人工维护变量列表

    选择文件系统而非数据库的原因：
    1. Git 天然提供审计日志（谁、何时、改了什么）
    2. 开发者可直接在 IDE 中编辑 YAML，无需额外 UI
    3. CI/CD 可直接加载特定版本的文件进行回归测试
    4. 回滚操作零成本（git checkout）

    Trade-off：
    - 大规模 Prompt 管理（>1000个）时查询效率不如数据库
    - 多人协作时 YAML 合并冲突需手动处理
    """

    def __init__(self, prompts_dir: str = "data/prompts") -> None:
        """初始化版本管理器。

        Args:
            prompts_dir: Prompt YAML 文件的存储目录
        """
        self.prompts_dir = Path(prompts_dir)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)

    def _version_to_filename(self, prompt_id: str) -> Path:
        """将 Prompt ID 映射为文件路径。

        命名规则: {name}_v{version}.yaml
        例: sql_generator_v1.2.0.yaml

        Args:
            prompt_id: Prompt 版本唯一标识

        Returns:
            对应的文件路径
        """
        return self.prompts_dir / f"{prompt_id}.yaml"

    def create_version(
        self,
        name: str,
        content: str,
        version: str = "1.0.0",
        parent_id: Optional[str] = None,
        author: str = "default",
        change_motive: str = "",
    ) -> PromptVersion:
        """创建新的 Prompt 版本。

        流程：
        1. 从 content 中自动提取变量插槽
        2. 生成唯一 ID
        3. 写入 YAML 文件
        4. TODO: 自动 git add + commit

        Args:
            name: Prompt 名称
            content: Prompt 正文
            version: 语义化版本号
            parent_id: 父版本 ID
            author: 作者
            change_motive: 修改动机

        Returns:
            创建的 PromptVersion 对象
        """
        prompt_id = f"{name}_v{version}"
        variables = re.findall(r"\{\{(\w+)\}\}", content)

        prompt = PromptVersion(
            id=prompt_id,
            name=name,
            content=content,
            variables=variables,
            version=version,
            parent_id=parent_id,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            author=author,
            change_motive=change_motive,
        )

        # 写入 YAML
        filepath = self._version_to_filename(prompt_id)
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(
                {
                    "id": prompt.id,
                    "name": prompt.name,
                    "content": prompt.content,
                    "variables": prompt.variables,
                    "version": prompt.version,
                    "parent_id": prompt.parent_id,
                    "created_at": prompt.created_at,
                    "author": prompt.author,
                    "change_motive": prompt.change_motive,
                    "evaluation_id": prompt.evaluation_id,
                    "metadata": prompt.metadata,
                    "content_hash": prompt.content_hash,
                },
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

        return prompt

    def get_version(self, prompt_id: str) -> Optional[PromptVersion]:
        """读取指定版本的 Prompt。

        Args:
            prompt_id: Prompt 版本唯一标识

        Returns:
            PromptVersion 对象，不存在则返回 None
        """
        filepath = self._version_to_filename(prompt_id)
        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return PromptVersion(
            id=data["id"],
            name=data["name"],
            content=data["content"],
            variables=data.get("variables", []),
            version=data["version"],
            parent_id=data.get("parent_id"),
            created_at=data["created_at"],
            author=data.get("author", "default"),
            change_motive=data.get("change_motive", ""),
            evaluation_id=data.get("evaluation_id"),
            metadata=data.get("metadata", {}),
        )

    def list_versions(self, name: Optional[str] = None) -> list[dict[str, Any]]:
        """列出所有 Prompt 版本。

        Args:
            name: 按 Prompt 名称过滤（可选）

        Returns:
            版本摘要列表
        """
        results: list[dict[str, Any]] = []
        for filepath in sorted(self.prompts_dir.glob("*.yaml")):
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if name and data.get("name") != name:
                continue
            results.append({
                "id": data["id"],
                "name": data["name"],
                "version": data["version"],
                "created_at": data["created_at"],
                "content_hash": data.get("content_hash", ""),
                "change_motive": data.get("change_motive", ""),
            })
        return results

    def diff_versions(
        self,
        prompt_id_a: str,
        prompt_id_b: str,
    ) -> dict[str, Any]:
        """对比两个版本的 Prompt 差异。

        返回结构化的 diff 结果，而非纯文本 diff，
        便于 Dashboard 可视化展示。

        Args:
            prompt_id_a: 版本 A 的 ID
            prompt_id_b: 版本 B 的 ID

        Returns:
            包含差异信息的字典
        """
        version_a = self.get_version(prompt_id_a)
        version_b = self.get_version(prompt_id_b)

        if not version_a or not version_b:
            return {"error": "版本不存在"}

        # 简单的文本行级 diff
        # TODO: 引入 difflib 进行更精细的对比
        lines_a = version_a.content.splitlines()
        lines_b = version_b.content.splitlines()

        return {
            "version_a": prompt_id_a,
            "version_b": prompt_id_b,
            "lines_a": len(lines_a),
            "lines_b": len(lines_b),
            "variables_a": version_a.variables,
            "variables_b": version_b.variables,
            "content_hash_a": version_a.content_hash,
            "content_hash_b": version_b.content_hash,
            "is_identical": version_a.content_hash == version_b.content_hash,
        }

    def get_version_tree(self, name: str) -> dict[str, Any]:
        """获取指定 Prompt 的版本演进树。

        通过 parent_id 递归构建，展示从初始版本到最新版本的完整路径。

        Args:
            name: Prompt 名称

        Returns:
            版本树的字典表示
        """
        versions = self.list_versions(name=name)
        if not versions:
            return {"name": name, "versions": []}

        # TODO: 构建完整的树结构（当前仅返回列表）
        return {
            "name": name,
            "versions": versions,
            "total": len(versions),
        }