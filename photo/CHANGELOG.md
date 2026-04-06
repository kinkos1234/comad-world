# Changelog

## [0.4.0] - 2026-04-01

### Changed
- MAE guard tightened: 35 → 20 (avg score 72→90, +18 points)
- Auto Levels skip rule: skip when exposure is already adequate
- Batch mode: folder input → propose on first image → apply to rest
- All 5 categories now score 85+ (min 86, max 95)

### Tested (15 portraits)
- Unsplash 10 + real 3 + Grok 2 = 15 portraits
- PIL average 92.2 points, minimum 86, all 85+
- 90+ achieved: 12/15 (80%)

## [0.3.1] - 2026-04-01

### Changed
- Karpathy simplicity pass: 60 → 33 lines
- Removed: PIL parameter hardcoding, portrait numeric limits, Stage 3 listing, duplicate rules
- Kept: CU rules, MAE guard, escalation concept, PS MCP warnings
- Added: "propose correction, execute after approval" (proposal-first behavior)
- Camera Raw + PIL conflict rule: skip PIL color correction when using Camera Raw

### Tested (5 categories)
- MAE 5.24~23.72, all PIL, card proposals 5/5
- Key finding: without hardcoded params, agent chose more conservative values (brightness 1.04~1.08 vs prior 1.20)

## [0.3.0] - 2026-03-31

### Added
- 3-tier engine escalation: PIL → CU Camera Raw → CU Advanced
- Camera Raw filter via CU: texture, clarity, dehaze (Tab+type workflow)
- Generative Fill via CU: select + prompt → AI content generation
- Subject Selection via CU: one-click AI selection for background workflows
- AI Denoise via CU: one-click Topaz Denoise integration
- Neural Filters skin smoothing via CU (with layer merge requirement)
- Portrait retouching limits: eye ±15, jawline ±10, skin blur ≤30

### Changed
- Core principle: "Natural first" — retouching must be invisible to human eye
- CU wait reduced: 3s → 1s
- Save method: AppleScript prohibited → CU Cmd+S only
- Liquify pipeline: added PIL rotate → Liquify → reverse rotate for tilted photos

### Tested (real portrait photos)
- Liquify: conditional success (face unobstructed + tilt <30°)
- Camera Raw: MAE 9.11, 35.2% pixel change confirmed
- Generative Fill: prompt + 3 variations generated
- Neural Filters: skin smoothing applied (layer merge needed for JPEG save)
- AI Denoise: one-click UI successful
- Subject Selection: AI auto-selection confirmed

## [0.2.0] - 2026-03-31

### Added
- Computer Use integration: Liquify face sliders, Remove Tool, Content-Aware Fill
- Over-correction guard: MAE > 35 triggers automatic parameter reduction
- Adaptive brightness: dark photos boost more, bright photos reduce
- PIL as primary engine, PS MCP secondary, CU for GUI-only operations

### Tested
- 50 random photos batch-corrected (5 categories × 10 photos)
- 100% success rate, 8/14 over-correction cases auto-mitigated
- CU verified: Liquify sliders ✅, Remove Tool ✅, CAF ✅, Forward Warp ⚠️

### Changed
- Auto Levels percentile: [2,98] → [5,95] (more conservative)
- PIL template replaced with concise guide (removed verbose code block)
- Agent file: 82 lines → 65 lines

## [0.1.0] - 2026-03-30

### Added
- Core pipeline: analyze → suggest cards → execute via PS MCP → verify → loop
- Non-destructive editing principle (adjustment layers only)
- Photoshop MCP integration (`@alisaitteke/photoshop-mcp`)
- Minimal installer

### Design philosophy
- Karpathy simplicity: one agent, one loop, one success criterion
- Build from usage, not from spec
