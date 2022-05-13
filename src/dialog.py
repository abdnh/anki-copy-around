from concurrent.futures import Future
from typing import List, Optional, Tuple

import anki
from anki.decks import DeckId
from anki.notes import Note
from aqt import qtmajor
from aqt.deckchooser import DeckChooser
from aqt.main import AnkiQt
from aqt.qt import *
from aqt.utils import showWarning

from . import consts
from .copy_around import get_related_content

if qtmajor > 5:
    from .forms.form_qt6 import Ui_Dialog
else:
    from .forms.form_qt5 import Ui_Dialog  # type: ignore


ANKI_POINT_VERSION = int(anki.version.split(".")[-1])  # type: ignore


PROGRESS_LABEL = "Processed {count} out of {total} note(s)"


class MyDeckChooser(DeckChooser):

    onDeckChanged = pyqtSignal(object)

    def choose_deck(self) -> None:
        super().choose_deck()
        self.onDeckChanged.emit(self.selectedId())


class CopyAroundDialog(QDialog):
    def __init__(self, mw: AnkiQt, parent: QWidget, notes: List[Note]):
        super().__init__(parent)
        self.mw = mw
        self.config = mw.addonManager.getConfig(__name__)
        self.notes = notes
        self.setup_ui()

    def setup_ui(self) -> None:
        self.form = Ui_Dialog()
        self.form.setupUi(self)
        self.setWindowTitle(consts.ADDON_NAME)
        # StudyDeck, which is used by DeckChooser, is asynchronous in 2.1.50
        if ANKI_POINT_VERSION >= 50:
            self.deck_chooser = MyDeckChooser(
                self.mw,
                self.form.deckChooser,  # type: ignore
                label=False,
                on_deck_changed=self._update_dest_fields,
            )
        else:
            self.deck_chooser = MyDeckChooser(
                self.mw, self.form.deckChooser, label=False  # type: ignore
            )
            qconnect(MyDeckChooser.onDeckChanged, self._update_dest_fields)
        qconnect(self.form.copyButton.clicked, self.on_copy)
        qconnect(
            self.form.matchedNotesLimitCheckBox.toggled,
            self.form.matchedNotesSpinBox.setEnabled,
        )
        qconnect(
            self.form.searchInFieldCheckBox.toggled,
            self.form.searchInFieldComboBox.setEnabled,
        )
        self.src_fields: List[str] = []
        # TODO: optimize
        for note in self.notes:
            for field in note.keys():
                if field not in self.src_fields:
                    self.src_fields.append(field)
        self.form.searchFieldComboBox.addItems(self.src_fields)
        self.form.copyIntoFieldComboBox.addItems(self.src_fields)

    def exec(self) -> int:
        def on_fetched_dest_fields() -> None:
            copy_from_fields = self.config["copy_from_fields"]
            for field in copy_from_fields:
                i, field = self._get_field(self.dest_fields, field)
                if field:
                    index = self.form.copyFromListWidget.model().createIndex(i, 0)
                    item = self.form.copyFromListWidget.itemFromIndex(index)
                    self.form.copyFromListWidget.setCurrentItem(
                        item, QItemSelectionModel.SelectionFlag.Select
                    )
            search_in_field = self.config["search_in_field"]
            i, search_in_field = self._get_field(self.dest_fields, search_in_field)
            if search_in_field:
                self.form.searchInFieldCheckBox.setChecked(True)
                self.form.searchInFieldComboBox.setCurrentText(search_in_field)

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
            self.deck_chooser.selected_deck_id = copy_from_deck["id"]
            self._update_dest_fields(
                copy_from_deck["id"], on_done=on_fetched_dest_fields
            )
        else:
            self._update_dest_fields(
                self.deck_chooser.selectedId(), on_done=on_fetched_dest_fields
            )

        matched_notes_limit = self.config["matched_notes_limit"]
        if matched_notes_limit > 0:
            self.form.matchedNotesLimitCheckBox.setChecked(True)
            self.form.matchedNotesSpinBox.setValue(matched_notes_limit)

        search_field = self.config["search_field"]
        i, search_field = self._get_field(self.src_fields, search_field)
        if search_field:
            self.form.searchFieldComboBox.setCurrentText(search_field)

        copy_into_field = self.config["copy_into_field"]
        i, copy_into_field = self._get_field(self.src_fields, copy_into_field)
        if copy_into_field:
            self.form.copyIntoFieldComboBox.setCurrentText(copy_into_field)
        else:
            self.form.copyIntoFieldComboBox.setCurrentIndex(1)

        randomize_results = self.config["randomize_results"]
        self.form.randomizeCheckBox.setChecked(randomize_results)

        return super().exec()

    def _get_field(self, fields: List[str], key: str) -> Tuple[int, Optional[str]]:
        for i, field in enumerate(fields):
            if key.lower() == field.lower():
                return i, field
        return -1, None

    def _update_dest_fields(
        self, dest_did: DeckId, on_done: Optional[Callable[[], None]] = None
    ) -> None:
        self.mw.progress.start(label="Getting field names...")
        self.mw.progress.set_title(consts.ADDON_NAME)
        self.dest_fields: List[str] = []

        def task() -> None:
            self.dest_fields = self.mw.col.db.list(
                """
select distinct name from fields
  where ntid in (select id from notetypes
    where id in (select mid from notes
	 where id in (select nid from cards where did = ?))) order by ntid, ord
""",
                dest_did,
            )

        def _on_done(fut: Future) -> None:
            try:
                fut.result()
            finally:
                self.mw.progress.finish()
            self.form.copyFromListWidget.clear()
            self.form.copyFromListWidget.addItems(self.dest_fields)
            self.form.searchInFieldComboBox.clear()
            self.form.searchInFieldComboBox.addItems(self.dest_fields)
            if on_done:
                on_done()

        self.mw.taskman.run_in_background(task, on_done=_on_done)

    def _process_notes(
        self,
        did: DeckId,
        search_field: str,
        copy_into_field: str,
        search_in_field: str,
        copy_from_fields: List[str],
        max_notes: int,
        randomize_results: bool,
    ) -> None:
        self.updated_notes = []
        for i, note in enumerate(self.notes):
            if i % 20 == 0:
                self.mw.taskman.run_on_main(
                    lambda i=i: self.mw.progress.update(
                        label=PROGRESS_LABEL.format(count=i, total=len(self.notes)),
                        value=i + 1,
                        max=len(self.notes),
                    )
                )
            copied, _ = get_related_content(
                note,
                did,
                search_field,
                search_in_field,
                copy_from_fields,
                max_notes,
                randomize_results,
            )
            if copied:
                note[copy_into_field] = copied
                self.updated_notes.append(note)

    def on_copy(self) -> None:
        search_field = self.src_fields[self.form.searchFieldComboBox.currentIndex()]
        copy_into_field = self.src_fields[
            self.form.copyIntoFieldComboBox.currentIndex()
        ]
        did = self.deck_chooser.selectedId()
        search_in_field = (
            self.dest_fields[self.form.searchInFieldComboBox.currentIndex()]
            if self.form.searchInFieldCheckBox.isChecked()
            else ""
        )
        copy_from_fields = [
            self.dest_fields[idx.row()]
            for idx in self.form.copyFromListWidget.selectedIndexes()
        ]
        max_notes = (
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
        self.config["copy_from_fields"] = copy_from_fields
        self.config["matched_notes_limit"] = max_notes
        self.config["randomize_results"] = randomize_results

        self.mw.addonManager.writeConfig(__name__, self.config)

        def on_done(fut: Future) -> None:
            try:
                fut.result()
            finally:
                self.mw.taskman.run_on_main(self.mw.progress.finish)
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
                copy_from_fields,
                max_notes,
                randomize_results,
            ),
            on_done=on_done,
        )
