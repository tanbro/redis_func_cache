#!/bin/bash

set -e

export SETUPTOOLS_SCM_PRETEND_VERSION=0
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_ROOT_USER_ACTION=ignore
export PIP_NO_WARN_SCRIPT_LOCATION=1

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

run_test() {
    local PYTHON=$1
    log "================================================================"
    log "Begin of ${PYTHON} unit-test"
    log "================================================================"

    # Check if Python version exists
    if ! command -v "${PYTHON}" &> /dev/null; then
        log "Warning: ${PYTHON} not found, skipping..."
        return 0
    fi

    TMPDIR=$(mktemp -d)
    trap 'rm -rf "$TMPDIR"' EXIT

    if ! "${PYTHON}" -m venv "$TMPDIR"; then
        log "Error: Failed to create virtual environment with ${PYTHON}"
        return 1
    fi

    log "Installing dependencies..."
    if ! "$TMPDIR/bin/pip" install --no-compile -e .[all] --group test --group mypy ruff ; then
        log "Error: Failed to install dependencies"
        return 1
    fi

    log "Lint check:"
    if ! "$TMPDIR/bin/ruff" check; then
        log "Error: Lint check failed"
        return 1
    fi

    log "Static check:"
    if ! "$TMPDIR/bin/mypy"; then
        log "Error: Static check failed"
        return 1
    fi

    log "Unit test:"
    if ! "$TMPDIR/bin/pytest" -x --cov; then
        log "Error: Unit test failed"
        return 1
    fi

    log "*****************************************************************"
    log "End of ${PYTHON} unit-test: SUCCESS"
    log "*****************************************************************"

    # 清理trap，为下一个循环做准备
    trap - EXIT
    rm -rf "$TMPDIR"
}

PYTHON_LIST=(python3.9 python3.10 python3.11 python3.12 python3.13 python3.14)
for PYTHON in "${PYTHON_LIST[@]}"
do
    echo
    if ! run_test "$PYTHON"; then
        exit 1
    fi
    echo
done
