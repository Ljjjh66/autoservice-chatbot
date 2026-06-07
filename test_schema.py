"""
Schema 验证完整测试套件
包含所有工具的完整测试用例
"""
from validators import validate_tool_args


def test_query_order_logistics():
    """查询订单物流 - 完整测试"""
    print("=" * 60)
    print("测试 1: query_order_logistics")
    print("=" * 60)
    
    # ✅ 正确格式
    ok, error, args = validate_tool_args("query_order_logistics", {"order_id": "ESP12345"})
    assert ok, f"正确格式应该通过: {error}"
    print("  ✅ 正确格式: ESP12345")
    
    # ✅ 带空格的订单号（应该自动trim）
    ok, error, args = validate_tool_args("query_order_logistics", {"order_id": "  ESP12345  "})
    assert ok, f"带空格应该通过: {error}"
    print("  ✅ 带空格: '  ESP12345  '")
    
    # ❌ 空订单号
    ok, error, args = validate_tool_args("query_order_logistics", {"order_id": ""})
    assert not ok, "空订单号应该失败"
    assert "不能为空" in error
    print("  ❌ 空订单号: 正确拒绝")
    
    # ❌ 纯数字
    ok, error, args = validate_tool_args("query_order_logistics", {"order_id": "12345"})
    assert not ok, "纯数字应该失败"
    assert "必须以 ESP 开头" in error
    print("  ❌ 纯数字: 正确拒绝")
    
    # ❌ 其他字母开头
    ok, error, args = validate_tool_args("query_order_logistics", {"order_id": "ABC123"})
    assert not ok, "ABC开头应该失败"
    assert "必须以 ESP 开头" in error
    print("  ❌ ABC开头: 正确拒绝")
    
    # ❌ 太短的订单号
    ok, error, args = validate_tool_args("query_order_logistics", {"order_id": "ES"})
    assert not ok, f"太短应该失败，实际: {error}"
    print(f"  ❌ 太短: 正确拒绝，错误: {error}")
    
    # ❌ 只有ESP（后面没有数字）
    ok, error, args = validate_tool_args("query_order_logistics", {"order_id": "ESP"})
    assert not ok, f"只有ESP应该失败，实际: {error}"
    print(f"  ❌ 只有ESP: 正确拒绝，错误: {error}")
    
    print("  🎉 test_query_order_logistics 通过！\n")


def test_update_order_address():
    """修改地址 - 完整测试"""
    print("=" * 60)
    print("测试 2: update_order_address")
    print("=" * 60)
    
    # ✅ 正确输入
    ok, error, args = validate_tool_args("update_order_address", 
                                        {"order_id": "ESP12345", "new_address": "Calle Test 123"})
    assert ok, f"正确输入应该通过: {error}"
    assert args["new_address"] == "Calle Test 123"
    print("  ✅ 正确输入")
    
    # ✅ 带空格的地址（应该自动trim）
    ok, error, args = validate_tool_args("update_order_address",
                                        {"order_id": "ESP12345", "new_address": "  Calle Test 123  "})
    assert ok, f"带空格应该通过: {error}"
    print("  ✅ 带空格地址")
    
    # ❌ 空订单号
    ok, error, args = validate_tool_args("update_order_address", 
                                        {"order_id": "", "new_address": "Calle Test"})
    assert not ok, "空订单号应该失败"
    print("  ❌ 空订单号: 正确拒绝")
    
    # ❌ 格式不对的订单号
    ok, error, args = validate_tool_args("update_order_address", 
                                        {"order_id": "ABC123", "new_address": "Calle Test"})
    assert not ok, "格式不对应该失败"
    print("  ❌ 格式不对订单号: 正确拒绝")
    
    # ❌ 空地址
    ok, error, args = validate_tool_args("update_order_address", 
                                        {"order_id": "ESP12345", "new_address": ""})
    assert not ok, "空地址应该失败"
    assert "地址不能为空" in error
    print("  ❌ 空地址: 正确拒绝")
    
    # ❌ 地址太长（超过200字符）
    long_address = "Calle " + "a" * 200 + ", Madrid"
    ok, error, args = validate_tool_args("update_order_address", 
                                        {"order_id": "ESP12345", "new_address": long_address})
    assert not ok, "太长地址应该失败"
    assert "太长" in error
    print("  ❌ 地址太长: 正确拒绝")
    
    print("  🎉 test_update_order_address 通过！\n")


def test_cancel_order():
    """取消订单 - 完整测试"""
    print("=" * 60)
    print("测试 3: cancel_order")
    print("=" * 60)
    
    # ✅ 正确订单号
    ok, error, args = validate_tool_args("cancel_order", {"order_id": "ESP12345"})
    assert ok, f"正确订单号应该通过: {error}"
    print("  ✅ 正确订单号")
    
    # ❌ 空订单号
    ok, error, args = validate_tool_args("cancel_order", {"order_id": ""})
    assert not ok, "空订单号应该失败"
    print("  ❌ 空订单号: 正确拒绝")
    
    # ❌ 格式不对
    ok, error, args = validate_tool_args("cancel_order", {"order_id": "12345"})
    assert not ok, "格式不对应该失败"
    print("  ❌ 格式不对: 正确拒绝")
    
    print("  🎉 test_cancel_order 通过！\n")


