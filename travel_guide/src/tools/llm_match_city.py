#!/usr/bin/env python3
"""
LLM辅助城市名称匹配
使用AWS Bedrock Claude API将模糊的城市名称匹配到攻略中的实际目的地
"""
import json
import os
import boto3
from typing import Optional, Dict
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.recommend_smart import get_all_destinations


def normalize_quotes(text: str) -> str:
    """
    规范化引号：将ASCII双引号转换为中文引号
    交替使用左引号(")和右引号(")

    Args:
        text: 包含ASCII双引号的文本

    Returns:
        转换后的文本
    """
    result = []
    quote_open = True
    for char in text:
        if char == '"':  # ASCII引号 (U+0022)
            if quote_open:
                result.append('\u201c')  # 左引号 (U+201C)
            else:
                result.append('\u201d')  # 右引号 (U+201D)
            quote_open = not quote_open
        else:
            result.append(char)
    return ''.join(result)


def initialize_bedrock_client(region: str = "us-west-2"):
    """
    初始化AWS Bedrock客户端

    Args:
        region: AWS区域

    Returns:
        boto3 bedrock-runtime客户端
    """
    return boto3.client(
        service_name='bedrock-runtime',
        region_name=region
    )


def llm_match_city(
    llm_generated_name: str,
    all_destinations: Dict[str, dict],
    region: Optional[str] = None,
    verbose: bool = False
) -> Optional[str]:
    """
    使用LLM将模糊的城市名称匹配到实际的攻略目的地

    Args:
        llm_generated_name: LLM生成的城市名称（如"密尔沃基"、"缅因州沿海"）
        all_destinations: 所有目的地字典 {name: info}
        region: 可选的区域过滤（如"North_America"）
        verbose: 是否打印详细信息

    Returns:
        匹配到的目的地名称，如果没有好的匹配则返回None

    Example:
        >>> dests = get_all_destinations(BASE_DIR)
        >>> result = llm_match_city("密尔沃基", dests, region="North_America")
        >>> print(result)  # 可能返回: "密歇根湖\"巨型沙丘与五彩悬崖\"大环线"
    """
    # 过滤目的地（如果指定了区域）
    if region:
        filtered_dests = {
            name: info for name, info in all_destinations.items()
            if info.get('region') == region
        }
    else:
        filtered_dests = all_destinations

    if not filtered_dests:
        if verbose:
            print(f"⚠️  区域 {region} 没有找到目的地")
        return None

    # 构建目的地列表文本
    dest_list = []
    for name, info in filtered_dests.items():
        countries = info.get('countries', [])
        hub = info.get('hub_city', 'N/A')
        dest_list.append(f"- {name} (国家: {', '.join(countries)}, Hub: {hub})")

    dest_list_text = "\n".join(dest_list)

    # 构建prompt
    prompt = f"""你是一个地理和旅游专家。用户提供了一个城市名称，你需要从给定的旅游目的地列表中找到最匹配的目的地。

用户输入的城市名称: {llm_generated_name}

可用的旅游目的地列表:
{dest_list_text}

请根据地理位置、语义关系、常识判断，从上述列表中选择最匹配的目的地。

规则:
1. 如果用户输入的是某个城市名，请找到包含该城市或该城市附近的目的地
2. 如果用户输入的是地区名（如"缅因州沿海"），请找到该地区的目的地
3. 只能返回上述列表中存在的目的地名称，不要创造新名称
4. 如果没有合适的匹配，返回"NONE"

请只返回匹配的目的地名称，不要有任何其他解释。格式如下:
MATCH: <目的地名称>

或者:
MATCH: NONE"""

    # 调用Bedrock API
    try:
        client = initialize_bedrock_client()

        # 使用Claude Sonnet 4.5 inference profile
        model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

        # 构建请求
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 200,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        if verbose:
            print(f"🤖 调用 Bedrock Claude API (model: {model_id})...")

        # 调用API
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )

        # 解析响应
        response_body = json.loads(response['body'].read())
        llm_response = response_body['content'][0]['text'].strip()

        if verbose:
            print(f"📥 LLM响应: {llm_response}")

        # 解析匹配结果
        if "MATCH:" in llm_response:
            matched_name = llm_response.split("MATCH:")[1].strip()

            if matched_name == "NONE":
                if verbose:
                    print(f"❌ LLM未找到匹配: {llm_generated_name}")
                return None

            # 规范化引号：LLM可能返回ASCII引号，但实际名称使用中文引号
            matched_name_normalized = normalize_quotes(matched_name)

            # 验证返回的名称确实存在于目的地列表中
            if matched_name_normalized in filtered_dests:
                if verbose:
                    print(f"✅ 成功匹配: {llm_generated_name} → {matched_name_normalized}")
                return matched_name_normalized
            elif matched_name in filtered_dests:
                # 如果原始名称就在列表中（可能已经是中文引号）
                if verbose:
                    print(f"✅ 成功匹配: {llm_generated_name} → {matched_name}")
                return matched_name
            else:
                if verbose:
                    print(f"⚠️  LLM返回的名称不在目的地列表中: {matched_name_normalized}")
                return None
        else:
            if verbose:
                print(f"⚠️  无法解析LLM响应")
            return None

    except Exception as e:
        print(f"❌ 调用Bedrock API失败: {e}")
        return None


def test_matching():
    """测试匹配功能"""
    print("🧪 测试LLM城市名称匹配\n")

    # 获取项目根目录
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # 加载所有目的地
    print("📚 加载目的地数据...")
    all_dests = get_all_destinations(BASE_DIR)
    print(f"   加载了 {len(all_dests)} 个目的地\n")

    # 测试用例
    test_cases = [
        ("密尔沃基", "North_America"),
        ("缅因州沿海", "North_America"),
        ("底特律", "North_America"),
        ("巴黎", "Europe"),
        ("不存在的城市XYZ", "North_America"),
    ]

    print("="*60)
    for city_name, region in test_cases:
        print(f"\n🔍 测试: {city_name} (区域: {region})")
        print("-"*60)
        result = llm_match_city(city_name, all_dests, region=region, verbose=True)
        print(f"\n📊 结果: {result if result else '无匹配'}")
        print("="*60)


if __name__ == '__main__':
    test_matching()
