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

# Create your resume
cp resume.example.yaml resume.yaml
# Edit resume.yaml with your info

# Search jobs
resume-agent search --limit 20

# Preview applications (dry run)
resume-agent apply --dry-run

# Apply for real (fills forms, does not submit by default)
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

这是一个自动投简历工具，帮助你：

1. 从 Remotive、Arbeitnow 等远程工作平台搜索职位
2. 根据关键词自动匹配合适的岗位
3. 自动生成求职信（支持 OpenAI 智能定制）
4. 自动填写 Greenhouse / Lever 等常见 ATS 申请表
5. 记录所有投递历史，避免重复申请

**使用步骤：**

```bash
cd resume-agent
pip install -e .
playwright install chromium
cp resume.example.yaml resume.yaml   # 编辑你的简历
resume-agent search                  # 搜索职位
resume-agent apply --dry-run         # 预览投递
resume-agent apply                   # 正式投递
resume-agent status                  # 查看投递记录
```

默认开启安全模式（dry_run），不会自动提交表单。确认无误后可在配置中设置 `auto_submit: true`。
