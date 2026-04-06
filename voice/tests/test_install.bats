#!/usr/bin/env bats
# Tests for Comad Voice install.sh
# Run: bats tests/test_install.bats

setup() {
    # Create a temporary home directory for each test
    export ORIG_HOME="$HOME"
    export HOME="$(mktemp -d)"
    export CLAUDE_DIR="$HOME/.claude"
    export CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"

    # Get the project root
    export PROJECT_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)"

    # Create minimal CLAUDE.md
    mkdir -p "$CLAUDE_DIR"
    echo "# Claude Code Config" > "$CLAUDE_MD"
}

teardown() {
    # Clean up temporary home
    if [ -d "$HOME" ] && [ "$HOME" != "$ORIG_HOME" ]; then
        rm -rf "$HOME"
    fi
    export HOME="$ORIG_HOME"
}

# ─── Prerequisite checks ───

@test "fails if claude command not found" {
    # Temporarily hide claude from PATH
    PATH="/usr/bin:/bin" run bash "$PROJECT_ROOT/install.sh" <<< "n"
    [ "$status" -ne 0 ]
    [[ "$output" == *"Claude Code not found"* ]]
}

# ─── Fresh install ───

@test "fresh install appends config to CLAUDE.md" {
    # Skip if claude not available
    if ! command -v claude &> /dev/null; then
        skip "claude command not available"
    fi

    run bash "$PROJECT_ROOT/install.sh" <<< "n"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Added Comad Voice to CLAUDE.md"* ]]

    # Verify markers exist
    grep -q "COMAD-VOICE:START" "$CLAUDE_MD"
    grep -q "COMAD-VOICE:END" "$CLAUDE_MD"
}

@test "fresh install creates backup" {
    if ! command -v claude &> /dev/null; then
        skip "claude command not available"
    fi

    run bash "$PROJECT_ROOT/install.sh" <<< "n"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Backup created"* ]]

    # Verify backup file exists
    backup_count=$(ls "$CLAUDE_MD".bak.* 2>/dev/null | wc -l)
    [ "$backup_count" -ge 1 ]
}

# ─── Update install ───

@test "update install detects existing and asks to overwrite" {
    if ! command -v claude &> /dev/null; then
        skip "claude command not available"
    fi

    # First install
    bash "$PROJECT_ROOT/install.sh" <<< "n"

    # Second install - answer 'n' to overwrite, 'n' to memory
    run bash "$PROJECT_ROOT/install.sh" <<< $'n\nn'
    [ "$status" -eq 0 ]
    [[ "$output" == *"already installed"* ]]
}

@test "update install overwrites when confirmed" {
    if ! command -v claude &> /dev/null; then
        skip "claude command not available"
    fi

    # First install
    bash "$PROJECT_ROOT/install.sh" <<< "n"

    # Add a marker to detect replacement
    old_content=$(cat "$CLAUDE_MD")

    # Second install - answer 'y' to overwrite, 'n' to memory
    run bash "$PROJECT_ROOT/install.sh" <<< $'y\nn'
    [ "$status" -eq 0 ]
    [[ "$output" == *"Updated CLAUDE.md"* ]]

    # Verify markers still exist (not duplicated)
    marker_count=$(grep -c "COMAD-VOICE:START" "$CLAUDE_MD")
    [ "$marker_count" -eq 1 ]
}

# ─── Memory templates ───

@test "memory templates are copied when accepted" {
    if ! command -v claude &> /dev/null; then
        skip "claude command not available"
    fi

    cd "$HOME"
    run bash "$PROJECT_ROOT/install.sh" <<< "y"
    [ "$status" -eq 0 ]

    # Memory dir should be created
    SAFE_PATH=$(echo "$HOME" | sed 's|/|-|g' | sed 's|^-||')
    MEMORY_DIR="$CLAUDE_DIR/projects/$SAFE_PATH/memory"
    [ -f "$MEMORY_DIR/MEMORY.md" ]
    [ -f "$MEMORY_DIR/experiments.md" ]
    [ -f "$MEMORY_DIR/architecture.md" ]
}

@test "memory templates are not overwritten if they exist" {
    if ! command -v claude &> /dev/null; then
        skip "claude command not available"
    fi

    cd "$HOME"
    SAFE_PATH=$(echo "$HOME" | sed 's|/|-|g' | sed 's|^-||')
    MEMORY_DIR="$CLAUDE_DIR/projects/$SAFE_PATH/memory"
    mkdir -p "$MEMORY_DIR"
    echo "# My custom memory" > "$MEMORY_DIR/MEMORY.md"

    run bash "$PROJECT_ROOT/install.sh" <<< "y"
    [ "$status" -eq 0 ]
    [[ "$output" == *"already exists"* ]]

    # Verify custom content is preserved
    grep -q "My custom memory" "$MEMORY_DIR/MEMORY.md"
}

# ─── File structure ───

@test "core/comad-voice.md exists and has markers" {
    [ -f "$PROJECT_ROOT/core/comad-voice.md" ]
    grep -q "COMAD-VOICE:START" "$PROJECT_ROOT/core/comad-voice.md"
    grep -q "COMAD-VOICE:END" "$PROJECT_ROOT/core/comad-voice.md"
}

@test "trigger modules exist" {
    [ -f "$PROJECT_ROOT/core/triggers/t1-review.md" ]
    [ -f "$PROJECT_ROOT/core/triggers/t2-fullcycle.md" ]
    [ -f "$PROJECT_ROOT/core/triggers/t3-parallel.md" ]
    [ -f "$PROJECT_ROOT/core/triggers/t4-polish.md" ]
}

@test "memory templates exist" {
    [ -f "$PROJECT_ROOT/memory-templates/MEMORY.md" ]
    [ -f "$PROJECT_ROOT/memory-templates/experiments.md" ]
    [ -f "$PROJECT_ROOT/memory-templates/architecture.md" ]
}

@test "install.sh is executable" {
    [ -x "$PROJECT_ROOT/install.sh" ]
}

@test "install.sh passes shellcheck" {
    if ! command -v shellcheck &> /dev/null; then
        skip "shellcheck not available"
    fi
    run shellcheck "$PROJECT_ROOT/install.sh"
    [ "$status" -eq 0 ]
}
