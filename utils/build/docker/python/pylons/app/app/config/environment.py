"""Pylons environment configuration"""

import os

from mako.lookup import TemplateLookup
from pylons.configuration import PylonsConfig
from pylons.error import handle_mako_error

import app.lib.app_globals as app_globals
import app.lib.helpers
from app.config.routing import make_map


def load_environment(global_conf, app_conf):
    """Configure the Pylons environment via the ``pylons.config``
    object
    """
    config = PylonsConfig()

    # Pylons paths
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = dict(
        root=root,
        controllers=os.path.join(root, "controllers"),
        static_files=os.path.join(root, "public"),
        templates=[os.path.join(root, "templates")],
    )

    # Initialize config with the basic options
    config.init_app(global_conf, app_conf, package="app", paths=paths)

    config["routes.map"] = make_map(config)
    config["pylons.app_globals"] = app_globals.Globals(config)
    config["pylons.h"] = app.lib.helpers
    config["debug"] = False

    # Create the Mako TemplateLookup, with the default auto-escaping
    config["pylons.app_globals"].mako_lookup = TemplateLookup(directories=paths["templates"])

    return config
