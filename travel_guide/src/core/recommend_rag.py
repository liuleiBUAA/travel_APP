#!/usr/bin/env python3
"""
RAG增强旅行推荐系统
在原有规则引擎基础上增加自然语言理解能力
使用国内免费模型：通义千问 + DeepSeek
"""

import json
import os
import re
from typing import Optional, List, Dict
from datetime import datetime
import requests

# 导入原有的推荐引擎
from recommend_smart import recommend_destinations, recommend_route, print_result

# ============ 配置 ============
# 通义千问配置（推荐）
# 注册：https://dashscope.aliyun.com
QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "")

# DeepSeek配置（可选，用于语义重排序）
# 注册：https://platform.deepseek.com
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# ============ RAG组件1：自然语言参数提取 ============
def extract_params_from_natural_language(user_query: str) -> dict:
    """
    使用通义千问从自然语言中提取结构化参数

    示例：
      输入："我想9月去Europe度蜜月，喜欢浪漫的湖边小镇，预算10-12天"
      输出：{
        "region": "Europe",
        "countries": ["瑞士", "奥地利"],
        "tags": ["小镇村落", "自然风光"],
        "month": 9,
        "days": [10, 12]
      }
    """
    if not QWEN_API_KEY:
        print("⚠️  未配置QWEN_API_KEY，跳过自然语言解析")
        return None

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    prompt = f"""你是一个旅行参数提取助手。从用户查询中提取旅行参数，输出JSON格式。

用户查询：{user_query}

提取规则：
1. region: 从["Europe", "North_America", "Oceania", "Asia"]中选择，根据提到的国家/城市判断
2. countries: 提取具体国家名（如"法国"、"意大利"），如果没提到则为空数组
3. tags: 从以下标签中选择匹配的（可多选）：
   - "人文历史"：博物馆、古迹、历史文化
   - "自然风光"：山川湖海、国家公园、自然景观
   - "海岛海滨"：海滩、海岛度假
   - "现代都市"：大城市、购物、现代建筑
   - "户外探险"：徒步、滑雪、极限运动
   - "小镇村落"：小镇风情、田园风光
   - "亲子家庭"：适合带孩子
4. month: 出发月份（1-12），如果没提到则为null
5. days: 天数，如果是范围用数组[min, max]，如果是单个数字用[num]，没提到则为null

语义映射规则：
- "浪漫" → ["小镇村落", "自然风光"]
- "度蜜月" → ["小镇村落", "自然风光"]
- "亲子游" → ["亲子家庭"]
- "看海" → ["海岛海滨"]
- "看山" → ["自然风光"]
- "网红打卡" → ["现代都市"]
- "古迹" → ["人文历史"]
- "放松" → ["小镇村落", "海岛海滨"]

输出JSON格式（只返回JSON，不要任何解释）：
{{
  "region": "Europe|North_America|Oceania|Asia|null",
  "countries": ["国家1", "国家2"] 或 [],
  "tags": ["标签1", "标签2"] 或 [],
  "month": 1-12 或 null,
  "days": [min, max] 或 [num] 或 null
}}"""

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "qwen-plus",
        "input": {
            "messages": [
                {"role": "system", "content": "你是一个专业的旅行参数提取助手，严格按照JSON格式输出。"},
                {"role": "user", "content": prompt}
            ]
        },
        "parameters": {
            "result_format": "message"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        result = response.json()

        if 'output' not in result:
            print(f"❌ API返回错误：{result}")
            return None

        content = result['output']['choices'][0]['message']['content']

        # 提取JSON（可能包含markdown代码块）
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        else:
            # 尝试直接提取JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

        params = json.loads(content)

        # 清理null值
        if params.get('region') == 'null':
            params['region'] = None
        if params.get('month') == 'null':
            params['month'] = None
        if params.get('days') == 'null':
            params['days'] = None

        return params

    except Exception as e:
        print(f"❌ 参数提取失败：{e}")
        return None


# ============ RAG组件2：语义重排序（可选）============
def semantic_rerank(candidates: List[Dict], user_query: str) -> List[Dict]:
    """
    使用DeepSeek对候选结果进行语义重排序
    基于用户查询的语义相似度重新打分
    """
    if not DEEPSEEK_API_KEY:
        # 没有配置API，跳过重排序
        return candidates

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        )

        scored_candidates = []
        for cand in candidates[:10]:  # 只对前10个重排序，节省成本
            prompt = f"""用户需求：{user_query}

目的地：{cand['name']}
标签：{cand.get('matched_tags', {})}
天数：{cand['days']}天
最佳季节：{cand.get('best_season', '全年')}

评分（0-10）：这个目的地与用户需求的语义匹配度？只返回一个数字。"""

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10
            )

            try:
                semantic_score = float(response.choices[0].message.content.strip())
            except:
                semantic_score = 5.0  # fallback

            scored_candidates.append({
                **cand,
                'semantic_score': semantic_score,
                'final_score': cand['total_score'] * 0.7 + semantic_score * 0.3  # 规则70% + 语义30%
            })

        # 按综合分数重新排序
        scored_candidates.sort(key=lambda x: x['final_score'], reverse=True)

        # 添加剩余的候选（未重排序的）
        remaining = candidates[10:]
        return scored_candidates + remaining

    except Exception as e:
        print(f"⚠️  语义重排序失败：{e}，使用原始排序")
        return candidates


