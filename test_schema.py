"""
测试 Schema 验证功能
"""
from validators import validate_tool_args

def test_query_order_logistics():
    """测试查询订单物流"""
    print("=" * 60)
    print("测试 1: 查询订单物流")
    print("=" * 60)
    
    # 测试正确的订单号
    ok, error, args = validate_tool_args("query_order_logistics", {"order_id": "ESP12345"})
    print(f"  正确订单号: {ok}, {error}, {args}")
    assert ok, "应该通过验证"
    
    # 测试空订单号
    ok, error, args = validate_tool_args("query_order_logistics", {"order_id": ""})
    print(f"  空订单号: {ok}, {error}")
    assert not ok, "应该失败验证"
    
    # 测试格式不对的订单号
    ok, error, args = validate_tool_args("query_order_logistics", {"order_id": "ABC123"})
    print(f"  格式不对: {ok}, {error}")
    assert not ok, "应该失败验证"
    
    print("  ✅ 通过")


def test_update_order_address():
    """测试修改地址"""
    print("\n" + "=" * 60)
    print("测试 2: 修改地址")
    print("=" * 60)
    
    # 测试正确输入
    ok, error, args = validate_tool_args("update_order_address", 
                                        {"order_id": "ESP12345", "new_address": "Calle Test 123"})
    print(f"  正确输入: {ok}, {error}, {args}")
    assert ok, "应该通过验证"
    
    # 测试空地址
    ok, error, args = validate_tool_args("update_order_address", 
                                        {"order_id": "ESP12345", "new_address": ""})
    print(f"  空地址: {ok}, {error}")
    assert not ok, "应该失败验证"
    
    print("  ✅ 通过")


def test_estimate_shipping():
    """测试运费估算"""
    print("\n" + "=" * 60)
    print("测试 3: 运费估算")
    print("=" * 60)
    
    # 测试正确输入
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": "España", "weight": 2.5})
    print(f"  正确输入: {ok}, {error}, {args}")
    assert ok, "应该通过验证"
    
    # 测试重量为负
    ok, error, args = validate_tool_args("estimate_shipping", 
                                        {"country": "España", "weight": -1})
    print(f"  负重量: {ok}, {error}")
    assert not ok, "应该失败验证"
    
    print("  ✅ 通过")


if __name__ == "__main__":
    print("🚀 开始测试 Schema 验证")
    
    test_query_order_logistics()
    test_update_order_address()
    test_estimate_shipping()
    
    print("\n" + "=" * 60)
    print("🎉 所有测试通过！")
    print("=" * 60)
