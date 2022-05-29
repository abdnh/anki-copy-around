import os

import anki
from aqt import gui_hooks, mw

from . import consts
from .bulk import init_hooks
from .collection_manager import CollectionManager
from .filter import init_filter

collection_manager = CollectionManager()
ANKI_VERSION = tuple(int(p) for p in anki.version.split("."))  # type: ignore


def open_other_col() -> None:
    mw.copyaround_colman = collection_manager
    other_col_name = consts.CONFIG["other_collection_name"]
    if other_col_name and other_col_name != mw.pm.name:
        collection_manager.open(other_col_name)
        if ANKI_VERSION < (2, 1, 50):
            # work around MediaManager changing working directory and breaking audio playback after we open the other collection
            # https://github.com/ankitects/anki/pull/1630
            os.chdir(mw.col.media.dir())


init_hooks()
init_filter()
gui_hooks.profile_did_open.append(open_other_col)
gui_hooks.profile_will_close.append(collection_manager.close)
