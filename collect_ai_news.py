import feedparser
import pandas as pd
from datetime import datetime
import os
import re
import hashlib

# 出力ディレクトリの作成
os.makedirs("data", exist_ok=True)
os.makedirs("output", exist_ok=True)

# RSSフィードの定義
feeds = {
    "Business_Insider": "https://www.businessinsider.jp/feed/index.xml",
    "ITmedia_AI_Plus": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
    "Hatena_IT": "https://b.hatena.ne.jp/hotentry/it.rss",
    "Hatena_AI": "https://b.hatena.ne.jp/q/ai?users=5&mode=rss&sort=recent",
    "Zenn_ML": "https://zenn.dev/topics/機械学習/feed",
    "Zenn_AI": "https://zenn.dev/topics/ai/feed",
    "Zenn_GenAI": "https://zenn.dev/topics/生成ai/feed",
    "Zenn_DL": "https://zenn.dev/topics/deeplearning/feed",
    "Zenn_LLM": "https://zenn.dev/topics/llm/feed",
    "Zenn_NLP": "https://zenn.dev/topics/nlp/feed",
    "Zenn_Python": "https://zenn.dev/topics/python/feed",
    "Zenn_GCP": "https://zenn.dev/topics/googlecloud/feed",
    "GCP_Blog": "https://cloudblog.withgoogle.com/rss/",
    "GCP_Japan": "https://cloudblog.withgoogle.com/ja/rss/",
    "Ggen_Blog": "https://blog.g-gen.co.jp/feed",
    "TechnoEdge": "https://www.techno-edge.net/rss20/index.rdf"
}

# HF Papersのフィードは現在使えないようなので注意が必要

# キーワードフィルター（必要に応じて調整）
keywords = [
    "生成AI", "LLM", "大規模言語モデル", "Claude", "GPT", "Gemini", "機械学習", 
    "深層学習", "AI", "人工知能", "自然言語処理", "NLP", "強化学習", "RL", 
    "Stable Diffusion", "DALL-E", "Midjourney", "Anthropic", "OpenAI", 
    "Google", "GCP", "Vertex AI", "PaLM"
]

# 今日の日付
today = datetime.now().strftime('%Y-%m-%d')
today_simple = datetime.now().strftime('%Y%m%d')

# 結果を格納するリスト
all_results = []
filtered_results = []

# 各フィードを処理
for name, url in feeds.items():
    try:
        feed = feedparser.parse(url)
        print(f"Processing {name}: Found {len(feed.entries)} entries")
        
        for entry in feed.entries:
            # 基本情報の抽出
            title = entry.title if hasattr(entry, 'title') else "No Title"
            link = entry.link if hasattr(entry, 'link') else ""
            published = entry.published if hasattr(entry, 'published') else ""
            
            # 要約がある場合は抽出、HTMLタグを除去
            summary = ""
            if hasattr(entry, 'summary'):
                summary = re.sub(r'<.*?>', '', entry.summary)
            elif hasattr(entry, 'description'):
                summary = re.sub(r'<.*?>', '', entry.description)
            
            # 一意のIDを生成
            item_id = hashlib.md5((title + link).encode()).hexdigest()
            
            # すべての記事を記録
            all_results.append({
                "id": item_id,
                "source": name,
                "title": title,
                "link": link,
                "published": published,
                "summary": summary[:200] + "..." if len(summary) > 200 else summary,
                "collected_date": today
            })
            
            # キーワードフィルタリング
            if any(keyword.lower() in title.lower() or keyword.lower() in summary.lower() for keyword in keywords):
                filtered_results.append({
                    "id": item_id,
                    "source": name,
                    "title": title,
                    "link": link,
                    "published": published,
                    "summary": summary[:200] + "..." if len(summary) > 200 else summary,
                    "collected_date": today
                })
    except Exception as e:
        print(f"Error processing {name}: {e}")

# CSVとして保存
all_df = pd.DataFrame(all_results)
filtered_df = pd.DataFrame(filtered_results)

# 全記事を保存
all_df.to_csv(f"data/all_news_{today_simple}.csv", index=False)

# フィルタリングされた記事を保存
filtered_df.to_csv(f"data/filtered_news_{today_simple}.csv", index=False)

# マークダウンレポートを生成
with open(f"output/ai_news_report_{today_simple}.md", "w", encoding="utf-8") as f:
    f.write(f"# AI・機械学習 ニュースレポート ({today})\n\n")
    f.write(f"**フィルタリング済みニュース: {len(filtered_results)}件** (全{len(all_results)}件中)\n\n")
    
    f.write("## 今日の主要ニュース\n\n")
    
    # ソース別にグループ化して表示
    sources = filtered_df['source'].unique()
    for source in sources:
        source_df = filtered_df[filtered_df['source'] == source]
        if len(source_df) > 0:
            f.write(f"### {source.replace('_', ' ')} ({len(source_df)}件)\n\n")
            for _, row in source_df.iterrows():
                f.write(f"- [{row['title']}]({row['link']})\n")
                if row['summary']:
                    f.write(f"  - {row['summary'][:150]}...\n")
            f.write("\n")

print(f"処理完了: 全{len(all_results)}件の記事、フィルタリング後{len(filtered_results)}件")
print(f"レポート生成: output/ai_news_report_{today_simple}.md")
