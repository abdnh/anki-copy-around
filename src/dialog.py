from concurrent.futures import Future
from typing import List, Optional

import anki
from anki.decks import DeckId
from aqt.qt import *
from aqt.main import AnkiQt
from aqt.deckchooser import DeckChooser
from anki.notes import Note
from anki.utils import stripHTML

from .form import Ui_Dialog
from . import consts

ANKI_POINT_VERSION = int(anki.version.split(".")[-1])


PROGRESS_LABEL = "Processed {count} out of {total} note(s)"


class MyDeckChooser(DeckChooser):

    onDeckChanged = pyqtSignal(object)

    def choose_deck(self) -> None:
        super().choose_deck()
        self.onDeckChanged.emit(self.selectedId())


class CopyAroundDialog(QDialog):
    def __init__(self, mw: AnkiQt, parent, notes: List[Note]):
        super().__init__(parent)
        self.mw = mw
        self.config = mw.addonManager.getConfig(__name__)
        self.notes = notes
        self.setup_ui()

    def setup_ui(self):
        self.form = Ui_Dialog()
        self.form.setupUi(self)
        self.setWindowTitle(consts.ADDON_NAME)
        # StudyDeck, which is used by DeckChooser, is asynchronous in 2.1.50
        if ANKI_POINT_VERSION >= 50:
            self.deckChooser = MyDeckChooser(
                self.mw,
                self.form.deckChooser,
                label=False,
                on_deck_changed=self._update_dest_fields,
            )
        else:
            self.deckChooser = MyDeckChooser(
                self.mw, self.form.deckChooser, label=False
            )
            qconnect(self.deckChooser.onDeckChanged, self._update_dest_fields)
        qconnect(self.form.copyButton.clicked, self.on_copy)
        qconnect(
            self.form.matchedNotesLimitCheckBox.toggled,
            lambda t: self.form.matchedNotesSpinBox.setEnabled(t),
        )
        self.src_fields = []
        for note in self.notes:
            for field in note.keys():
                if field not in self.src_fields:
                    self.src_fields.append(field)
        self.form.searchFieldComboBox.addItems(self.src_fields)
        self.form.copyIntoFieldComboBox.addItems(self.src_fields)
        self._update_dest_fields(self.deckChooser.selectedId())

    def exec(self) -> int:
        copy_from_deck = self.mw.col.decks.by_name(self.config["copy_from_deck"])
        if copy_from_deck:
            self.deckChooser.selected_deck_id = copy_from_deck["id"]
            self._update_dest_fields(copy_from_deck["id"])

        matched_notes_limit = self.config["matched_notes_limit"]
        if matched_notes_limit > 0:
            self.form.matchedNotesLimitCheckBox.setChecked(True)
            self.form.matchedNotesSpinBox.setValue(matched_notes_limit)

        search_field = self.config["search_field"]
        if search_field := self._get_field(self.src_fields, search_field):
            self.form.searchFieldComboBox.setCurrentText(search_field)

        copy_into_field = self.config["copy_into_field"]
        if copy_into_field := self._get_field(self.src_fields, copy_into_field):
            self.form.copyIntoFieldComboBox.setCurrentText(copy_into_field)
        else:
            self.form.copyIntoFieldComboBox.setCurrentIndex(1)

        copy_from_field = self.config["copy_from_field"]
        if copy_from_field := self._get_field(self.dest_fields, copy_from_field):
            self.form.copyFromFieldComboBox.setCurrentText(copy_from_field)

        return super().exec()

    def _get_field(self, fields: List[str], key) -> Optional[str]:
        for field in fields:
            if key.lower() == field.lower():
                return field
        return None

    def _update_dest_fields(self, dest_did: DeckId):
        self.dest_fields: List[str] = []
        for nid in self.mw.col.find_notes(f"did:{dest_did}"):
            note = self.mw.col.get_note(nid)
            for field in note.keys():
                if field not in self.dest_fields:
                    self.dest_fields.append(field)
        self.form.copyFromFieldComboBox.clear()
        self.form.copyFromFieldComboBox.addItems(self.dest_fields)

    def _preprocess_search(self, text: str) -> str:
        text = stripHTML(text)
        text = text.replace("\\", "\\\\")
        text = text.replace(":", "\\:")
        text = text.replace('"', '\\"')
        return f'"{text}"'

    def _process_notes(
        self,
        did: DeckId,
        search_field: str,
        copy_into_field: str,
        copy_from_field: str,
        matched_notes_count: int,
    ):
        self.updated_notes = []
        for i, note in enumerate(self.notes):
            if i % 20:
                self.mw.taskman.run_on_main(
                    lambda: self.mw.progress.update(
                        label=PROGRESS_LABEL.format(count=0, total=len(self.notes)),
                        value=i + 1,
                    )
                )
            search_for = self._preprocess_search(note[search_field])
            query = self.mw.col.build_search_string(f"did:{did}", search_for)
            nids = self.mw.col.find_notes(query)
            if not nids:
                continue
            if matched_notes_count > 0:
                nids = nids[:matched_notes_count]
            copied = []
            for nid in nids:
                dest_note = self.mw.col.get_note(nid)
                if copy_from_field not in dest_note:
                    continue
                copied.append(dest_note[copy_from_field])
            note[copy_into_field] = "<br>".join(copied)
            self.updated_notes.append(note)

    def on_copy(self):
        search_field = self.src_fields[self.form.searchFieldComboBox.currentIndex()]
        copy_into_field = self.src_fields[
            self.form.copyIntoFieldComboBox.currentIndex()
        ]
        did = self.deckChooser.selectedId()
        copy_from_field = self.dest_fields[
            self.form.copyFromFieldComboBox.currentIndex()
        ]
        matched_notes_count = (
            self.form.matchedNotesSpinBox.value()
            if self.form.matchedNotesLimitCheckBox.isChecked()
            else -1
        )

        # save options
        self.config["search_field"] = search_field
        self.config["copy_into_field"] = copy_into_field
        self.config["copy_from_deck"] = self.mw.col.decks.get(did)["name"]
        self.config["copy_from_field"] = copy_from_field
        self.config["matched_notes_limit"] = matched_notes_count
        self.mw.addonManager.writeConfig(__name__, self.config)

        def on_done(fut: Future):
            try:
                fut.result()
            finally:
                self.mw.taskman.run_on_main(lambda: self.mw.progress.finish())
            self.accept()

        self.mw.progress.start(
            max=len(self.notes),
            label=PROGRESS_LABEL.format(count=0, total=len(self.notes)),
            parent=self,
        )
        self.mw.progress.set_title(consts.ADDON_NAME)
        self.mw.taskman.run_in_background(
            lambda: self._process_notes(
                did,
                search_field,
                copy_into_field,
                copy_from_field,
                matched_notes_count,
            ),
            on_done=on_done,
        )
