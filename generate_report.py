#!/usr/bin/env python3
"""
Daily Market Report Generator
Claude API + Web Search で市況データを取得し、HTMLレポートを生成する。
"""

import anthropic
import datetime
import os
import re

DEFAULT_PRIMARY_MODEL = "claude-sonnet-4-20250514"
DEFAULT_FALLBACK_MODEL = "claude-opus-4-20250514"
DEFAULT_MAX_OUTPUT_TOKENS = 3500
REQUIRED_SECTION_PATTERNS = {
    "上がりそう": [
        r"上がりそう",
        r"上昇.{0,12}銘柄",
        r"買い.{0,12}候補",
        r"強気.{0,12}銘柄",
    ],
    "落ちそう": [
        r"落ちそう",
        r"下落.{0,12}銘柄",
        r"売り.{0,12}候補",
        r"弱気.{0,12}銘柄",
    ],
}


def get_japan_now():
    """日本時間の現在日時を取得"""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    jst = datetime.timezone(datetime.timedelta(hours=9))
    return utc_now.astimezone(jst)


def get_japan_date(jst_now):
    """日本語表示用の日付文字列を取得"""
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    wd = weekdays[jst_now.weekday()]
    return jst_now.strftime(f"%-m/%-d（{wd}）朝")


def get_existing_report_date(path="index.html"):
    """既存HTMLに埋め込まれた report-date を取得"""
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    match = re.search(r"report-date:\s*(\d{4}-\d{2}-\d{2})", content)
    if match:
        return match.group(1)
    return None


def add_report_date_marker(html_content, iso_date):
    """生成HTMLに report-date コメントを埋め込む"""
    marker = f"<!-- report-date: {iso_date} -->"
    content = re.sub(r"<!--\s*report-date:\s*\d{4}-\d{2}-\d{2}\s*-->\n?", "", html_content)

    first_line, sep, rest = content.partition("\n")
    if first_line.lower().startswith("<!doctype"):
        return f"{first_line}\n{marker}\n{rest}" if sep else f"{first_line}\n{marker}\n"
    return f"{marker}\n{content}"


def get_max_output_tokens():
    raw = os.getenv("ANTHROPIC_MAX_OUTPUT_TOKENS", str(DEFAULT_MAX_OUTPUT_TOKENS))
    try:
        return max(1200, int(raw))
    except ValueError:
        return DEFAULT_MAX_OUTPUT_TOKENS


def get_missing_required_sections(html_content):
    """必須セクションの不足判定（表現ゆらぎを許容）"""
    missing = []
    for section_name, patterns in REQUIRED_SECTION_PATTERNS.items():
        if not any(re.search(pattern, html_content) for pattern in patterns):
            missing.append(section_name)
    return missing


def inject_fallback_sections(html_content, missing_sections):
    """不足セクションを最低限のHTMLで補完して処理継続できるようにする"""
    blocks = []
    if "上がりそう" in missing_sections:
        blocks.append(
            """
<section style="margin:20px 0;padding:14px;border-radius:12px;border:1px solid #86efac;background:#f0fdf4;">
  <h2 style="margin:0 0 8px;font-size:20px;color:#166534;">上がりそうな銘柄</h2>
  <p style="margin:0;color:#14532d;line-height:1.7;">本日は十分な根拠を満たす候補を抽出できませんでした。次回更新で再判定します。</p>
</section>
""".strip()
        )

    if "落ちそう" in missing_sections:
        blocks.append(
            """
<section style="margin:20px 0;padding:14px;border-radius:12px;border:1px solid #fca5a5;background:#fef2f2;">
  <h2 style="margin:0 0 8px;font-size:20px;color:#991b1b;">落ちそうな銘柄</h2>
  <p style="margin:0;color:#7f1d1d;line-height:1.7;">本日は十分な根拠を満たす候補を抽出できませんでした。次回更新で再判定します。</p>
</section>
""".strip()
        )

    fallback_html = "\n".join(blocks)
    body_close_idx = html_content.lower().rfind("</body>")
    if body_close_idx >= 0:
        return html_content[:body_close_idx] + fallback_html + "\n" + html_content[body_close_idx:]
    return html_content + "\n" + fallback_html


def request_html_with_fallback(client, prompt):
    primary_model = os.getenv("ANTHROPIC_MODEL", DEFAULT_PRIMARY_MODEL)
    fallback_model = os.getenv("ANTHROPIC_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)
    max_output_tokens = get_max_output_tokens()

    models = [primary_model]
    if fallback_model and fallback_model not in models:
        models.append(fallback_model)

    last_error = None
    for model in models:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_output_tokens,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                }],
                messages=[{"role": "user", "content": prompt}],
            )
            print(f"Model used: {model} / max_output_tokens={max_output_tokens}")
            return response
        except Exception as exc:
            last_error = exc
            print(f"Model failed: {model} ({exc})")

    raise last_error


