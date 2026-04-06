# QA — Browser-Based Quality Assurance

Triggered by "QA해줘", "qa", "테스트해봐", "사이트 확인", or after any web frontend build.
Uses `comad-browse` for headless browser testing.

## Prerequisites

```bash
cd browse && bun install   # install comad-browse once
```

## How It Works

### Phase 1: Discovery
1. Detect dev server (check ports 3000, 5173, 8080, 4321, or user-specified URL)
2. `browse goto {url}` → take initial screenshot
3. `browse snapshot -i` → map all interactive elements

### Phase 2: Systematic Testing

**Navigation Test:**
- Click every link (`browse click @eN`), verify no 404/500
- Check back/forward navigation works
- Verify all routes render content (not blank pages)

**Form Test:**
- Find all forms (`browse snapshot -i` → filter textbox/button)
- Fill with valid data → submit → verify success
- Fill with invalid data → verify error handling
- Test empty submission → verify validation

**Responsive Test:**
- `browse viewport 1920 1080` → screenshot (desktop)
- `browse viewport 768 1024` → screenshot (tablet)
- `browse viewport 375 812` → screenshot (mobile)
- Compare layouts for obvious breakage

**Console Error Check:**
- After each page load, check for JS errors
- Report any uncaught exceptions or failed network requests

**Performance Check:**
- Measure page load time per route
- Flag pages taking > 3 seconds
- Check for oversized images (> 500KB)

### Phase 3: Report

Output structured report:
```
## QA Report — {url}
Date: {timestamp}
Pages tested: {count}
Health score: {score}/100

### Critical Issues
- [FAIL] /login — form submit returns 500
- [FAIL] /dashboard — uncaught TypeError in console

### Warnings
- [WARN] /about — loads in 4.2s (threshold: 3s)
- [WARN] /gallery — image hero.jpg is 2.1MB

### Passed
- [PASS] Navigation: all 12 links resolve
- [PASS] Mobile viewport: no horizontal overflow
- [PASS] Forms: 3/3 forms validate correctly
```

### Phase 4: Fix (optional)

If `--fix` flag or user confirms:
1. Fix each issue in source code
2. Commit atomically per fix
3. Re-run QA to verify fix
4. Loop until health score > 90

## Integration with voice

When voice detects QA trigger:
1. Auto-detect running dev server
2. Run Phase 1-3
3. Present report as improvement cards
4. User picks which to fix → Phase 4

## CLI Usage (standalone)

```bash
# QA a running dev server
browse goto http://localhost:3000
# Then ask Claude to read voice/qa.md and run the QA process

# QA a deployed site
browse goto https://your-site.com
```

## Configuration (optional)

Add to `comad.config.yaml`:
```yaml
qa:
  dev_ports: [3000, 5173, 8080]
  load_time_threshold: 3000  # ms
  image_size_threshold: 512000  # bytes
  viewport_sizes:
    - { name: desktop, width: 1920, height: 1080 }
    - { name: tablet, width: 768, height: 1024 }
    - { name: mobile, width: 375, height: 812 }
```
