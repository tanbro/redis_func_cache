#!/bin/bash

set -e

export SETUPTOOLS_SCM_PRETEND_VERSION=0

# uv 不读取任何 PIP_* 环境变量：把 pip 配置的镜像源映射给 uv
if [ -z "${UV_DEFAULT_INDEX:-}" ] && [ -n "${PIP_INDEX_URL:-}" ]; then
    export UV_DEFAULT_INDEX="${PIP_INDEX_URL}"
fi

# manylinux 基础镜像已自带全部所需 Python，禁止 uv 额外下载
export UV_PYTHON_DOWNLOADS=never

# coverage 数据放 /tmp：工作区 bind mount 里可能有宿主机（Windows）跑测试留下的
# .coverage，其绝对路径在容器里无法解析，会产生大量 couldn't-parse 警告
export COVERAGE_FILE=/tmp/.coverage

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

# uv.lock 不进 SCM（gitignore *.lock）：首次运行生成一次，
# 之后 uv run --frozen 全程只读使用，绝不改写
if [ ! -f uv.lock ]; then
    log "Generating uv.lock..."
    uv lock
fi

# lint 与被测 Python 版本无关，只跑一次；
# --ignore EXE002：Windows bind mount 会给所有文件加可执行位，导致该规则在容器里全量误报
log "Lint check:"
uvx ruff check --ignore EXE002

# mypy 需要 项目源码 + 依赖的类型信息，必须在 sync 过 typing 组的环境里跑；
# 同样持久化到 /venvs，跨次运行增量复用
log "Static check:"
UV_PROJECT_ENVIRONMENT="/venvs/typing" uv run --frozen --no-dev --group typing mypy

read -r -a PYTHON_LIST <<< "${PYTHON_LIST:-3.10 3.11 3.12 3.13 3.14}"
for PYTHON in "${PYTHON_LIST[@]}"; do
    log "================================================================"
    log "Begin of Python ${PYTHON} pytest"
    log "================================================================"

    # 各版本固定独立路径，配合容器里的 volume 跨次运行增量复用
    export UV_PROJECT_ENVIRONMENT="/venvs/${PYTHON}"

    # uv run 自动完成 sync，失败时 set -e 会带着 uv 的真实退出码退出
    uv run --python "${PYTHON}" --frozen --all-extras --no-dev --group test pytest --cov

    log "*****************************************************************"
    log "End of Python ${PYTHON} pytest: SUCCESS"
    log "*****************************************************************"
    echo
done
