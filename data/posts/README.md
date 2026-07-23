# 如何更新博客

本站是静态站：列表读 `data/posts.json`，正文读 `data/posts/*.md`。

## 新写一篇

1. 在 `data/posts/` 新建 Markdown，文件名即 slug（如 `spring-notes.md`）。
2. 在 `data/posts.json` 增加一条（**slug 不要带 `.md`**）：

```json
{
  "title": "春日札记",
  "date": "2026-03-21",
  "summary": "一两句摘要，出现在列表页。",
  "slug": "spring-notes"
}
```

3. 提交并推送到 GitHub（GitHub Pages 会自动更新）：

```bash
git add data/posts/spring-notes.md data/posts.json
git commit -m "Add spring-notes post"
git push
```

## 修改已有文章

- 改正文：直接编辑对应的 `data/posts/某slug.md`
- 改标题 / 日期 / 摘要：编辑 `data/posts.json` 里那一条
- 删文：删掉 `.md`，并去掉 JSON 里对应项

## 本地预览

用本地静态服务器打开（直接双击打开时，`fetch` 可能被浏览器拦住）：

```bash
python3 -m http.server 8080
```

然后访问 `http://localhost:8080/blog.html`。

## 约定

| 字段 | 说明 |
|---|---|
| `title` | 列表标题，可用中英 |
| `date` | 建议 `YYYY-MM-DD` |
| `summary` | 列表摘要 |
| `slug` | 对应 `data/posts/{slug}.md` |
