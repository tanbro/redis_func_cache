README
######

.. include:: README.include.md
   :parser: myst_parser.sphinx_

How to Build the Documentation
==============================

#. The documentation is built using `Sphinx <https://www.sphinx-doc.org/>`_.
   We need to install the package, Sphinx and some extensions used in the documentation:

   * Using pip:

     .. code:: sh

        pip install -e . --group docs

   * 3rd package managers, such like `uv`_, can be used:

     .. code:: sh

        uv sync --group docs

#. Generate API documentation.
   If the source tree has changed, you may clear the `docs/apidocs` directory and regenerate the API documentation:

   .. code:: sh

      sphinx-apidoc -H "" -feo docs/apidocs src

#. Build HTML documentation:

   * Using the Make tool (for Unix/Linux/macOS):

      .. code:: sh

         make -C docs html

   * On Windows:

      .. code:: bat

         docs\make html

The built static website is located at ``docs/_build/html``. You can serve it with a simple HTTP server:

.. code:: sh

   python -m http.server -d docs/_build/html

Then open http://localhost:8000/ in a web browser.

.. tip::
   Try another port if ``8000`` is already in use.
   For example, to serve on port ``8080``:

   .. code:: sh

      python -m http.server -d docs/_build/html 8080

   .. seealso:: Python ``stdlib``'s :mod:`http.server`


.. _uv: https://docs.astral.sh/uv/
