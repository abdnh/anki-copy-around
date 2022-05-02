import random

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


def get_related_content(
    note: Note,
    did: DeckId,
    search_field: str,
    search_in_field: str,
    copy_from_field: str,
    matched_notes_count: int = -1,
    shuffle: bool = False,
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
    copied = []
    for nid in nids:
        dest_note = mw.col.get_note(nid)
        if copy_from_field not in dest_note:
            continue
        # filter by chosen field
        if search_in_field and (
            search_in_field not in dest_note
            or (
                search_in_field in dest_note
                and search_text not in stripHTML(dest_note[search_in_field])
            )
        ):
            continue
        copied.append(dest_note[copy_from_field])

    return "<br>".join(copied)
