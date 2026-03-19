# 📈 Daily Market Report (自動更新)

毎朝 9:00（日本時間）に GitHub Actions が自動実行し、Claude API で最新の市況レポートを生成して GitHub Pages に公開します。

## セットアップ手順

### 1. GitHubリポジトリを作成
```bash
# 新しいリポジトリを作成（GitHub上で「market-report」等の名前で作成）
# Public リポジトリにする（GitHub Pages無料利用のため）
```

### 2. ファイルをプッシュ
```bash
cd market-report
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/market-report.git
git push -u origin main
```

### 3. Anthropic API Keyを設定
1. リポジトリの **Settings** → **Secrets and variables** → **Actions** を開く
2. **New repository secret** をクリック
3. Name: `ANTHROPIC_API_KEY`
4. Value: あなたの Anthropic API Key（`sk-ant-...`）

### 4. GitHub Pagesを有効化
1. リポジトリの **Settings** → **Pages** を開く
2. Source: **Deploy from a branch**
3. Branch: **main** / **/ (root)** を選択
4. **Save** をクリック

### 5. 動作確認
1. リポジトリの **Actions** タブを開く
2. **Daily Market Report** ワークフローを選択
3. **Run workflow** → **Run workflow** で手動実行
4. 数分後、`https://YOUR_USERNAME.github.io/market-report/` にアクセス

## 公開URL

```
https://YOUR_USERNAME.github.io/market-report/
```

このURLをLINEグループにピン留めすれば、メンバーは毎朝同じリンクで最新レポートを閲覧できます。

## カスタマイズ

### 更新時刻の変更
`.github/workflows/daily-report.yml` の cron を編集:
```yaml
# 例: 日本時間 7:00 AM（UTC 22:00 前日）
- cron: '0 22 * * *'
```

### API利用料の目安
- Claude Sonnet + Web Search: 約 $0.05〜0.10/回
- 月30回実行: 約 $1.5〜3.0/月

## 注意事項
- GitHub Actions の cron は数分〜十数分の遅延が生じることがあります
- データはWeb検索に基づく速報値であり、正確性を保証するものではありません
- Anthropic API の利用規約・料金にご注意ください