def test_request_refund():
    """申请退款 - 完整测试"""
    print("=" * 60)
    print("测试 4: request_refund")
    print("=" * 60)
    
    # ✅ 正确输入（reason为空，使用默认值）
    ok, error, args = validate_tool_args("request_refund", 
                                        {"order_id": "ESP12345", "reason": ""})
    assert ok, f"空原因应该通过: {error}"
    assert args["reason"] == ""
    print("  ✅ 空原因（默认值）")
    
    # ✅ 正确输入（reason有内容）
    ok, error, args = validate_tool_args("request_refund", 
                                        {"order_id": "ESP12345", "reason": "商品损坏"})
    assert ok, f"正常原因应该通过: {error}"
    assert args["reason"] == "商品损坏"
    print("  ✅ 正常原因")
    
    # ✅ 正确输入（reason为None，会转为空字符串）
    ok, error, args = validate_tool_args("request_refund", 
                                        {"order_id": "ESP12345", "reason": None})
    assert ok, f"None原因应该通过: {error}"
    print("  ✅ None原因")
    
    # ❌ 空订单号
    ok, error, args = validate_tool_args("request_refund", 
                                        {"order_id": "", "reason": "测试"})
    assert not ok, "空订单号应该失败"
    print("  ❌ 空订单号: 正确拒绝")
    
    # ❌ 格式不对的订单号
    ok, error, args = validate_tool_args("request_refund", 
                                        {"order_id": "ABC123", "reason": "测试"})
    assert not ok, "格式不对应该失败"
    print("  ❌ 格式不对订单号: 正确拒绝")
    
    # ❌ 原因太长（超过500字符）
    long_reason = "原因：" + "a" * 500
    ok, error, args = validate_tool_args("request_refund", 
                                        {"order_id": "ESP12345", "reason": long_reason})
    assert not ok, "太长原因应该失败"
    assert "太长" in error
    print("  ❌ 原因太长: 正确拒绝")
    
    print("  🎉 test_request_refund 通过！\n")


def test_estimate_shipping():
    """运费估算 - 完整测试"""
    print("=" * 60)
    print("测试 5: estimate_shipping")
    print("=" * 60)
    
    # ✅ 正常输入
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": "España", "weight": 2.5})
    assert ok, f"正常输入应该通过: {error}"
    assert args["weight"] == 2.5
    print("  ✅ 正常输入: España, 2.5kg")
    
    # ✅ 整数重量
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": "España", "weight": 5})
    assert ok, f"整数重量应该通过: {error}"
    print("  ✅ 整数重量: 5kg")
    
    # ✅ 小数重量
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": "España", "weight": 0.5})
    assert ok, f"小数重量应该通过: {error}"
    print("  ✅ 小数重量: 0.5kg")
    
    # ✅ 刚好100kg（边界值）
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": "España", "weight": 100})
    assert ok, f"刚好100kg应该通过: {error}"
    print("  ✅ 边界值: 100kg")
    
    # ❌ 负重量
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": "España", "weight": -1})
    assert not ok, "负重量应该失败"
    assert "必须大于0" in error
    print("  ❌ 负重量: 正确拒绝")
    
    # ❌ 零重量
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": "España", "weight": 0})
    assert not ok, "零重量应该失败"
    print("  ❌ 零重量: 正确拒绝")
    
    # ❌ 超过100kg
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": "España", "weight": 101})
    assert not ok, "超过100kg应该失败"
    assert "超过100" in error
    print("  ❌ 超过100kg: 正确拒绝")
    
    # ❌ 空国家
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": "", "weight": 2.5})
    assert not ok, "空国家应该失败"
    print("  ❌ 空国家: 正确拒绝")
    
    # ❌ 国家名称太长
    long_country = "a" * 60
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": long_country, "weight": 2.5})
    assert not ok, "国家太长应该失败"
    print("  ❌ 国家太长: 正确拒绝")
    
    print("  🎉 test_estimate_shipping 通过！\n")


def test_search_no_schema():
    """search工具不需要Schema验证"""
    print("=" * 60)
    print("测试 6: search (无Schema验证)")
    print("=" * 60)
    
    # search工具不需要验证，应该直接通过
    ok, error, args = validate_tool_args("search", {"query": "测试查询"})
    assert ok, f"search应该直接通过: {error}"
    print("  ✅ search工具直接通过验证")
    
    print("  🎉 test_search_no_schema 通过！\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 开始运行完整测试套件")
    print("=" * 60 + "\n")
    
    test_query_order_logistics()
    test_update_order_address()
    test_cancel_order()
    test_request_refund()
    test_estimate_shipping()
    test_search_no_schema()
    
    print("=" * 60)
    print("🎉 所有测试通过！")
    print("=" * 60)
    print("\n测试覆盖率：")
    print("  - query_order_logistics: 7个测试用例")
    print("  - update_order_address: 6个测试用例")
    print("  - cancel_order: 3个测试用例")
    print("  - request_refund: 6个测试用例")
    print("  - estimate_shipping: 9个测试用例")
    print("  - search: 1个测试用例")
    print("  总计: 32个测试用例")
