""".env 文件读写服务。

提供保存和读取 .env 配置的功能，供 GUI 配置页使用。
"""

from __future__ import annotations

import os
from pathlib import Path

from src.observability.logger import get_logger

logger = get_logger()


class EnvService:
    """.env 文件读写服务。"""

    @staticmethod
    def save_env(env_data: dict[str, str]) -> None:
        """保存配置到 .env 文件。

        Args:
            env_data: 配置字典，key 为环境变量名，value 为值
        """
        env_path = Path(".env")

        # 读取现有 .env 文件（保留未更新的配置）
        existing = {}
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        existing[key.strip()] = value.strip()

        # 合并更新
        existing.update(env_data)

        # 写入文件
        with open(env_path, "w", encoding="utf-8") as f:
            for key, value in existing.items():
                f.write(f"{key}={value}\n")

        logger.info(f".env 配置已保存，共 {len(existing)} 项")

    @staticmethod
    def load_env() -> dict[str, str]:
        """读取 .env 文件。

        Returns:
            配置字典
        """
        env_path = Path(".env")
        result = {}

        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        result[key.strip()] = value.strip()

        return result

    @staticmethod
    def get_env_path() -> str:
        """获取 .env 文件路径。"""
        return str(Path(".env").resolve())
