#!/bin/zsh
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"
export SHELL="/bin/zsh"
export USER="jhkim"
export TERM="xterm-256color"
cd "$HOME/Programmer/01-comad/comad-world/brain"
bun run packages/ingester/src/geeknews-importer.ts --incremental
