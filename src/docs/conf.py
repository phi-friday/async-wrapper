# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
from __future__ import annotations

import sys
from os import environ
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent.parent / "src"
sys.path.insert(0, src_dir.as_posix())

__version__ = environ.get("READTHEDOCS_GIT_IDENTIFIER", "")
if not __version__:
    from async_wrapper import __version__

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "async_wrapper"
copyright = "2023, phi.friday"  # noqa: A001
author = "phi.friday"
release = __version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.todo",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx_search.extension",
    "sphinx_rtd_theme",
    "sphinx_mdinclude",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = []

intersphinx_mapping = {"anyio": ("https://anyio.readthedocs.io/en/3.x/", None)}
autodoc_member_order = "bysource"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# napoleon
napoleon_google_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
