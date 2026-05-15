"""
아티클 + 영상 XLS 파일을 콘텐츠 풀 CSV로 변환하는 스크립트
실행: python prepare_data.py --article 아티클파일.xls --video 영상파일.xls
"""
import argparse
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import os

def parse_xls_html(filepath, file_type="article"):
    """HTML 형식의 XLS 파싱"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    soup = BeautifulSoup(content, "html.parser")
    rows = soup.find_all("tr")
    records = []

    if file_type == "article":
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 8:
                texts = [c.get_text(strip=True) for c in cells]
                title = texts[3]
                if title and len(title) > 3:
                    records.append({
                        "type": "아티클",
                        "cat": texts[2],
                        "title": title,
                        "author": texts[4],
                        "pub_date": texts[6][:10] if texts[6] else "",
                        "tags": texts[7],
                        "volume": texts[8] if len(texts) > 8 else ""
                    })
    else:  # video
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 10:
                texts = [c.get_text(strip=True) for c in cells]
                title = texts[5]
                if title and len(title) > 3:
                    records.append({
                        "type": "영상",
                        "cat": texts[3],
                        "title": title,
                        "author": texts[6],
                        "pub_date": texts[9][:10] if texts[9] else "",
                        "tags": texts[16] if len(texts) > 16 else "",
                        "volume": ""
                    })

    return records


def main():
    parser = argparse.ArgumentParser(description="XLS → CSV 변환")
    parser.add_argument("--article", required=True, help="아티클 XLS 파일 경로")
    parser.add_argument("--video", required=True, help="영상 XLS 파일 경로")
    parser.add_argument("--output", default="data/contents.csv", help="출력 CSV 경로")
    args = parser.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")

    print(f"아티클 파싱 중: {args.article}")
    articles = parse_xls_html(args.article, "article")
    print(f"  → {len(articles)}개 파싱 완료")

    print(f"영상 파싱 중: {args.video}")
    videos = parse_xls_html(args.video, "video")
    print(f"  → {len(videos)}개 파싱 완료")

    all_contents = articles + videos
    df = pd.DataFrame(all_contents)

    # 발행일 기준 오늘 이전 콘텐츠만
    df = df[df["pub_date"] <= today]
    df = df[df["title"].str.len() > 3]
    df = df.drop_duplicates(subset=["title"])
    df = df.sort_values("pub_date", ascending=False)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"\n✅ 완료: {len(df)}개 콘텐츠 → {args.output}")
    print(f"   아티클: {len(df[df['type']=='아티클'])}개")
    print(f"   영상:   {len(df[df['type']=='영상'])}개")


if __name__ == "__main__":
    main()
