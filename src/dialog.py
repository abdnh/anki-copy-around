from concurrent.futures import Future
from typing import List, Optional, Tuple

from anki.models import NotetypeId
from anki.notes import Note
from aqt import qtmajor
from aqt.main import AnkiQt
from aqt.notetypechooser import NotetypeChooser
from aqt.qt import *
from aqt.utils import showWarning

from . import consts
from .copy_around import get_related_content

if qtmajor > 5:
    from .forms.form_qt6 import Ui_Dialog
else:
    from .forms.form_qt5 import Ui_Dialog  # type: ignore


PROGRESS_LABEL = "Processed {count} out of {total} note(s)"


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
        self.notetype_chooser = NotetypeChooser(
            mw=self.mw,
            widget=self.form.notetypeChooser,
            show_prefix_label=False,
            starting_notetype_id=self.mw.col.models.current()["id"],
            on_notetype_changed=self._update_dest_fields,
        )
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
        mids = set(note.mid for note in self.notes)
        if len(mids) > 1:
            showWarning(
                "Please select notes from only one notetype.",
                parent=self,
                title=consts.ADDON_NAME,
            )
            return 0
        copy_from_notetype = self.mw.col.models.by_name(
            self.config["copy_from_notetype"]
        )
        if copy_from_notetype:
            self.notetype_chooser.selected_notetype_id = copy_from_notetype["id"]
            self._update_dest_fields(copy_from_notetype["id"])
        else:
            self._update_dest_fields(
                self.notetype_chooser.selected_notetype_id,
            )

        copy_from_fields = self.config["copy_from_fields"]
        for field in copy_from_fields:
            _, field = self._get_field(self.dest_fields, field)
            if field:
                items = self.form.copyFromListWidget.findItems(
                    field, Qt.MatchFlag.MatchFixedString  # pylint: disable=no-member
                )
                if items:
                    self.form.copyFromListWidget.setCurrentItem(
                        items[0],
                        QItemSelectionModel.SelectionFlag.Select,  # pylint: disable=no-member
                    )
        search_in_field = self.config["search_in_field"]
        i, search_in_field = self._get_field(self.dest_fields, search_in_field)
        if search_in_field:
            self.form.searchInFieldCheckBox.setChecked(True)
            self.form.searchInFieldComboBox.setCurrentText(search_in_field)

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

    def _update_dest_fields(self, mid: NotetypeId) -> None:
        self.dest_fields: List[str] = []
        if mid:
            model = self.mw.col.models.get(mid)
            for field in model["flds"]:
                self.dest_fields.append(field["name"])
        self.form.copyFromListWidget.clear()
        self.form.copyFromListWidget.addItems(self.dest_fields)
        self.form.searchInFieldComboBox.clear()
        self.form.searchInFieldComboBox.addItems(self.dest_fields)

    def _process_notes(
        self,
        notetype: str,
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
                notetype,
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
        notetype = self.notetype_chooser.selected_notetype_name()
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
        self.config["copy_from_notetype"] = notetype
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
                notetype,
                search_field,
                copy_into_field,
                search_in_field,
                copy_from_fields,
                max_notes,
                randomize_results,
            ),
            on_done=on_done,
        )