def generate_report():
    client = anthropic.Anthropic()

    jst_now = get_japan_now()
    japan_date = get_japan_date(jst_now)
    iso_date = jst_now.strftime("%Y-%m-%d")

    force_generate = os.getenv("FORCE_GENERATE", "0") == "1"
    existing_report_date = get_existing_report_date("index.html")
    if existing_report_date == iso_date and not force_generate:
        print(f"Skip API call: report already generated for {iso_date}")
        return

    prompt = f"""あなたは金融市場のアナリストです。今日の日付は{japan_date}（日本時間）です。

以下の手順でマーケットレポートHTMLを生成してください。

## Step 1: Web検索で最新の市況データを取得
以下の6項目の最新値と前日比（%）を検索してください:
1. S&P 500
2. 日経平均
3. NY原油 WTI
4. 天然ガス（TTF or Henry Hub）
5. NY金先物
6. ドル円 為替レート

## Step 2: Web検索でマーケットニュースを3本取得
株式・商品・為替に関連する今日の主要ニュースを3本だけ検索してまとめてください。

## Step 3: Web検索で「上がりそう/落ちそう」銘柄候補を抽出
米国株または日本株から、以下を抽出してください（必須）:
- 上がりそうな銘柄: 3銘柄
- 落ちそうな銘柄: 3銘柄

各銘柄に次の情報を必ず含めてください:
- 銘柄名
- ティッカー
- 想定方向（上昇 or 下落）
- 根拠（直近ニュース、決算、需給、金利、セクター動向などを1行）
- 注目ポイント（決算日、重要指標、価格帯など1つ、1行）

不確実な予想であることを短く明記してください。

## Step 4: 以下の仕様に従ってHTMLを生成
- 完全な単一HTMLファイル（CSS・JSすべてインライン）
- <!DOCTYPE html>から</html>まで完全に出力すること
- 余計な説明文は不要、HTMLコードのみ出力
- 読者は「経済に詳しくない人」を想定すること

### デザイン仕様:
- ヘッダー: 濃紺(#1a2744)背景、白文字、「🇺🇸 NY市況 & マーケットサマリー」、右側に日付「{japan_date}」
- 冒頭サマリー: 「30秒でわかる今日のポイント」を3行で表示
  - 各行は「何が起きたか」「生活者目線で何を意味するか」を平易に1文で書く
- 市況カード: 2列グリッド、6カード（S&P500, 日経平均, NY原油, 天然ガス, NY金, ドル円）
  - 各カードにラベル（淡色背景#f0ede8）、数値（28px bold）、変動率バッジ
  - プラスは緑(#16a34a)、マイナスは赤(#dc2626)のバッジ
  - 各カードに「ひとこと解説」を1行追加（例: 円安は輸入品の値上がり要因）
- ニュースセクション: 「ニュースひとめで」見出し、3トピック
  - ニュースは必ず3トピックのみ
  - 各トピック: 青(#2c4a7c)背景のヘッダー、▸付きポイント、重要語は赤太字
  - 各トピックに「なぜ気にする?」を1行で追記
- 銘柄セクション: 「上がりそうな銘柄」「落ちそうな銘柄」の2ブロックを必ず表示
  - それぞれ3件、カード形式
  - カード内に「銘柄名（ティッカー）」「根拠」「注目ポイント」を表示
  - 上がりそうは緑系、落ちそうは赤系の見出し色で視認性を分ける
- 免責文: 「投資助言ではなく参考情報」など短い注意書きを銘柄セクション直下に配置
- フッター: 「Generated by Claude · データはWeb検索に基づく速報値」
- フォント: "Noto Sans JP", "Hiragino Sans", sans-serif
- max-width: 700px, 中央寄せ
- レスポンシブ対応（700px以下で1列）
- モバイル最適化: 画面幅320pxでも横スクロールなし
  - body余白を十分に確保（左右12px以上）
  - 見出し、本文、バッジの文字サイズを段階的に縮小
  - カードの上下余白を広めにしてタップしやすくする
- body背景: #e8e4df

### 文章ルール（初心者向け）
- 専門用語は使ってよいが、初出で必ず（）内に短い説明を付ける
  - 例: 利回り（債券を持ったときの実質的な年収益率）
- 1文はできるだけ短く（目安50文字前後）、断定しすぎない
- 「上昇/下落の理由」は、ニュース事実と推測を分けて書く
- 難しい略語だけで終わらせない（TTF, CPI, FOMCなどは一言説明）
- 読者が次に見るべきポイントを最後に1行で示す（例: 今夜の米雇用統計に注目）

### 出力量の制約（クレジット節約）
- HTMLの総量は必要最小限にする（冗長な装飾CSSを避ける）
- 余計な前置き・重複説明は書かない
- 各説明文は簡潔にする（1〜2文まで）

HTMLコードのみを出力してください。```html等のマークダウン記法は使わないでください。
"""

    response = request_html_with_fallback(client, prompt)

    # レスポンスからHTMLを抽出
    html_content = ""
    for block in response.content:
        if block.type == "text":
            html_content += block.text

    # マークダウンのコードブロックが含まれている場合は除去
    html_content = html_content.strip()
    if html_content.startswith("```html"):
        html_content = html_content[7:]
    if html_content.startswith("```"):
        html_content = html_content[3:]
    if html_content.endswith("```"):
        html_content = html_content[:-3]
    html_content = html_content.strip()

    # <!DOCTYPE から始まるように調整
    doctype_idx = html_content.lower().find("<!doctype")
    if doctype_idx > 0:
        html_content = html_content[doctype_idx:]

    # 必須セクションの最低限バリデーション（不足時は自動補完して継続）
    missing_sections = get_missing_required_sections(html_content)
    if missing_sections:
        missing_str = ", ".join(missing_sections)
        print(
            f"Warning: Generated HTML is missing required stock sections: {missing_str}"
        )
        html_content = inject_fallback_sections(html_content, missing_sections)

    html_content = add_report_date_marker(html_content, iso_date)

    # 結果を保存
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Report generated successfully for {japan_date}")
    print(f"HTML size: {len(html_content)} bytes")

if __name__ == "__main__":
    generate_report()
