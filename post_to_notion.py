import os
import glob
import re
from collections import Counter
import pandas as pd
from datetime import datetime
from notion_client import Client

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_PAGE_ID = "32be8e3e-06bf-809d-9204-d39d545ebfa2"
SENTINEL_TEXT = "📌 最新の情報が上に追加されます"


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


def find_most_picked_article(df):
    """全タイトルのキーワード頻度から最も注目されている記事を選ぶ。スコアとトップキーワードも返す。"""
    stop_words = {
        "の", "に", "は", "を", "が", "で", "と", "も", "や", "から", "まで",
        "より", "へ", "について", "による", "ため", "こと", "もの", "など",
        "a", "the", "in", "of", "to", "and", "for", "is", "on", "with", "at",
        "by", "an", "as", "be", "this", "that", "are", "was", "were",
    }
    word_counts = Counter()
    word_original_case = {}
    for title in df['title'].dropna():
        words = re.findall(r'[A-Za-z0-9]+|[\u3040-\u9fff]{2,}', title)
        for word in words:
            if word.lower() not in stop_words and len(word) >= 2:
                word_counts[word.lower()] += 1
                if word.lower() not in word_original_case:
                    word_original_case[word.lower()] = word

    top_words = [w for w, _ in word_counts.most_common(15)]

    best_score = -1
    best_article = None
    best_keywords = []
    for _, row in df.iterrows():
        title_lower = str(row['title']).lower()
        matched = [w for w in top_words if w in title_lower]
        score = len(matched)
        if score > best_score:
            best_score = score
            best_article = row
            best_keywords = matched

    keyword_info = [
        (word_original_case.get(kw, kw), word_counts[kw])
        for kw in best_keywords[:5]
    ]
    return (best_article if best_article is not None else df.iloc[0]), best_score, keyword_info


def get_latest_articles(df, n=3):
    """公開日が新しい順に記事を取得"""
    df_copy = df.copy()
    df_copy['pub_date'] = pd.to_datetime(df_copy['published'], errors='coerce', utc=True)
    df_valid = df_copy.dropna(subset=['pub_date']).sort_values('pub_date', ascending=False)
    return df_valid.head(n)


def make_text(content, bold=False, url=None):
    obj = {"type": "text", "text": {"content": str(content)}}
    if url:
        obj["text"]["link"] = {"url": str(url)}
    if bold:
        obj["annotations"] = {"bold": True}
    return obj


def get_sentinel_block_id(notion, page_id):
    """ページ先頭のセンチネルブロックIDを取得または作成する。
    センチネルの直後に新しいコンテンツを挿入することで常に最上部への追加を実現する。
    """
    response = notion.blocks.children.list(block_id=page_id, page_size=10)
    blocks = response.get("results", [])

    for block in blocks:
        if block.get("type") == "callout":
            rich_texts = block["callout"].get("rich_text", [])
            if rich_texts and SENTINEL_TEXT in rich_texts[0]["text"]["content"]:
                return block["id"]

    # 存在しない場合は作成（初回のみ）
    result = notion.blocks.children.append(
        block_id=page_id,
        children=[{
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": SENTINEL_TEXT}}],
                "icon": {"type": "emoji", "emoji": "📌"},
                "color": "gray_background"
            }
        }]
    )
    sentinel_id = result["results"][0]["id"]
    print(f"Sentinelブロックを作成しました: {sentinel_id}")
    return sentinel_id


def append_to_notion(df, date_str):
    notion = Client(auth=NOTION_TOKEN)
    dt = datetime.strptime(date_str, '%Y%m%d')
    date_display = dt.strftime('%Y年%m月%d日')

    most_picked, score, keyword_info = find_most_picked_article(df)
    latest_articles = get_latest_articles(df)

    kw_text = "　".join([f"{kw}（{count}件）" for kw, count in keyword_info])

    sentinel_id = get_sentinel_block_id(notion, NOTION_PAGE_ID)

    blocks = [
        {"object": "block", "type": "divider", "divider": {}},
        {
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [make_text(f"📅 {date_display}", bold=True)]}
        },
        {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [make_text(f"📰 最も注目された記事（スコア: {score} | {kw_text}）")]}
        },
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [make_text(most_picked['title'], bold=True)]}
        },
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [make_text(str(most_picked.get('summary', ''))[:400])]}
        },
        {
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [
                make_text("出典: "),
                make_text(most_picked['link'], url=most_picked['link'])
            ]}
        },
        {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [make_text("🆕 最新記事トップ3")]}
        },
    ]

    for i, (_, article) in enumerate(latest_articles.iterrows(), 1):
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [make_text(f"{i}. {article['title']}", bold=True)]}
        })
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [make_text(str(article.get('summary', ''))[:400])]}
        })
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [
                make_text("出典: "),
                make_text(article['link'], url=article['link'])
            ]}
        })

    # センチネルブロックの直後に挿入 → 常にページ最上部に追加される
    notion.blocks.children.append(
        block_id=NOTION_PAGE_ID,
        children=blocks,
        after=sentinel_id
    )
    print(f"✅ Notionへの投稿完了: {date_display}")


def main():
    today = datetime.now().strftime('%Y%m%d')
    df = load_latest_csv()
    print("Notionに投稿中...")
    append_to_notion(df, today)


if __name__ == "__main__":
    main()
