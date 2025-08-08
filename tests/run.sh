set -e

export SETUPTOOLS_SCM_PRETEND_VERSION=0
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_ROOT_USER_ACTION=ignore
export PIP_NO_WARN_SCRIPT_LOCATION=1


PYTHON_LIST=(python3.8 python3.9 python3.10 python3.11 python3.12 python3.13)
for PYTHON in ${PYTHON_LIST[@]}
do
    echo
    echo "================================================================"
    echo "Begin of ${PYTHON} unit-test"
    echo "================================================================"
    echo
    TMPDIR=$(mktemp -d)
    trap 'rm -rf $TMPDIR' EXIT
    ${PYTHON} -m venv $TMPDIR
    echo
    $TMPDIR/bin/pip install --no-compile -e . -r tests/requirements.txt ruff mypy pytest pytest-asyncio pytest-cov types-redis types-PyYAML types-Pygments
    echo
    echo "Lint check:"
    $TMPDIR/bin/ruff check
    echo
    echo "Static check:"
    $TMPDIR/bin/mypy
    echo
    echo "Unit test:"
    $TMPDIR/bin/pytest --cov --cov-report=xml --junitxml=junit.xml
    echo
    echo "*****************************************************************"
    echo "End of ${PYTHON} unit-test"
    echo "*****************************************************************"
    echo
done
