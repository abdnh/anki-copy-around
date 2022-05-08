import random
from typing import Iterable, MutableSequence, Optional, cast

from anki.cards import Card
from anki.collection import SearchNode
from anki.decks import DeckId
from anki.notes import Note
from aqt import mw

try:
    from anki.utils import strip_html as stripHTML
except ImportError:
    from anki.utils import stripHTML

HIGHLIGHT_COLOR = "#0000ff"


def get_related_content(
    note: Note,
    did: DeckId,
    search_field: str,
    search_in_field: str,
    copy_from_fields: Iterable[str],
    max_notes: int = -1,
    shuffle: bool = False,
    highlight: bool = False,
    delayed: bool = False,
    subs2srs: bool = False,
    card: Optional[Card] = None,
    side: str = "question",
) -> str:
    search_terms = [SearchNode(deck=mw.col.decks.get(did)["name"])]
    search_text = note[search_field]
    search_terms.append(search_text)
    field_terms = []
    for copy_from_field in copy_from_fields:
        field_terms.append(SearchNode(field_name=copy_from_field))
    search_terms.append(mw.col.build_search_string(*field_terms, joiner="OR"))
    query = mw.col.build_search_string(*search_terms)
    nids = cast(MutableSequence, mw.col.find_notes(query))
    if not nids:
        return ""
    if shuffle:
        random.shuffle(nids)
    copied = ""
    count = 0
    for nid in nids:
        if max_notes >= 0 and count >= max_notes:
            break
        if note.id == nid:
            continue
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
                    # FIXME: do not touch filenames inside [sound:foo.mp3]
                    field_contents = field_contents.replace(
                        search_text,
                        f'<span style="color: {HIGHLIGHT_COLOR}">{search_text}</span>',
                    )
                if delayed and (
                    playback_controller := getattr(mw, "playback_controller", None)
                ):
                    # We need to process audio filenames manually in the delayed=true case
                    # because Anki's processing of them will have finished at this stage.
                    # I use my control-audio-playback add-on here.
                    field_contents, tags = playback_controller.add_sound_tags_from_text(
                        field_contents,
                        "q" if side == "question" else "a",
                        card.autoplay(),
                    )
                copied_fields.append(
                    f'<span class="{css_class}">{field_contents}</span>'
                )
        if subs2srs and (subs2srs_context := getattr(mw, "subs2srs_context", None)):
            # get previous and next sub2srs recordings using the subs2srs-context add-on
            audio_buttons = subs2srs_context.get_audio_buttons(nid)
            copied_fields.append(audio_buttons)

        if copied_fields:
            copied += (
                f'<div class="copyaround-related-note" data-nid="{nid}">'
                + "".join(copied_fields)
                + "</div>"
            )
            count += 1

    return copied
