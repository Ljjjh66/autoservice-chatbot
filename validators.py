"""
工具参数验证器 - 集中管理所有工具的验证逻辑
"""
from typing import Dict, Any, Optional, Tuple
from pydantic import ValidationError
from schemas import SCHEMA_REGISTRY


def validate_tool_args(function_name: str, function_args: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    验证工具参数

    Args:
        function_name: 工具名称
        function_args: 工具参数

    Returns:
        (是否成功, 错误信息, 验证后的参数)
    """
    # 查找对应的 Schema
    schema_class = SCHEMA_REGISTRY.get(function_name)

    # 如果没有对应的 Schema，直接通过（留作后续扩展）
    if schema_class is None:
        return True, None, function_args

    try:
        # 验证参数
        validated = schema_class(**function_args)
        # 转换为字典，确保有默认值的参数也能带上
        validated_args = validated.model_dump()
        return True, None, validated_args

    except ValidationError as e:
        # 处理验证错误，生成友好的错误提示
        error_details = []
        for error in e.errors():
            field = error.get("loc", [""])[0]
            msg = error.get("msg", "")
            error_details.append(f"{field}: {msg}")

        error_msg = "参数验证失败: " + "; ".join(error_details)
        return False, error_msg, None

    except Exception as e:
        # 其他异常
        return False, f"参数验证时发生错误: {str(e)}", None


def format_validation_error_for_llm(error_msg: str) -> str:
    """
    将验证错误格式化为 LLM 能理解的提示语

    Args:
        error_msg: 验证错误信息

    Returns:
        格式化后的错误提示
    """
    return (
        f"Lo siento, hubo un error con los parámetros: {error_msg}. "
        f"Por favor, verifica los datos e inténtalo nuevamente."
    )
