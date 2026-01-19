# CodeRabbit AI Code Review

This project uses [CodeRabbit](https://coderabbit.ai) for AI-powered code reviews.

## Setup

### 1. Get CodeRabbit API Key

1. Sign up at [coderabbit.ai](https://coderabbit.ai)
2. Connect your GitHub account
3. Copy your API key from the dashboard

### 2. Add API Key to GitHub Secrets

1. Go to your repository settings → Secrets and variables → Actions
2. Add a new secret:
   - Name: `OPENAI_API_KEY` (or `CODERABBIT_API_KEY`)
   - Value: Your CodeRabbit API key

### 3. Configure CodeRabbit

Edit `.coderabbit.yaml` to customize:
- Review profile (chill, balanced, thorough)
- Language-specific rules
- Categories to review
- Files to ignore

## Running Locally

### Install CodeRabbit CLI

```bash
pip install coderabbitai
```

### Run a Review

```bash
# Review all changed files
coderabbit review

# Review specific files
coderabbit review --files backend/api/routes/code.py frontend/src/app/code/page.tsx

# With a specific config
coderabbit review --config .coderabbit.yaml
```

## Review Categories

CodeRabbit reviews for:
- **Security** - Vulnerabilities, secret exposure, injection risks
- **Performance** - Inefficient code, resource leaks
- **Best Practices** - Modern patterns, clean code
- **Bugs** - Potential bugs, edge cases
- **Style** - Code style, naming conventions
- **Documentation** - Missing docs, unclear comments
- **Test Coverage** - Test suggestions

## Configuration Files

| File | Purpose |
|------|---------|
| `.coderabbit.yaml` | Main configuration |
| `.coderabbit/coderabbit_reviews.yaml` | Review rules |

## GitHub Integration

CodeRabbit automatically reviews:
- Pull requests to `main` and `develop`
- Pushes to `main` and `develop`

Results appear as:
- PR comments with line-by-line feedback
- Summary in PR conversation
- Status check on the PR

## Tips

1. **Be specific**: CodeRabbit learns from your feedback on its reviews
2. **Use walkthroughs**: Enable sequence diagrams for complex changes
3. **Customize rules**: Adjust rules in `coderabbit_reviews.yaml`
4. **Ignore files**: Add patterns to `.coderabbit.yaml` ignore list

## Supported Languages

- Python (backend)
- TypeScript/JavaScript (frontend)
- YAML/JSON configs
- Markdown documentation
