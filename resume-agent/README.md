# Resume Agent — 自动投简历系统

Automated job search and resume application agents. Search remote job boards, generate tailored cover letters, and auto-fill applications on Greenhouse and Lever.

## Features

- **Job search** — Aggregates remote jobs from Remotive and Arbeitnow APIs
- **Smart matching** — Filters jobs by your keyword preferences
- **Cover letter generation** — Template-based or AI-tailored (OpenAI optional)
- **Auto-apply agents**:
  - `greenhouse` — Fills Greenhouse application forms
  - `lever` — Fills Lever application forms
  - `manual` — Generates cover letter for manual apply
- **Application tracking** — SQLite database tracks all applications and status
- **Safe defaults** — Dry-run mode enabled by default; auto-submit disabled

## Quick Start

```bash
cd resume-agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium

# Option A: Use your PDF resume directly (recommended)
cp /path/to/your/resume.pdf resume.pdf
resume-agent apply --resume resume.pdf --dry-run

# Option B: Extract PDF to YAML for review, then apply
resume-agent import-pdf resume.pdf -o resume.yaml
resume-agent apply --dry-run

# Search jobs
resume-agent search --limit 20

# Apply for real (fills forms + uploads PDF, does not submit by default)
resume-agent apply --limit 5

# Check application history
resume-agent status
```

## Configuration

Copy `agent-config.example.yaml` to `agent-config.yaml`:

```yaml
search_keywords:
  - software engineer
  - full stack
dry_run: true        # Preview mode
auto_submit: false   # Set true to actually submit (use carefully!)
max_applications_per_run: 5
```

Optional `.env` for AI cover letters:

```
OPENAI_API_KEY=sk-...
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `resume-agent init` | Create sample resume.yaml |
| `resume-agent import-pdf <file>` | Extract PDF resume to YAML |
| `resume-agent search` | Search matching jobs |
| `resume-agent apply` | Search + auto-apply |
| `resume-agent status` | View application history |
| `resume-agent cover-letter <url>` | Generate cover letter for a job |

## Architecture

```
resume-agent/
├── src/resume_agent/
│   ├── agents/          # Greenhouse, Lever, Manual apply agents
│   ├── search/          # Job board API integration
│   ├── llm/             # Cover letter generation
│   ├── storage/         # SQLite application tracker
│   ├── orchestrator.py  # Main workflow coordinator
│   └── cli.py           # Command-line interface
├── resume.example.yaml
└── agent-config.example.yaml
```

## Safety Notes

1. **Always start with `--dry-run`** to preview what will happen
2. **`auto_submit: false` by default** — forms are pre-filled but not submitted until you enable it
3. Review each application before enabling auto-submit
4. Respect job board terms of service and rate limits
5. Never commit `resume.yaml` or `.env` with personal data

## 中文说明

这是一个自动投简历工具，**直接支持 PDF 简历**。

### 只用 PDF（最简单）

```bash
cd resume-agent
pip install -e .
playwright install chromium

# 把你的 PDF 简历放进来
cp ~/Downloads/我的简历.pdf resume.pdf

# 预览投递（不会真正提交）
resume-agent apply --resume resume.pdf --dry-run

# 正式投递（自动填表 + 上传 PDF）
resume-agent apply --resume resume.pdf
```

系统会：
1. 从 PDF 自动提取姓名、邮箱、电话、LinkedIn、技能等
2. 投递时自动上传你的 PDF 到 Greenhouse / Lever 表单
3. 生成匹配岗位的求职信

可选：设置 `OPENAI_API_KEY` 后，PDF 解析和求职信质量会更好。

### 其他命令

```bash
# 把 PDF 解析成 YAML，方便检查和修改
resume-agent import-pdf resume.pdf -o resume.yaml

# 查看原始 PDF 文本（调试用）
resume-agent import-pdf resume.pdf --show-text

# 搜索职位 / 查看投递记录
resume-agent search
resume-agent status
```

默认开启安全模式（dry_run），不会自动提交表单。确认无误后可在配置中设置 `auto_submit: true`。
