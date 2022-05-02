from concurrent.futures import Future
from typing import List, Optional

import anki
from anki.decks import DeckId
from aqt.qt import *
from aqt import qtmajor
from aqt.main import AnkiQt
from aqt.deckchooser import DeckChooser
from anki.notes import Note
from aqt.utils import showWarning

if qtmajor > 5:
    from .form_qt6 import Ui_Dialog
else:
    from .form_qt5 import Ui_Dialog  # type: ignore
from . import consts
from .copy_around import get_related_content, escape_search_term

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
        qconnect(
            self.form.searchInFieldCheckBox.toggled,
            lambda t: self.form.searchInFieldComboBox.setEnabled(t),
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
        mids = set(note.mid for note in self.notes)
        if len(mids) > 1:
            showWarning(
                "Please select notes from only one notetype.",
                parent=self,
                title=consts.ADDON_NAME,
            )
            return 0
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

        search_in_field = self.config["search_in_field"]
        if search_in_field := self._get_field(self.dest_fields, search_in_field):
            self.form.searchInFieldCheckBox.setChecked(True)
            self.form.searchInFieldComboBox.setCurrentText(search_in_field)

        randomize_results = self.config["randomize_results"]
        self.form.randomizeCheckBox.setChecked(randomize_results)

        return super().exec()

    def _get_field(self, fields: List[str], key) -> Optional[str]:
        for field in fields:
            if key.lower() == field.lower():
                return field
        return None

    def _update_dest_fields(self, dest_did: DeckId):
        self.dest_fields: List[str] = []
        deck = escape_search_term(self.mw.col.decks.get(dest_did)["name"])
        for nid in self.mw.col.find_notes(f"deck:{deck}"):
            note = self.mw.col.get_note(nid)
            for field in note.keys():
                if field not in self.dest_fields:
                    self.dest_fields.append(field)
        self.form.copyFromFieldComboBox.clear()
        self.form.copyFromFieldComboBox.addItems(self.dest_fields)
        self.form.searchInFieldComboBox.clear()
        self.form.searchInFieldComboBox.addItems(self.dest_fields)

    def _process_notes(
        self,
        did: DeckId,
        search_field: str,
        copy_into_field: str,
        search_in_field: str,
        copy_from_field: str,
        matched_notes_count: int,
        randomize_results: bool,
    ):
        self.updated_notes = []
        for i, note in enumerate(self.notes):
            if i % 20 == 0:
                self.mw.taskman.run_on_main(
                    lambda: self.mw.progress.update(
                        label=PROGRESS_LABEL.format(count=i, total=len(self.notes)),
                        value=i + 1,
                        max=len(self.notes),
                    )
                )
            copied = get_related_content(
                note,
                did,
                search_field,
                search_in_field,
                [copy_from_field],
                matched_notes_count,
                randomize_results,
            )
            if copied:
                note[copy_into_field] = copied
                self.updated_notes.append(note)

    def on_copy(self):
        search_field = self.src_fields[self.form.searchFieldComboBox.currentIndex()]
        copy_into_field = self.src_fields[
            self.form.copyIntoFieldComboBox.currentIndex()
        ]
        did = self.deckChooser.selectedId()
        search_in_field = (
            self.dest_fields[self.form.searchInFieldComboBox.currentIndex()]
            if self.form.searchInFieldCheckBox.isChecked()
            else ""
        )
        copy_from_field = self.dest_fields[
            self.form.copyFromFieldComboBox.currentIndex()
        ]
        matched_notes_count = (
            self.form.matchedNotesSpinBox.value()
            if self.form.matchedNotesLimitCheckBox.isChecked()
            else -1
        )
        randomize_results = self.form.randomizeCheckBox.isChecked()

        # save options
        self.config["search_field"] = search_field
        self.config["copy_into_field"] = copy_into_field
        self.config["copy_from_deck"] = self.mw.col.decks.get(did)["name"]
        self.config["search_in_field"] = search_in_field
        self.config["copy_from_field"] = copy_from_field
        self.config["matched_notes_limit"] = matched_notes_count
        self.config["randomize_results"] = randomize_results

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
                search_in_field,
                copy_from_field,
                matched_notes_count,
                randomize_results,
            ),
            on_done=on_done,
        )
