import sys
import os

# 把项目根目录加入路径，这样才能导入 tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import (
    query_order_status,
    modify_order_address
)


def test_query_order_status_basic():
    """最基础的测试：查询一个订单"""
    print("\n" + "="*50)
    print("测试：查询订单 ESP12345")
    print("="*50)
    
    result = query_order_status("ESP12345")
    print(f"结果：{result}")
    
    # 验证结果
    assert result["success"] is True
    print("✅ test_query_order_status_basic 通过！")


if __name__ == "__main__":
    print("🚀 开始运行测试...")
    test_query_order_status_basic()
    print("\n🎉 测试完成！")