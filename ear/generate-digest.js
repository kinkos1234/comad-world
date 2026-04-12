#!/usr/bin/env node
// generate-digest.js — Auto-generate daily digest from archive markdown files
// No external dependencies. Reads archive/*.md, writes digests/{date}-digest.html
// Designed to run via cron: 0 8 * * * node /path/to/generate-digest.js

const fs = require('fs');
const path = require('path');

const EAR_DIR = __dirname;
const ARCHIVE_DIR = path.join(EAR_DIR, 'archive');
const DIGESTS_DIR = path.join(EAR_DIR, 'digests');
const TEMPLATE_PATH = path.join(EAR_DIR, 'digest-template.html');
const LOG_PATH = path.join(EAR_DIR, 'digest.log');

function log(msg) {
  const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
  const line = `${ts} ${msg}\n`;
  fs.appendFileSync(LOG_PATH, line);
  console.log(line.trim());
}

// Target date: yesterday in LOCAL timezone (or pass YYYY-MM-DD as arg).
// toISOString() returns UTC, which shifts the date by -1 when the cron fires
// at local 08:00 KST (UTC 23:00 previous day) — caused digests 04-10/04-11 to
// be skipped because the script computed "2 days ago" instead of "yesterday".
const targetDate = process.argv[2] || (() => {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
})();

const digestPath = path.join(DIGESTS_DIR, `${targetDate}-digest.html`);

// Skip if already exists and > 1KB
if (fs.existsSync(digestPath) && fs.statSync(digestPath).size > 1024) {
  log(`[SKIP] Digest already exists: ${digestPath}`);
  process.exit(0);
}

// Find archive files for target date
const archiveFiles = fs.readdirSync(ARCHIVE_DIR)
  .filter(f => f.startsWith(targetDate) && f.endsWith('.md'))
  .sort();

if (archiveFiles.length === 0) {
  log(`[SKIP] No archive files for ${targetDate}`);
  process.exit(0);
}

log(`Generating digest for ${targetDate} (${archiveFiles.length} articles)...`);

// Parse frontmatter and body from markdown
function parseArticle(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const fmMatch = content.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!fmMatch) return null;

  const fm = {};
  fmMatch[1].split('\n').forEach(line => {
    const colonIdx = line.indexOf(':');
    if (colonIdx === -1) return;
    const key = line.slice(0, colonIdx).trim();
    let val = line.slice(colonIdx + 1).trim();
    // Parse arrays: [a, b, c]
    if (val.startsWith('[') && val.endsWith(']')) {
      val = val.slice(1, -1).split(',').map(s => s.trim());
    }
    fm[key] = val;
  });

  const body = fmMatch[2];

  // Extract title (first # heading)
  const titleMatch = body.match(/^# (.+)$/m);
  const title = titleMatch ? titleMatch[1].trim() : path.basename(filePath, '.md');

  // Extract 핵심 요약 bullets
  const summaryMatch = body.match(/## 핵심 요약\n([\s\S]*?)(?=\n## |$)/);
  const bullets = [];
  if (summaryMatch) {
    summaryMatch[1].split('\n').forEach(line => {
      const trimmed = line.replace(/^- /, '').trim();
      if (trimmed.length > 0) bullets.push(trimmed);
    });
  }

  // Extract 왜 알아야 하는가
  const whyMatch = body.match(/## 왜 알아야 하는가\n([\s\S]*?)(?=\n## |$)/);
  const why = whyMatch ? whyMatch[1].trim() : '';

  return {
    title,
    relevance: fm.relevance || '참고',
    categories: Array.isArray(fm.categories) ? fm.categories : [],
    geeknews: fm.geeknews || '',
    source: fm.source || '',
    bullets,
    why
  };
}

// Parse all articles
const articles = archiveFiles
  .map(f => parseArticle(path.join(ARCHIVE_DIR, f)))
  .filter(Boolean);

// Sort: 필독 → 추천 → 참고
const relevanceOrder = { '필독': 0, '추천': 1, '참고': 2 };
articles.sort((a, b) => (relevanceOrder[a.relevance] ?? 2) - (relevanceOrder[b.relevance] ?? 2));

// Count by relevance
const mustCount = articles.filter(a => a.relevance === '필독').length;
const recommendCount = articles.filter(a => a.relevance === '추천').length;
const noteCount = articles.filter(a => a.relevance === '참고').length;

// Generate article HTML blocks
function relevanceClass(r) {
  if (r === '필독') return 'must';
  if (r === '추천') return 'recommend';
  return 'note';
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

const articlesHtml = articles.map(a => {
  const bulletsHtml = a.bullets.map(b => `      <li>${escapeHtml(b)}</li>`).join('\n');
  const tagsHtml = a.categories.map(c => `<span class="tag">${escapeHtml(c)}</span>`).join(' ');

  const linksHtml = [
    a.source ? `<a href="${escapeHtml(a.source)}" target="_blank">원문</a>` : '',
    a.geeknews ? `<a href="${escapeHtml(a.geeknews)}" target="_blank">GeekNews</a>` : ''
  ].filter(Boolean).join(' ');

  return `  <article class="article">
    <div class="article-header">
      <span class="relevance-indicator ${relevanceClass(a.relevance)}"></span>
      <a href="${escapeHtml(a.geeknews || a.source || '#')}" class="article-title" target="_blank">${escapeHtml(a.title)}</a>
    </div>
    <div class="article-meta">${tagsHtml}</div>
    <div class="article-summary">
      <ul>
${bulletsHtml}
      </ul>
    </div>
${a.why ? `    <div class="article-why">${escapeHtml(a.why)}</div>` : ''}
    <div class="article-links">${linksHtml}</div>
  </article>`;
}).join('\n\n');

// Read template and replace placeholders
let template = fs.readFileSync(TEMPLATE_PATH, 'utf8');
template = template
  .replace(/\{\{DATE\}\}/g, targetDate)
  .replace(/\{\{MUST_COUNT\}\}/g, String(mustCount))
  .replace(/\{\{RECOMMEND_COUNT\}\}/g, String(recommendCount))
  .replace(/\{\{NOTE_COUNT\}\}/g, String(noteCount))
  .replace(/\{\{TOTAL_COUNT\}\}/g, String(articles.length))
  .replace('{{ARTICLES}}', articlesHtml);

// Ensure digests directory exists
if (!fs.existsSync(DIGESTS_DIR)) {
  fs.mkdirSync(DIGESTS_DIR, { recursive: true });
}

fs.writeFileSync(digestPath, template, 'utf8');
log(`✓ Digest generated: ${digestPath} (${articles.length} articles)`);
