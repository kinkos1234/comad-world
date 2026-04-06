// Preset definitions — mirrors presets/*.yaml in comad-world
export const PRESETS = [
  {
    value: 'ai-ml',
    title: 'AI / Machine Learning',
    description: 'LLMs, deep learning, computer vision, robotics, AI safety',
    file: 'ai-ml.yaml',
  },
  {
    value: 'web-dev',
    title: 'Web Development',
    description: 'Frontend frameworks, backend APIs, DevOps, JS/TS ecosystem',
    file: 'web-dev.yaml',
  },
  {
    value: 'finance',
    title: 'Finance / Fintech',
    description: 'Quantitative finance, crypto, DeFi, trading systems',
    file: 'finance.yaml',
  },
  {
    value: 'biotech',
    title: 'Biotech / Life Sciences',
    description: 'Drug discovery, genomics, computational biology',
    file: 'biotech.yaml',
  },
  {
    value: 'custom',
    title: 'Custom',
    description: 'Start from a blank config and define your own interests',
    file: null,
  },
];

export const SCOPES = [
  {
    value: 'full',
    title: 'Full  (brain + ear + eye)',
    description: 'Knowledge graph, Discord curator, simulation engine',
  },
  {
    value: 'lite',
    title: 'Lite  (brain only)',
    description: 'Knowledge graph + MCP server — no extras',
  },
  {
    value: 'minimal',
    title: 'Minimal  (brain MCP only)',
    description: 'MCP server only — no Docker needed',
  },
];
