# Adapted from https://github.com/Ajatt-Tools/cropro

# Copyright: Ren Tatsumoto <tatsu at autistici.org>
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

import os
from typing import Optional

from anki.collection import Collection
from aqt import mw


class CollectionManager:
    def __init__(self) -> None:
        self._col: Optional[Collection] = None
        self._name: Optional[str] = None

    @property
    def col(self) -> Collection:
        return self._col

    @property
    def name(self) -> Optional[str]:
        return self._name if self._col else None

    @staticmethod
    def _load(name: str) -> Optional[Collection]:
        try:
            return Collection(os.path.join(mw.pm.base, name, "collection.anki2"))
        except:
            return None

    @property
    def is_opened(self) -> bool:
        return self._col is not None

    def close(self) -> None:
        if self.is_opened:
            self._col.close()
            self._name = self._col = None

    def open(self, name: str) -> None:
        self.close()
        self._col = self._load(name)
        self._name = name
