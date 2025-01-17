# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import sys
if sys.version_info < (3, 8):
    import importlib_metadata
else:
    import importlib.metadata as importlib_metadata

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'redis_func_cache'
copyright = '2024, Liu Xue Yan'
author = 'Liu Xue Yan'
# full version
version = importlib_metadata.version(project)
# major/minor version
release = ".".join(version.split(".")[:2])

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.githubpages",
    "sphinx.ext.intersphinx",
    "sphinx.ext.graphviz",
    "sphinx.ext.inheritance_diagram",
    "sphinx_tippy",
    "sphinx_inline_tabs",
    "sphinx_copybutton",
    "versionwarning.extension",
    "sphinxcontrib.mermaid",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]
html_theme_options = {
    "source_repository": "https://github.com/tanbro/redis_func_cache",
    "source_branch": "main",
    "source_directory": "docs/",
    "top_of_page_button": "edit",
}

# -- Options for autodoc ----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#configuration
# autodoc_mock_imports = []

# Automatically extract typehints when specified and place them in
# descriptions of the relevant function/method.
autodoc_typehints = "description"

# Don't show class signature with the class' name.
# autodoc_class_signature = "separated"

autoclass_content = "both"


# -- Options for myst_parser extension ---------------------------------------

myst_enable_extensions = [
    "amsmath",
    "attrs_inline",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist"
]
myst_fence_as_directive = ["mermaid"]

# -- Options for intersphinx extension ---------------------------------------

# configuration for intersphinx: refer to the Python standard and/or 3rd libraries.
intersphinx_mapping = {
    "python": ("https://docs.python.org/", None),
    "redis": ("https://redis.readthedocs.io/en/latest/", None),
    "msgpack": ("https://msgpack-python.readthedocs.io/en/latest/", None),
    "pygments": ("https://pygments.org/docs/", None),
}

# -- Options for Napoleon settings ---------------------------------------
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
