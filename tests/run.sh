set -e

export SETUPTOOLS_SCM_PRETEND_VERSION=0


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
    uv venv --python ${PYTHON} $TMPDIR
    echo
    source $TMPDIR/bin/activate
    echo
    uv sync --group lint --group static-type-check --group pytest
    echo
    echo "Lint:"
    ruff check
    echo
    echo "Static type check:"
    mypy
    echo
    echo "Py test:"
    pytest --cov --cov-report=xml --junitxml=junit.xml
    echo
    echo "*****************************************************************"
    echo "End of ${PYTHON} unit-test"
    echo "*****************************************************************"
    echo
done
