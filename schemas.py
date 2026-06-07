"""
工具输入 Schema 定义 - 集中管理所有工具的输入规范
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class QueryOrderLogisticsSchema(BaseModel):
    """查询订单物流状态的输入 Schema"""
    order_id: str = Field(..., description="订单号，格式如 ESP12345")

    @field_validator("order_id")
    def validate_order_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("订单号不能为空")
        if not v.startswith("ESP"):
            raise ValueError("订单号格式不正确，必须以 ESP 开头")
        if len(v) < 4:  # ESP + 至少1个数字
            raise ValueError("订单号长度不正确")
        return v


class UpdateOrderAddressSchema(BaseModel):
    """修改订单地址的输入 Schema"""
    order_id: str = Field(..., description="订单号，格式如 ESP12345")
    new_address: str = Field(..., description="新的配送地址")

    @field_validator("order_id")
    def validate_order_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("订单号不能为空")
        if not v.startswith("ESP"):
            raise ValueError("订单号格式不正确，必须以 ESP 开头")
        return v

    @field_validator("new_address")
    def validate_address(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("地址不能为空")
        if len(v) > 200:
            raise ValueError("地址太长了，最多200个字符")
        return v


class CancelOrderSchema(BaseModel):
    """取消订单的输入 Schema"""
    order_id: str = Field(..., description="订单号，格式如 ESP12345")

    @field_validator("order_id")
    def validate_order_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("订单号不能为空")
        if not v.startswith("ESP"):
            raise ValueError("订单号格式不正确，必须以 ESP 开头")
        return v


class RequestRefundSchema(BaseModel):
    """申请退款的输入 Schema"""
    order_id: str = Field(..., description="订单号，格式如 ESP12345")
    reason: Optional[str] = Field(default="", description="退款原因（可选）")

    @field_validator("order_id")
    def validate_order_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("订单号不能为空")
        if not v.startswith("ESP"):
            raise ValueError("订单号格式不正确，必须以 ESP 开头")
        return v

    @field_validator("reason")
    def validate_reason(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return ""
        v = v.strip()
        if len(v) > 500:
            raise ValueError("退款原因太长了，最多500个字符")
        return v


class EstimateShippingSchema(BaseModel):
    """估算运费的输入 Schema"""
    country: str = Field(..., description="目的地国家（西班牙语或英语）")
    weight: float = Field(..., description="包裹重量（公斤）")

    @field_validator("country")
    def validate_country(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("国家不能为空")
        if len(v) > 50:
            raise ValueError("国家名称太长了")
        return v

    @field_validator("weight")
    def validate_weight(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("重量必须大于0公斤")
        if v > 100:
            raise ValueError("重量不能超过100公斤")
        return v


# Schema 注册表
SCHEMA_REGISTRY = {
    "query_order_logistics": QueryOrderLogisticsSchema,
    "update_order_address": UpdateOrderAddressSchema,
    "cancel_order": CancelOrderSchema,
    "request_refund": RequestRefundSchema,
    "estimate_shipping": EstimateShippingSchema,
    "search": None,  # search 工具暂时不需要复杂验证
}
