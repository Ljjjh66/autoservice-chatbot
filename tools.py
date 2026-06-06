"""
工具函数模块 - 包含订单物流查询和地址修改功能
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import random
import string

# ============================================================
# 模拟订单数据库 - 包含西班牙客户的订单数据
# ============================================================
ORDER_DATABASE: Dict[str, dict] = {
    "ESP12345": {
        "customer_name": "Carlos García",
        "address": "Calle Mayor 123, Madrid, Spain",
        "status": "运输中",
        "carrier": "DHL Express",
        "estimated_delivery": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
        "order_date": "2026-06-01",
        "cancelable": False,
        "refundable": False
    },
    "ESP12346": {
        "customer_name": "María López",
        "address": "Avinguda Diagonal 456, Barcelona, Spain",
        "status": "已发货",
        "carrier": "SEUR",
        "estimated_delivery": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "order_date": "2026-06-02",
        "cancelable": False,
        "refundable": False
    },
    "ESP12347": {
        "customer_name": "Juan Martínez",
        "address": "Calle Gran Vía 789, Valencia, Spain",
        "status": "已送达",
        "carrier": "Correos España",
        "estimated_delivery": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        "order_date": "2026-05-28",
        "cancelable": False,
        "refundable": True
    },
    "ESP12348": {
        "customer_name": "Ana Sánchez",
        "address": "Paseo de la Castellana 321, Madrid, Spain",
        "status": "未发货",
        "carrier": "Pending",
        "estimated_delivery": "TBD",
        "order_date": "2026-06-04",
        "cancelable": True,
        "refundable": False
    }
}


def query_order_status(order_id: str) -> dict:
    """
    查询订单物流状态

    Args:
        order_id: 订单号，格式如 "ESP12345"

    Returns:
        dict: 包含 success (bool) 和 message (str) 字段
              如果成功，message 中包含物流详情
    """
    # 验证订单ID格式（必须以 ESP 开头）
    if not order_id.startswith("ESP"):
        return {
            "success": False,
            "message": f"无效的订单号格式: {order_id}。订单号必须以 'ESP' 开头。"
        }

    # 在数据库中查找订单
    order = ORDER_DATABASE.get(order_id)

    if order is None:
        return {
            "success": False,
            "message": f"错误: 订单 {order_id} 不存在。"
        }

    # 构建成功响应，包含详细的物流信息
    response = {
        "success": True,
        "message": f"订单 {order_id} 查询成功",
        "data": {
            "order_id": order_id,
            "customer_name": order["customer_name"],
            "current_address": order["address"],
            "status": order["status"],
            "carrier": order["carrier"],
            "estimated_delivery": order["estimated_delivery"],
            "order_date": order["order_date"]
        }
    }

    return response


def modify_order_address(order_id: str, new_address: str) -> dict:
    """
    修改订单配送地址

    Args:
        order_id: 订单号，格式如 "ESP12345"
        new_address: 新的配送地址

    Returns:
        dict: 包含 success (bool) 和 message (str) 字段
              描述操作结果
    """
    # 验证订单ID格式
    if not order_id.startswith("ESP"):
        return {
            "success": False,
            "message": f"无效的订单号格式: {order_id}。订单号必须以 'ESP' 开头。"
        }

    # 查找订单是否存在
    order = ORDER_DATABASE.get(order_id)

    if order is None:
        return {
            "success": False,
            "message": f"错误: 订单 {order_id} 不存在，无法修改地址。"
        }

    # 检查订单状态 - 只有"未发货"的订单才能修改地址
    if order["status"] != "未发货":
        return {
            "success": False,
            "message": f"不能修改，订单已发货。当前状态: {order['status']}"
        }

    # 获取旧地址用于日志
    old_address = order["address"]

    # 更新数据库中的地址
    ORDER_DATABASE[order_id]["address"] = new_address

    # 返回成功信息
    return {
        "success": True,
        "message": f"订单 {order_id} 的地址已成功修改",
        "data": {
            "order_id": order_id,
            "old_address": old_address,
            "new_address": new_address
        }
    }


def cancel_order(order_id: str) -> dict:
    """
    取消订单

    Args:
        order_id: 订单号，格式如 "ESP12345"

    Returns:
        dict: 包含 success (bool) 和 message (str) 字段
              描述取消操作结果
    """
    # 验证订单ID格式
    if not order_id.startswith("ESP"):
        return {
            "success": False,
            "message": f"无效的订单号格式: {order_id}。订单号必须以 'ESP' 开头。"
        }

    # 查找订单是否存在
    order = ORDER_DATABASE.get(order_id)

    if order is None:
        return {
            "success": False,
            "message": f"错误: 订单 {order_id} 不存在，无法取消。"
        }

    # 检查订单是否可取消
    if not order.get("cancelable", False):
        current_status = order["status"]
        if current_status in ["已发货", "运输中"]:
            return {
                "success": False,
                "message": f"无法取消订单 {order_id}，因为订单已经发货，当前状态: {current_status}。请等待收货后申请退货。"
            }
        elif current_status == "已送达":
            return {
                "success": False,
                "message": f"无法取消订单 {order_id}，因为订单已送达。请申请退货退款。"
            }
        elif current_status == "已取消":
            return {
                "success": False,
                "message": f"订单 {order_id} 已经是取消状态。"
            }
        else:
            return {
                "success": False,
                "message": f"无法取消订单 {order_id}，当前状态: {current_status}。"
            }

    # 执行取消操作
    ORDER_DATABASE[order_id]["status"] = "已取消"
    ORDER_DATABASE[order_id]["cancelable"] = False
    ORDER_DATABASE[order_id]["refundable"] = True

    # 返回成功信息
    return {
        "success": True,
        "message": f"订单 {order_id} 已成功取消。",
        "data": {
            "order_id": order_id,
            "previous_status": "未发货",
            "new_status": "已取消",
            "refund_eligible": True
        }
    }


def request_refund(order_id: str, reason: str = "") -> dict:
    """
    申请退款

    Args:
        order_id: 订单号，格式如 "ESP12345"
        reason: 退款原因（可选）

    Returns:
        dict: 包含 success (bool) 和 message (str) 字段
              包含退款编号和申请详情
    """
    # 验证订单ID格式
    if not order_id.startswith("ESP"):
        return {
            "success": False,
            "message": f"无效的订单号格式: {order_id}。订单号必须以 'ESP' 开头。"
        }

    # 查找订单是否存在
    order = ORDER_DATABASE.get(order_id)

    if order is None:
        return {
            "success": False,
            "message": f"错误: 订单 {order_id} 不存在，无法申请退款。"
        }

    # 检查订单是否可退款
    if not order.get("refundable", False):
        current_status = order["status"]
        if current_status == "已送达":
            # 已送达但还未标记为可退款，需要人工审核
            return {
                "success": False,
                "message": f"订单 {order_id} 已送达，如需退款请联系客服申请人工审核。"
            }
        elif current_status in ["已发货", "运输中"]:
            return {
                "success": False,
                "message": f"无法申请退款，订单 {order_id} 正在运输中（{current_status}）。请等待送达后再申请。"
            }
        elif current_status == "未发货":
            return {
                "success": False,
                "message": f"订单 {order_id} 尚未发货，请先取消订单。"
            }
        elif current_status == "已退款":
            return {
                "success": False,
                "message": f"订单 {order_id} 已经申请过退款。"
            }
        else:
            return {
                "success": False,
                "message": f"无法申请退款，订单 {order_id} 状态异常: {current_status}。"
            }

    # 生成退款编号
    refund_number = "RMA-" + "".join(random.choices(string.digits, k=8))

    # 更新订单状态
    ORDER_DATABASE[order_id]["status"] = "已退款"
    ORDER_DATABASE[order_id]["refundable"] = False
    ORDER_DATABASE[order_id]["refund_reason"] = reason
    ORDER_DATABASE[order_id]["refund_number"] = refund_number

    # 返回成功信息
    return {
        "success": True,
        "message": f"退款申请成功！退款编号: {refund_number}",
        "data": {
            "order_id": order_id,
            "refund_number": refund_number,
            "reason": reason if reason else "未提供",
            "processing_time": "7个工作日内",
            "refund_method": "原支付方式"
        }
    }


def estimate_shipping(country: str, weight: float) -> dict:
    """
    估算运费

    Args:
        country: 目的地国家（西班牙语或英语）
        weight: 包裹重量（公斤）

    Returns:
        dict: 包含 success (bool) 和 message (str) 字段
              包含运费、预计天数等信息
    """
    # 运费标准字典（国家名支持多语言）
    SHIPPING_RATES = {
        # 国家名: (每公斤运费EUR, 基础运费EUR, 预计天数)
        "españa": (8.0, 5.0, "3-5"),
        "spain": (8.0, 5.0, "3-5"),
        "francia": (12.0, 8.0, "5-7"),
        "france": (12.0, 8.0, "5-7"),
        "alemania": (10.0, 7.0, "5-7"),
        "germany": (10.0, 7.0, "5-7"),
        "italia": (11.0, 7.0, "5-7"),
        "italy": (11.0, 7.0, "5-7"),
        "portugal": (9.0, 5.0, "2-4"),
        "reinounido": (14.0, 10.0, "7-10"),
        "united kingdom": (14.0, 10.0, "7-10"),
        "uk": (14.0, 10.0, "7-10"),
        "estados unidos": (18.0, 15.0, "10-15"),
        "united states": (18.0, 15.0, "10-15"),
        "usa": (18.0, 15.0, "10-15"),
        "méxico": (16.0, 12.0, "8-12"),
        "mexico": (16.0, 12.0, "8-12"),
        "china": (20.0, 18.0, "15-20"),
        "china": (20.0, 18.0, "15-20"),
        "brasil": (17.0, 14.0, "10-15"),
        "brazil": (17.0, 14.0, "10-15"),
        "argentina": (19.0, 16.0, "12-18"),
        "argentina": (19.0, 16.0, "12-18")
    }

    # 标准化国家名称
    country_normalized = country.lower().strip()

    # 查找国家
    if country_normalized not in SHIPPING_RATES:
        # 返回可用国家列表
        available_countries = sorted(set(SHIPPING_RATES.keys()))
        return {
            "success": False,
            "message": f"暂不支持向 {country} 配送。可配送国家包括: {', '.join(available_countries)}"
        }

    # 计算运费
    per_kg_rate, base_rate, delivery_days = SHIPPING_RATES[country_normalized]
    shipping_cost = base_rate + (per_kg_rate * weight)

    # 免费送货阈值（西班牙境内满50欧元）
    free_shipping_threshold = 50.0
    is_domestic = country_normalized in ["españa", "spain"]
    order_amount = 100.0  # 假设订单金额，需要根据实际情况调整

    if is_domestic and order_amount >= free_shipping_threshold:
        final_shipping = 0.0
        free_shipping_note = "订单满50欧，享受免费送货！"
    else:
        final_shipping = round(shipping_cost, 2)
        free_shipping_note = f"西班牙境内订单满50欧可享受免费送货，当前需支付 {final_shipping} EUR"

    # 返回结果
    return {
        "success": True,
        "message": f"运费估算成功",
        "data": {
            "destination": country,
            "weight_kg": weight,
            "shipping_cost_eur": final_shipping,
            "currency": "EUR",
            "estimated_delivery": f"{delivery_days} días laborables",
            "free_shipping_note": free_shipping_note,
            "carrier_options": ["DHL Express", "SEUR", "Correos Express"]
        }
    }


# ============================================================
# 测试代码 - 当直接运行 python tools.py 时执行
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("工具函数测试")
    print("=" * 60)

    # 测试1: 查询订单状态
    print("\n【测试1】查询订单状态")
    print("-" * 40)

    test_order_ids = ["ESP12345", "ESP12346", "ESP12347", "ESP12349"]

    for order_id in test_order_ids:
        result = query_order_status(order_id)
        print(f"\n查询订单 {order_id}:")
        print(f"  Success: {result['success']}")
        print(f"  Message: {result['message']}")
        if result['success'] and 'data' in result:
            print(f"  物流状态: {result['data']['status']}")
            print(f"  承运人: {result['data']['carrier']}")
            print(f"  预计送达: {result['data']['estimated_delivery']}")

    # 测试2: 修改订单地址
    print("\n" + "=" * 60)
    print("【测试2】修改订单地址")
    print("-" * 40)

    # 测试未发货订单 - 应该成功
    print("\n尝试修改未发货订单 ESP12348 的地址:")
    result = modify_order_address("ESP12348", "Calle Nueva 999, Sevilla, Spain")
    print(f"  Success: {result['success']}")
    print(f"  Message: {result['message']}")
    if result['success']:
        print(f"  新地址: {result['data']['new_address']}")

    # 再次尝试修改已发货订单 - 应该失败
    print("\n尝试修改已发货订单 ESP12345 的地址:")
    result = modify_order_address("ESP12345", "Calle Cambiada 111, Bilbao, Spain")
    print(f"  Success: {result['success']}")
    print(f"  Message: {result['message']}")

    # 测试不存在的订单
    print("\n尝试修改不存在的订单 ESP99999 的地址:")
    result = modify_order_address("ESP99999", "Calle Test 222, Madrid, Spain")
    print(f"  Success: {result['success']}")
    print(f"  Message: {result['message']}")

    # 测试无效的订单号格式
    print("\n尝试使用无效格式的订单号:")
    result = modify_order_address("FRA12345", "Calle Test 333, Paris, France")
    print(f"  Success: {result['success']}")
    print(f"  Message: {result['message']}")

    # 测试3: 取消订单
    print("\n" + "=" * 60)
    print("【测试3】取消订单")
    print("-" * 40)

    # 测试取消未发货订单
    print("\n尝试取消未发货订单 ESP12348:")
    result = cancel_order("ESP12348")
    print(f"  Success: {result['success']}")
    print(f"  Message: {result['message']}")

    # 测试取消已发货订单 - 应该失败
    print("\n尝试取消已发货订单 ESP12346:")
    result = cancel_order("ESP12346")
    print(f"  Success: {result['success']}")
    print(f"  Message: {result['message']}")

    # 测试取消已送达订单 - 应该失败
    print("\n尝试取消已送达订单 ESP12347:")
    result = cancel_order("ESP12347")
    print(f"  Success: {result['success']}")
    print(f"  Message: {result['message']}")

    # 测试4: 申请退款
    print("\n" + "=" * 60)
    print("【测试4】申请退款")
    print("-" * 40)

    # 重置ESP12348状态用于测试
    ORDER_DATABASE["ESP12348"]["status"] = "已送达"
    ORDER_DATABASE["ESP12348"]["refundable"] = True

    print("\n尝试为已送达订单 ESP12347 申请退款:")
    result = request_refund("ESP12347", "Producto defectuoso")
    print(f"  Success: {result['success']}")
    print(f"  Message: {result['message']}")
    if result['success'] and 'data' in result:
        print(f"  退款编号: {result['data']['refund_number']}")
        print(f"  退款原因: {result['data']['reason']}")

    # 测试对未发货订单申请退款 - 应该失败
    print("\n尝试为未发货订单 ESP12348 申请退款:")
    ORDER_DATABASE["ESP12348"]["status"] = "未发货"
    ORDER_DATABASE["ESP12348"]["refundable"] = False
    result = request_refund("ESP12348", "Ya no lo necesito")
    print(f"  Success: {result['success']}")
    print(f"  Message: {result['message']}")

    # 测试5: 估算运费
    print("\n" + "=" * 60)
    print("【测试5】估算运费")
    print("-" * 40)

    test_countries = ["España", "Francia", "Alemania", "Italia", "Reino Unido", "Estados Unidos", "Japón"]

    for country in test_countries:
        result = estimate_shipping(country, 2.5)
        print(f"\n运费到 {country} (2.5kg):")
        print(f"  Success: {result['success']}")
        if result['success']:
            print(f"  运费: {result['data']['shipping_cost_eur']} {result['data']['currency']}")
            print(f"  预计: {result['data']['estimated_delivery']}")
        else:
            print(f"  Message: {result['message']}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


# ============================================================
# 函数别名 - 用于 Agent 调用
# ============================================================

# 提供别名以满足 Agent 要求的函数名
def query_order_logistics(order_id: str) -> dict:
    """查询订单物流状态（别名函数，用于 Agent 调用）"""
    return query_order_status(order_id)


def update_order_address(order_id: str, new_address: str) -> dict:
    """修改订单配送地址（别名函数，用于 Agent 调用）"""
    return modify_order_address(order_id, new_address)
