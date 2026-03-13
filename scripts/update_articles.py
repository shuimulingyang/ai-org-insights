#!/usr/bin/env python3
"""
AI Org Insights — Daily Article Updater
每日自动搜索 AI 组织变革 & HR 转型前沿文章，提炼核心观点，更新 data.js
"""

import json
import re
import sys
import os
from datetime import datetime, timezone
from duckduckgo_search import DDGS
import anthropic

# ── 配置 ──────────────────────────────────────────────────────────────────────
MAX_NEW_ARTICLES = 5
DAYS_LOOKBACK    = 60   # 只收录最近 N 天内的文章
TARGET_SOURCES   = [
    "McKinsey", "BCG", "Gartner", "Josh Bersin", "Mercer",
    "Deloitte", "PwC", "Korn Ferry", "WEF", "Fortune", "Harvard Business Review"
]

SEARCH_QUERIES = [
    "McKinsey BCG AI organizational transformation workforce restructuring 2026",
    "Gartner CHRO HR transformation future of work AI 2026",
    "Josh Bersin Mercer AI HR agentic workforce skills 2026",
    "AI middle management flattening hierarchy future organization 2026",
    "Deloitte PwC WEF skills-based organization AI talent 2026",
]

DATA_JS_PATH = os.path.join(os.path.dirname(__file__), "..", "data.js")

# ── 读取现有数据 ───────────────────────────────────────────────────────────────
def load_existing_data():
    with open(DATA_JS_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    # 提取 JSON 部分
    match = re.search(r'const ARTICLES_DATA\s*=\s*(\{[\s\S]+\});?\s*$', content)
    if not match:
        raise ValueError("无法解析 data.js")
    data = json.loads(match.group(1))
    return data

# ── 搜索新文章 ────────────────────────────────────────────────────────────────
def search_articles():
    results = []
    seen_urls = set()
    with DDGS() as ddgs:
        for query in SEARCH_QUERIES:
            try:
                hits = list(ddgs.text(query, max_results=8, timelimit="m"))  # m = past month
                for h in hits:
                    url = h.get("href", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        results.append({
                            "title": h.get("title", ""),
                            "url":   url,
                            "body":  h.get("body", ""),
                        })
            except Exception as e:
                print(f"搜索失败 [{query[:40]}]: {e}", file=sys.stderr)
    return results

# ── 用 Claude 判断并提炼文章 ──────────────────────────────────────────────────
def extract_insights(client, candidates, existing_urls):
    today = datetime.now(timezone.utc).strftime("%Y-%m")

    prompt = f"""你是 AI 组织洞察研究员。以下是今天搜索到的候选文章列表（标题 + 摘要 + URL）。

## 目标
从中挑选 **最多 {MAX_NEW_ARTICLES} 篇**高质量文章，要求：
1. 来源必须是：{', '.join(TARGET_SOURCES)} 之一（或这些机构的官方博客/研究报告）
2. 主题涉及：AI 对组织结构的冲击 / HR 职能转型 / 未来工作形态 / Agentic AI / 技能型组织
3. URL **不在**以下已收录列表中：
{chr(10).join('   - ' + u for u in existing_urls)}

## 候选文章
{json.dumps(candidates, ensure_ascii=False, indent=2)}

## 输出格式
只输出一个合法 JSON 数组（不要任何解释文字），每个元素结构如下：
[
  {{
    "id": "来源关键词-年月（小写连字符，如 mckinsey-agentic-org-2026-03）",
    "title": "原始标题（保持原文语言）",
    "source": "机构名（从 TARGET_SOURCES 中选一个最匹配的）",
    "date": "{today}",
    "category": "org-impact 或 hr-transform 或 both",
    "lang": "en 或 zh",
    "url": "原始 URL",
    "summary": "一句话中文摘要（30字以内）",
    "key_insights": [
      { "zh": "中文观点1（含具体数据或论断，30字以内）", "en": "English insight 1 (≤25 words, data-driven)" },
      { "zh": "中文观点2（30字以内）", "en": "English insight 2 (≤25 words)" },
      { "zh": "中文观点3（30字以内）", "en": "English insight 3 (≤25 words)" }
    ]
  }}
]

category 规则：
- org-impact：主要讨论 AI 对组织结构、层级、管理模式的冲击
- hr-transform：主要讨论 HR 职能转型、CHRO 角色、人才战略
- both：两者兼有

如果没有符合条件的文章，返回空数组 []
"""

    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    # 提取 JSON
    match = re.search(r'\[[\s\S]*\]', raw)
    if not match:
        print("Claude 未返回有效 JSON", file=sys.stderr)
        return []
    return json.loads(match.group(0))

# ── 更新 data.js ───────────────────────────────────────────────────────────────
def save_data(data):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data["last_updated"] = today

    js_content = (
        f"// AI 组织洞察数据 · 每日自动更新\n"
        f"// 由 Claude AI 搜索并提炼，最后更新：{today}\n"
        f"const ARTICLES_DATA = {json.dumps(data, ensure_ascii=False, indent=2)};\n"
    )
    with open(DATA_JS_PATH, "w", encoding="utf-8") as f:
        f.write(js_content)

# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("错误：未找到 ANTHROPIC_API_KEY 环境变量", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print("📖 读取现有文章数据...")
    data = load_existing_data()
    existing_urls = {a["url"] for a in data["articles"]}
    existing_ids  = {a["id"]  for a in data["articles"]}
    print(f"   现有文章：{len(data['articles'])} 篇")

    print("🔍 搜索新文章...")
    candidates = search_articles()
    print(f"   找到候选：{len(candidates)} 篇")

    if not candidates:
        print("⚠️  无候选文章，跳过更新")
        return

    print("🧠 用 Claude 提炼核心观点...")
    new_articles = extract_insights(client, candidates, existing_urls)

    # 去重（以防 Claude 返回已有文章）
    new_articles = [
        a for a in new_articles
        if a.get("url") not in existing_urls and a.get("id") not in existing_ids
    ]

    if not new_articles:
        print("✅ 本次无新增高质量文章，data.js 保持不变")
        return

    print(f"✨ 新增 {len(new_articles)} 篇文章：")
    for a in new_articles:
        print(f"   [{a['source']}] {a['title'][:60]}")

    # 追加到最前面（最新的排前面）
    data["articles"] = new_articles + data["articles"]
    save_data(data)
    print(f"💾 data.js 已更新，当前共 {len(data['articles'])} 篇文章")

if __name__ == "__main__":
    main()
