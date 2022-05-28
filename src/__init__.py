import re

from aqt import gui_hooks, mw

from . import consts
from .bulk import init_hooks
from .collection_manager import CollectionManager
from .filter import init_filter

collection_manager = CollectionManager()


def open_other_col() -> None:
    mw.copyaround_colman = collection_manager
    other_col_name = consts.CONFIG["other_collection_name"]
    if other_col_name and other_col_name != mw.pm.name:
        collection_manager.open(other_col_name)


init_hooks()
init_filter()
gui_hooks.profile_did_open.append(open_other_col)
gui_hooks.profile_will_close.append(collection_manager.close)
