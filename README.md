# GitHub Agent

🤖 **Multi-agent system for automated GitHub PR generation from PRD documents**

一个基于 Claude Agent SDK 的多代理系统，可以自动分析产品需求文档、生成代码、创建 Pull Request。

## ✨ Features

- **📄 PRD 分析**: 自动分析产品需求文档，评估可行性、识别风险
- **🔍 仓库理解**: 分析 GitHub 仓库或本地项目结构
- **💻 代码生成**: 基于分析结果自动生成代码变更
- **🔀 自动 PR**: 创建分支、提交代码、创建 Pull Request
- **🏠 本地支持**: 无需 GitHub，直接修改本地项目
- **🆕 创建仓库**: 从本地项目自动创建 GitHub 仓库
- **🌐 多模型支持**: 支持 Claude、Qwen、DeepSeek 等 LLM

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/JSM-CN/github-agent.git
cd github-agent

# Install dependencies
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

## ⚙️ Configuration

### 方法 1: 环境变量

```bash
# Required: LLM API Key
export ANTHROPIC_API_KEY="your-anthropic-key"  # For Claude
# OR
export OPENAI_API_KEY="your-openai-key"        # For OpenAI/Qwen/DeepSeek

# Required: GitHub Token (for GitHub operations)
export GITHUB_TOKEN="your-github-token"

# Optional: Model Configuration
export LLM_PROVIDER="anthropic"                 # anthropic, openai, qwen, deepseek
export DEFAULT_MODEL="claude-sonnet-4-20250514"
```

### 方法 2: .env 文件

```bash
# Initialize configuration
github-agent init

# This will create a .env file with your keys
```

### 方法 3: CLI 参数

大多数命令支持 `--anthropic-key` 或 `--github-token` 参数。

## 🌐 Multi-Model Support

支持多种 LLM 提供商：

| Provider | 环境变量 | 默认模型 |
|----------|---------|---------|
| Anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 |
| OpenAI | `OPENAI_API_KEY` | gpt-4o |
| Qwen | `OPENAI_API_KEY` | qwen-plus |
| DeepSeek | `OPENAI_API_KEY` | deepseek-chat |

### 配置示例

**使用 Qwen:**
```bash
export LLM_PROVIDER="qwen"
export OPENAI_API_KEY="your-dashscope-api-key"
export DEFAULT_MODEL="qwen-plus"
```

**使用 DeepSeek:**
```bash
export LLM_PROVIDER="deepseek"
export OPENAI_API_KEY="your-deepseek-api-key"
export DEFAULT_MODEL="deepseek-chat"
```

**使用自定义 API:**
```bash
export LLM_PROVIDER="custom"
export LLM_BASE_URL="https://your-api-endpoint/v1"
export OPENAI_API_KEY="your-api-key"
export DEFAULT_MODEL="your-model-name"
```

## 🚀 Usage

### 代理设置（可选）

如果你需要使用代理访问 GitHub：

```bash
# 设置代理
export http_proxy=proxy.example.com:8080
export https_proxy=$http_proxy

# 然后正常运行命令
github-agent create-repo -P . --push
```

### GitHub 仓库工作流

```bash
# 完整工作流: 分析 PRD → 生成代码 → 创建 PR
github-agent run -p requirements.md -r https://github.com/owner/repo

# 仅分析仓库
github-agent analyze -p requirements.md -r https://github.com/owner/repo

# Dry run (不创建实际 PR)
github-agent run -p requirements.md -r https://github.com/owner/repo --dry-run
```

### 本地项目工作流

```bash
# 完整工作流: 分析本地项目 → 生成代码 → 应用更改
github-agent local -p requirements.md -P ./my-project

# 仅分析本地项目
github-agent local-analyze -p requirements.md -P ./my-project

# Dry run (不写入文件)
github-agent local -p requirements.md -P ./my-project --dry-run

# 不创建分支
github-agent local -p requirements.md -P ./my-project --no-branch

# 不自动提交
github-agent local -p requirements.md -P ./my-project --no-commit
```

### GitHub 仓库管理

```bash
# 从本地项目创建 GitHub 仓库（公开）
github-agent create-repo -P ./my-project --name my-awesome-project

# 创建私有仓库
github-agent create-repo -P ./my-project --name my-project --private

# 创建仓库并自动推送本地代码
github-agent create-repo -P ./my-project --name my-project --push

# 创建私有仓库并推送
github-agent create-repo -P ./my-project --name my-project --private --push

# 在当前目录创建仓库并推送（仓库名默认为目录名）
github-agent create-repo --push

# 推送本地项目到已存在的 GitHub 仓库
github-agent push -P ./my-project
```

### 其他命令

```bash
# 查看配置
github-agent config

# 初始化配置
github-agent init

# 查看版本
github-agent --version

# 查看帮助
github-agent --help
```

## 📖 PRD 文档格式

PRD 文档支持 Markdown 格式，建议包含以下内容：

```markdown
# 产品需求文档：功能名称

## 背景
当前存在的问题或需求背景...

## 需求
1. 功能需求 1
2. 功能需求 2

## 技术要求
- 技术栈要求
- 性能要求

## 验收标准
- 验收标准 1
- 验收标准 2
```

## 🏗️ Project Structure

```
github_agent/
├── cli.py                    # CLI 入口
├── config.py                 # 配置管理
├── orchestrator.py           # GitHub 工作流编排
├── models/                   # 数据模型
│   └── __init__.py
├── agents/                   # 代理模块
│   ├── base.py               # 基础代理类
│   ├── repo_understanding.py # 模块1: 仓库理解
│   ├── code_generation.py    # 模块4: 代码生成
│   ├── github_operator.py    # 模块6: GitHub 操作
│   └── local_agent.py        # 本地项目代理
├── tools/                    # 工具模块
│   ├── claude.py             # LLM 客户端
│   ├── github.py             # GitHub API 客户端
│   └── local.py              # 本地文件/git 操作
└── utils/                    # 工具函数
    └── __init__.py
```

## 🔧 Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run linting
ruff check src/

# Run type checking
mypy src/
```

## 📋 Requirements

- Python >= 3.11
- Anthropic API key (for Claude models)
- OR OpenAI-compatible API key (for Qwen, DeepSeek, etc.)
- GitHub Personal Access Token (for GitHub operations)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License - see LICENSE file for details.

---

**Built with ❤️ using Claude Agent SDK**