# ============ RAG组件3：推荐理由生成 ============
def generate_explanation(selected: List[Dict], user_query: str) -> str:
    """
    使用通义千问生成个性化推荐理由
    """
    if not QWEN_API_KEY:
        return ""

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

    destinations = "\n".join([
        f"- {d['name']} ({d['days']}天) - 标签:{d.get('matched_tags', {})} - 最佳季节:{d.get('best_season', '全年')}"
        for d in selected
    ])

    prompt = f"""用户需求：{user_query}

推荐路线包含以下目的地：
{destinations}

请用简洁、友好的语言（3-5句话）解释为什么推荐这些地方，重点说明：
1. 如何满足用户的具体需求（如"浪漫"、"蜜月"等）
2. 各目的地的核心亮点
3. 整体路线的优势（地理连贯性、季节适合等）

用轻松、专业的语气，像朋友推荐一样。"""

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "qwen-plus",
        "input": {
            "messages": [
                {"role": "user", "content": prompt}
            ]
        },
        "parameters": {
            "result_format": "message"
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        result = response.json()
        return result['output']['choices'][0]['message']['content']
    except Exception as e:
        print(f"⚠️  理由生成失败：{e}")
        return ""


# ============ 主函数：RAG增强推荐 ============
def recommend_with_rag(
    user_query: str,
    base_dir: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    use_semantic_rerank: bool = False
) -> Dict:
    """
    RAG增强推荐主函数

    Args:
        user_query: 用户自然语言查询
        base_dir: 数据目录
        use_semantic_rerank: 是否使用语义重排序（需要DeepSeek API）

    Returns:
        推荐结果字典
    """
    print(f"\n{'='*80}")
    print(f"🤖 RAG增强旅行推荐系统")
    print(f"{'='*80}")
    print(f"用户输入：{user_query}")

    # 第1步：自然语言参数提取
    print(f"\n{'='*80}")
    print(f"🔍 第1步：理解您的需求（通义千问）...")
    print(f"{'='*80}")

    params = extract_params_from_natural_language(user_query)

    if not params:
        print("❌ 无法理解查询，请使用命令行参数模式")
        return None

    # 显示提取的参数
    print(f"\n理解结果：")
    print(f"  区域：{params.get('region') or '未指定'}")
    print(f"  国家：{params.get('countries') or '未指定'}")
    print(f"  偏好：{params.get('tags') or '未指定'}")
    print(f"  月份：{params.get('month') or '未指定'}月")
    print(f"  天数：{params.get('days') or '未指定'}")

    # 检查必填参数
    if not params.get('region'):
        print("❌ 未检测到区域，请在查询中明确提到：Europe/North_America/Oceania/Asia")
        return None

    # 处理天数参数
    days_list = params.get('days')
    if not days_list:
        # 默认给3个方案
        days_list = None
    elif len(days_list) == 1:
        days_list = days_list
    elif len(days_list) == 2:
        days_list = days_list

    # 第2步：调用规则引擎筛选候选
    print(f"\n{'='*80}")
    print(f"⚙️  第2步：规则引擎筛选...")
    print(f"{'='*80}")

    candidates = recommend_destinations(
        region=params['region'],
        countries=params.get('countries') or None,
        tags=params.get('tags') or None,
        month=params.get('month'),
        top_n=20
    )

    if not candidates:
        print("❌ 没有找到符合条件的目的地")
        return None

    print(f"找到 {len(candidates)} 个候选目的地")
    for i, c in enumerate(candidates[:5], 1):
        print(f"  {i}. {c['name']} - {c['days']}天 - 评分:{c['total_score']}")

    # 第3步：语义重排序（可选）
    if use_semantic_rerank and DEEPSEEK_API_KEY:
        print(f"\n{'='*80}")
        print(f"🤖 第3步：语义重排序（DeepSeek）...")
        print(f"{'='*80}")
        candidates = semantic_rerank(candidates, user_query)
        print(f"重排序后Top 5：")
        for i, c in enumerate(candidates[:5], 1):
            print(f"  {i}. {c['name']} - 综合分:{c.get('final_score', c['total_score']):.2f}")

    # 第4步：generated_routes（根据天数）
    print(f"\n{'='*80}")
    print(f"🗺️  第4步：generated_routes...")
    print(f"{'='*80}")

    if days_list is None:
        # 生成3个方案
        results = []
        for days in [7, 10, 14]:
            print(f"\n>>> 生成{days}天方案...")
            result = recommend_route(
                region=params['region'],
                total_days=days,
                tags=params.get('tags'),
                month=params.get('month'),
                countries=params.get('countries')
            )
            if result.get('success'):
                results.append(result)

        # 为每个方案生成解释
        for i, result in enumerate(results, 1):
            print(f"\n{'#'*80}")
            print(f"# 方案 {i}: {result['total_days']}天行程")
            print(f"{'#'*80}")

            # 生成个性化解释
            explanation = generate_explanation(result['selected'], user_query)
            if explanation:
                print(f"\n💡 推荐理由：")
                print(f"{'-'*60}")
                print(explanation)
                print(f"{'-'*60}")

            print_result(result)

        return {"success": True, "results": results}

    else:
        # 单个方案
        if len(days_list) == 1:
            days = days_list[0]
        else:
            days = sum(days_list) // 2  # 取中间值

        result = recommend_route(
            region=params['region'],
            total_days=days,
            tags=params.get('tags'),
            month=params.get('month'),
            countries=params.get('countries')
        )

        if result.get('success'):
            # 生成个性化解释
            explanation = generate_explanation(result['selected'], user_query)
            if explanation:
                print(f"\n{'='*80}")
                print(f"💡 推荐理由")
                print(f"{'='*80}")
                print(explanation)
                print(f"{'='*80}\n")

            print_result(result)

        return result


# ============ 命令行接口 ============
def main():
    import argparse

    parser = argparse.ArgumentParser(description='RAG增强旅行推荐系统')
    parser.add_argument('query', nargs='*', help='自然语言查询（如："我想9月去Europe度蜜月"）')
    parser.add_argument('--rerank', action='store_true', help='启用语义重排序（需要DeepSeek API）')
    parser.add_argument('--config', action='store_true', help='显示配置指南')

    args = parser.parse_args()

    if args.config:
        print("""
╔════════════════════════════════════════════════════════════════╗
║           RAG推荐系统配置指南                                   ║
╚════════════════════════════════════════════════════════════════╝

【必需】通义千问API（用于自然语言理解）
  1. 注册：https://dashscope.aliyun.com
  2. 获取API Key
  3. 设置环境变量：
     export QWEN_API_KEY="your_api_key"

  或在代码中直接配置：
     QWEN_API_KEY = "your_api_key"

【可选】DeepSeek API（用于语义重排序）
  1. 注册：https://platform.deepseek.com
  2. 获取API Key
  3. 设置环境变量：
     export DEEPSEEK_API_KEY="your_api_key"

【测试】
  python recommend_with_rag.py "我想9月去Europe度蜜月，喜欢浪漫的湖边小镇"
        """)
        return

    if not args.query:
        print("请输入查询，或使用 --config 查看配置指南")
        print("\n示例：")
        print('  python recommend_with_rag.py "我想9月去Europe度蜜月，喜欢浪漫的湖边小镇"')
        print('  python recommend_with_rag.py "带孩子去North_America玩，10-12天，喜欢自然风光"')
        return

    user_query = " ".join(args.query)

    # 检查API配置
    if not QWEN_API_KEY:
        print("❌ 未配置QWEN_API_KEY")
        print("请运行: python recommend_with_rag.py --config")
        return

    # 执行推荐
    recommend_with_rag(user_query, use_semantic_rerank=args.rerank)


if __name__ == "__main__":
    main()
