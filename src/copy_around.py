import random
import re
from typing import Iterable

from anki.decks import DeckId
from anki.notes import Note
from aqt import mw

try:
    from anki.utils import strip_html as stripHTML
except:
    from anki.utils import stripHTML


def escape_search_term(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace('"', '\\"')
    text = text.replace("_", "\_")
    return f'"{text}"'


HIGHLIGHT_COLOR = "#0000ff"


def get_related_content(
    note: Note,
    did: DeckId,
    search_field: str,
    search_in_field: str,
    copy_from_fields: Iterable[str],
    matched_notes_count: int = -1,
    shuffle: bool = False,
    highlight: bool = False,
):
    deck = escape_search_term(mw.col.decks.get(did)["name"])
    search_terms = [f"deck:{deck}"]
    # search in all fields, then filter by chosen search field if any
    search_text = stripHTML(note[search_field])
    search_terms.append(escape_search_term(search_text))
    query = mw.col.build_search_string(*search_terms)
    nids = mw.col.find_notes(query)
    if not nids:
        return ""
    if shuffle:
        random.shuffle(nids)
    if matched_notes_count >= 0:
        nids = nids[:matched_notes_count]
    copied = ""
    for nid in nids:
        dest_note = mw.col.get_note(nid)
        # filter by chosen field
        if search_in_field and (
            search_in_field not in dest_note
            or (
                search_in_field in dest_note
                and search_text not in stripHTML(dest_note[search_in_field])
            )
        ):
            continue

        copied_fields = []
        for copy_from_field in copy_from_fields:
            if copy_from_field in dest_note:
                css_class = f'copyaround-field-{copy_from_field.replace(" ", "_")}'
                field_contents = dest_note[copy_from_field]
                if highlight:
                    # TODO: do not touch filenames inside [sound:foo.mp3]
                    field_contents = field_contents.replace(
                        search_text,
                        f'<span style="color: {HIGHLIGHT_COLOR}">{search_text}</span>',
                    )
                copied_fields.append(
                    f'<span class="{css_class}">{field_contents}</span>'
                )
        if copied_fields:
            copied += (
                f'<div class="copyaround-related-note" data-nid="{nid}">'
                + "".join(copied_fields)
                + "</div>"
            )

    return copied
