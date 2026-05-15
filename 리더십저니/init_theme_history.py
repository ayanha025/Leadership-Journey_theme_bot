"""
큐레이션 XLS 파일에서 기발행 테마명(키워드명)을 추출해 theme_history.json 초기화
실행: python init_theme_history.py --xls 큐레이션파일.xls
"""
import argparse
import json
import os
from bs4 import BeautifulSoup


def extract_theme_names(xls_path):
    with open(xls_path, "r", encoding="utf-8") as f:
        content = f.read()
    soup = BeautifulSoup(content, "html.parser")
    rows = soup.find_all("tr")

    themes = []
    seen = set()
    for row in rows[1:]:  # 헤더 제외
        cells = row.find_all(["td", "th"])
        if len(cells) > 3:
            name = cells[3].get_text(strip=True)  # 키워드명 컬럼
            if name and len(name) >= 4 and name not in seen:
                themes.append(name)
                seen.add(name)
    return themes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xls", required=True, help="큐레이션 XLS 파일 경로")
    parser.add_argument("--output", default="data/theme_history.json")
    args = parser.parse_args()

    themes = extract_theme_names(args.xls)

    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(themes, f, ensure_ascii=False, indent=2)

    print(f"완료: {len(themes)}개 테마 -> {args.output}")
    for t in themes[:5]:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
