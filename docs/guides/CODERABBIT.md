# CodeRabbit AI Code Review

This project uses [CodeRabbit](https://coderabbit.ai) for AI-powered code reviews.

## Setup

### 1. Install CodeRabbit GitHub App

1. Go to [coderabbit.ai](https://coderabbit.ai)
2. Click "Connect GitHub" and authorize the app
3. Select this repository: `Smart-Tutor-AI-AI-Driven-Personalized-Teaching-Support`
4. Configure review settings in the CodeRabbit dashboard

### 2. API Key Setup (Optional for CLI)

Get your API key from [coderabbit.ai](https://coderabbit.ai) → Settings → API Key

Add to GitHub secrets:
- **Name**: `OPENAI_API_KEY` (or `CODERABBIT_API_KEY`)
- **Value**: Your CodeRabbit API key

### 3. Configure Review Rules

Edit `.coderabbit.yaml` to customize:
- Review profile (chill, balanced, thorough)
- Language-specific rules
- Categories to review
- Files to ignore

## Features

| Feature | Description |
|---------|-------------|
| **Line-by-line review** | AI analyzes each changed file |
| **Security scanning** | Finds vulnerabilities and secrets |
| **Performance tips** | Suggests optimizations |
| **Bug detection** | Identifies potential bugs |
| **Style suggestions** | Code style improvements |
| **Sequence diagrams** | Visualizes complex logic |

## GitHub Integration

Once the GitHub App is connected, CodeRabbit will automatically:

1. **Review PRs** - Adds comments on changed files
2. **Post summary** - Overview of findings in PR conversation
3. **Show walkthroughs** - Sequence diagrams for complex changes
4. **Track suggestions** - Mark suggestions as resolved

## Configuration Files

| File | Purpose |
|------|---------|
| `.coderabbit.yaml` | Main configuration |
| `.coderabbit/coderabbit_reviews.yaml` | Review rules |
| `.github/workflows/coderabbit.yml` | CI/CD workflow (placeholder) |

## Supported Languages

- **Python** - Backend APIs, scripts
- **TypeScript/JavaScript** - Frontend React components
- **YAML/JSON** - Config files
- **Markdown** - Documentation

## Review Categories

CodeRabbit checks for:

| Category | What it catches |
|----------|-----------------|
| **Security** | Hardcoded secrets, SQL injection, unsafe deserialization |
| **Performance** | Inefficient loops, N+1 queries, missing caching |
| **Best Practices** | Type hints, docstrings, context managers |
| **Bugs** | Null handling, edge cases, exception types |
| **Style** | Naming conventions, code organization |
| **Tests** | Test coverage gaps, missing assertions |
| **Documentation** | Unclear comments, missing docstrings |

## Tips

1. **Respond to reviews**: CodeRabbit learns from your feedback
2. **Use walkthroughs**: Enable for complex refactoring PRs
3. **Customize rules**: Adjust rules in `coderabbit_reviews.yaml`
4. **Ignore files**: Add patterns to `.coderabbit.yaml` ignore list

## Troubleshooting

### CodeRabbit not reviewing PRs?

1. Check GitHub App permissions in repository settings
2. Verify repository is connected in CodeRabbit dashboard
3. Ensure PR is open (not draft)

### Want CLI reviews?

```bash
# Install via npm (if available)
npm install -g @coderabbitai/cli

# Or use via npx
npx @coderabbitai/cli review
```

## Example Review Output

```
📝 Code Review Summary

🐰 CodeRabbit reviewed 12 files

✅ Found 3 suggestions:
  • security: Use environment variables for API keys
  • performance: Cache database connections
  • style: Rename 'calc' to 'calculate_total'

📊 Categories:
  security: 1 warning
  performance: 1 suggestion
  best_practices: 1 info
```
