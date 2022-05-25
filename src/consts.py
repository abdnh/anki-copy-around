import os

from aqt import mw

ADDON_NAME = "Copy Around"
ADDON_DIR = os.path.dirname(__file__)
ADDON_PACKAGE = os.path.basename(ADDON_DIR)
ICONS_DIR = os.path.join(ADDON_DIR, "icons")
FILTER_NAME = "copyaround"
CONFIG = mw.addonManager.getConfig(__name__)
