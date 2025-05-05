from pydantic import BaseModel, Field


# 通用的錯誤回應模型
class BaseResponseSchema(BaseModel):
    success: bool = Field(default=True)
    message: str