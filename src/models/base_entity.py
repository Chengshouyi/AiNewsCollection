from typing import Protocol, List, runtime_checkable

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