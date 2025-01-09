"""Jinja2 environment for the Open WebUI."""

from jinja2 import Environment, PackageLoader, select_autoescape

env = Environment(
    loader=PackageLoader("open_webui"),
    autoescape=select_autoescape(),
)
