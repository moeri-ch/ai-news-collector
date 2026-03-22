import os
import glob
import json
import pandas as pd
from datetime import datetime
import anthropic
from notion_client import Client

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
NOTION_PAGE_ID = "32be8e3e-06bf-809d-9204-d39d545ebfa2"


def load_latest_csv():
    today = datetime.now().strftime('%Y%m%d')
    csv_path = f"data/filtered_news_{today}.csv"
    if not os.path.exists(csv_path):
        files = sorted(glob.glob("data/filtered_news_*.csv"), reverse=True)
        if not files:
            raise FileNotFoundError("No filtered news CSV found")
        csv_path = files[0]
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} articles from {csv_path}")
    return df


def summarize_with_claude(df):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    sample_df = df.head(150)

    articles_text = ""
    for _, row in sample_df.iterrows():
        articles_text += (
            f"ソース: {row['source']}\n"
            f"タイトル: {row['title']}\n"
            f"URL: {row['link']}\n"
            f"公開日: {row['published']}\n"
            f"概要: {row.get('summary', '')}\n\n"
        )

    prompt = f"""あなたはAI・テクノロジーニュースのキュレーターです。以下は今日収集されたAI・機械学習関連の記事一覧です。

{articles_text}

以下の条件でJSONを生成してください:
1. most_picked: 複数のソースで取り上げられているか、または特に重要性の高い記事を1つ選んでください
2. latest_articles: 公開日（published）が最も新しい記事を3つ選んでください

JSONフォーマット:
{{
  "most_picked": {{
    "title": "記事タイトル（元のタイトルをそのまま使用）",
    "summary": "記事の内容を2〜3文で要約。IT専門家でない読者向けに平易な言葉で。",
    "url": "記事のURL",
    "terms": "記事内の専門用語の解説（用語がある場合のみ）。不要な場合は空文字。"
  }},
  "latest_articles": [
    {{
      "title": "記事タイトル",
      "summary": "記事の内容を2〜3文で要約。平易な言葉で。",
      "url": "記事のURL",
      "terms": "専門用語の解説（必要な場合のみ）"
    }}
  ]
}}

JSONのみ返してください。"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    if "```" in response_text:
        for part in response_text.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                response_text = part
                break

    return json.loads(response_text)


def make_text(content, bold=False, url=None):
    obj = {"type": "text", "text": {"content": content}}
    if url:
        obj["text"]["link"] = {"url": url}
    if bold:
        obj["annotations"] = {"bold": True}
    return obj


def append_to_notion(summary_data, date_str):
    notion = Client(auth=NOTION_TOKEN)
    dt = datetime.strptime(date_str, '%Y%m%d')
    date_display = dt.strftime('%Y年%m月%d日')

    most_picked = summary_data["most_picked"]
    latest_articles = summary_data["latest_articles"]

    blocks = [
        {"object": "block", "type": "divider", "divider": {}},
        {
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [make_text(f"📅 {date_display}", bold=True)]}
        },
        {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [make_text("📰 最も注目された記事")]}
        },
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [make_text(most_picked["title"], bold=True)]}
        },
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [make_text(most_picked["summary"])]}
        },
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [
                make_text("出典: "),
                make_text(most_picked["url"], url=most_picked["url"])
            ]}
        },
    ]

    if most_picked.get("terms"):
        blocks.append({
            "object": "block", "type": "callout",
            "callout": {
                "rich_text": [make_text("💡 用語解説\n" + most_picked["terms"])],
                "icon": {"type": "emoji", "emoji": "💡"}
            }
        })

    blocks.append({
        "object": "block", "type": "heading_3",
        "heading_3": {"rich_text": [make_text("🆕 最新記事トップ3")]}
    })

    for i, article in enumerate(latest_articles[:3], 1):
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [make_text(f"{i}. {article['title']}", bold=True)]}
        })
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [make_text(article["summary"])]}
        })
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [
                make_text("出典: "),
                make_text(article["url"], url=article["url"])
            ]}
        })
        if article.get("terms"):
            blocks.append({
                "object": "block", "type": "callout",
                "callout": {
                    "rich_text": [make_text("💡 用語解説\n" + article["terms"])],
                    "icon": {"type": "emoji", "emoji": "💡"}
                }
            })

    notion.blocks.children.append(block_id=NOTION_PAGE_ID, children=blocks)
    print(f"✅ Notionへの投稿完了: {date_display}")


def main():
    today = datetime.now().strftime('%Y%m%d')
    df = load_latest_csv()
    print("Claude APIで要約を生成中...")
    summary_data = summarize_with_claude(df)
    print("Notionに投稿中...")
    append_to_notion(summary_data, today)


if __name__ == "__main__":
    main()
