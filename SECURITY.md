# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| latest  | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT open a public GitHub issue**
2. Email: [create a private security advisory](../../security/advisories/new) on this repository
3. Include: description, steps to reproduce, potential impact

We will acknowledge your report within 48 hours and provide a timeline for a fix.

## Security Considerations

### API Keys
- `ANTHROPIC_API_KEY` — used by brain module for entity extraction
- `GITHUB_TOKEN` — used by brain module for GitHub crawling (optional)
- `NEO4J_PASSWORD` — database authentication

**Never commit `.env` files.** Use `.env.example` as a template.

### Data Privacy
- Brain module stores crawled content in Neo4j locally
- Ear module archives articles to local markdown files
- No data is sent to external services except the configured LLM API

### Dependencies
- Run `bun audit` (brain) and `pip audit` (eye) regularly
- Pin dependency versions in production deployments
