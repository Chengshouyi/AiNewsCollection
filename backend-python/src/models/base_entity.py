"""基礎實體模組，用於定義實體驗證協議。

此模組提供基礎協議和實現，用於定義所有需要驗證功能的實體的通用接口。
"""

# Standard library imports
from typing import Protocol, List, runtime_checkable
import logging

# Local application imports


logger = logging.getLogger(__name__)  # 使用統一的 logger


@runtime_checkable
class ValidatableEntity(Protocol):
    def validate(self, is_update: bool = False) -> List[str]:
        """返回錯誤訊息列表，空列表表示驗證通過"""
        ...


class BaseEntity:
    def validate(self, is_update: bool = False) -> List[str]:
        """基本驗證邏輯"""
        errors = []
        # 實現通用驗證
        return errors
