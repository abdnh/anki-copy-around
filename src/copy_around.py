import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, MutableSequence, Optional, Tuple, Union, cast

from anki.cards import Card
from anki.collection import SearchNode
from anki.decks import DeckId
from anki.notes import Note, NoteId
from aqt import mw

try:
    from anki.utils import strip_html as stripHTML
except ImportError:
    from anki.utils import stripHTML

from . import consts

HIGHLIGHT_COLOR = "#0000ff"
# Credit: adapted from  https://icons.getbootstrap.com/icons/plus-circle/
ADD_BUTTON = """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="#414141" class="bi bi-plus-circle" viewBox="0 0 16 16">
  <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
  <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"/>
</svg>"""


@dataclass
class Subs2srsOptions:
    font_size: str


@dataclass
class RelatedField:
    name: str
    # raw field text as taken from the note contents, with little to no modifications
    raw_contents: str
    # field text with all necessary modifications for display
    processed_contents: str


@dataclass
class RelatedNote:
    nid: NoteId
    fields: Dict[str, RelatedField]
    subs2srs_text: str


@dataclass
class CopyAroundRelated:
    nid: NoteId
    related_notes: Dict[NoteId, RelatedNote]


def get_related(
    note: Note,
    did: DeckId,
    search_field: str,
    search_in_field: str,
    copy_from_fields: Iterable[str],
    max_notes: int = -1,
    shuffle: bool = False,
    # highlight: bool = False,
    # delayed: bool = False,
    subs2srs_info: Optional[Subs2srsOptions] = None,
    # card: Optional[Card] = None,
    # side: str = "question",
    # save_field: Optional[str] = None,
) -> Tuple[str, CopyAroundRelated]:
    copyaround = CopyAroundRelated(note.id, {})
    search_terms: List[Union[str, SearchNode]] = [
        SearchNode(deck=mw.col.decks.get(did)["name"])
    ]
    search_text = stripHTML(note[search_field])
    search_terms.append(search_text)
    field_terms = []
    for copy_from_field in copy_from_fields:
        field_terms.append(SearchNode(field_name=copy_from_field))
    search_terms.append(mw.col.build_search_string(*field_terms, joiner="OR"))
    query = mw.col.build_search_string(*search_terms)
    nids = cast(MutableSequence, mw.col.find_notes(query))
    if not nids:
        return "", copyaround
    if shuffle:
        random.shuffle(nids)
    count = 0
    for nid in nids:
        if count >= max_notes >= 0:
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

        copied_fields = {}
        subs2srs_text = ""
        for copy_from_field in copy_from_fields:
            if copy_from_field in dest_note:
                field_contents = dest_note[copy_from_field]
                copied_fields[copy_from_field] = RelatedField(
                    copy_from_field, field_contents, field_contents
                )
        if subs2srs_info and (
            subs2srs_context := getattr(mw, "subs2srs_context", None)
        ):
            # get info from previous and next sub2srs notes using the subs2srs-context add-on
            audio_buttons = subs2srs_context.get_audio_buttons(nid, flip=True)
            expressions = subs2srs_context.get_expressions(nid)
            # subs2srs_text += (
            #     f"{expressions[0]}{audio_buttons[0]}{audio_buttons[1]}{expressions[1]}"
            # )
            subs2srs_text += f'<div class="copyaround-subs2srs-context" style="font-size: {subs2srs_info.font_size};">{expressions[0]}{audio_buttons[0]}{audio_buttons[1]}{expressions[1]}</div>'

        if copied_fields:
            count += 1
            related_note = RelatedNote(nid, copied_fields, subs2srs_text)
            copyaround.related_notes[nid] = related_note

    return search_text, copyaround


def format_field(name: str, contents: str) -> str:
    css_class = f'copyaround-field-{name.replace(" ", "_")}'
    return f'<span class="{css_class}">{contents}</span>'


def format_note(nid: NoteId, formatted_fields: List[str]) -> str:
    return (
        f'<div class="copyaround-related-note" data-nid="{nid}">'
        + "".join(formatted_fields)
        + "</div>"
    )


def format_note_for_saving(note: RelatedNote) -> str:
    fields = [format_field(k, v.raw_contents) for k, v in note.fields.items()]
    return format_note(note.nid, fields)


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
    subs2srs_info: Optional[Subs2srsOptions] = None,
    card: Optional[Card] = None,
    side: str = "question",
    save_field: Optional[str] = None,
) -> Tuple[str, CopyAroundRelated]:
    search_text, copyaround = get_related(
        note,
        did,
        search_field,
        search_in_field,
        copy_from_fields,
        max_notes,
        shuffle,
        subs2srs_info,
    )
    copied = ""
    # count = 0
    for related in copyaround.related_notes.values():
        copied_fields = []
        for field_name, related_field in related.fields.items():
            processed_contents = related_field.processed_contents
            if highlight:
                # FIXME: do not touch filenames inside [sound:foo.mp3]
                processed_contents = processed_contents.replace(
                    search_text,
                    f'<span style="color: {HIGHLIGHT_COLOR}">{search_text}</span>',
                )
                # include highlight with "raw" contents
                related_field.raw_contents = processed_contents
            if delayed and (
                playback_controller := getattr(mw, "playback_controller", None)
            ):
                # We need to process audio filenames manually in the delayed=true case
                # because Anki's processing of them will have finished at this stage.
                # I use my control-audio-playback add-on here.
                processed_contents, tags = playback_controller.add_sound_tags_from_text(
                    processed_contents,
                    "q" if side == "question" else "a",
                    card and card.autoplay(),
                )
            related_field.processed_contents = processed_contents
            copied_fields.append(format_field(field_name, processed_contents))
        if save_field:
            copied_fields.append(
                f"""<a class="copyaround-add-button"
                style="text-decoration: none; display: inline-flex; vertical-align: middle; margin: 3px;"
                href=#
                onclick="pycmd('{consts.FILTER_NAME}:add:{related.nid}:{save_field}'); return false;">{ADD_BUTTON}</a>"""
            )

        if related.subs2srs_text:
            copied_fields.append(related.subs2srs_text)
        if copied_fields:
            copied += format_note(related.nid, copied_fields)
            # count += 1

    return copied, copyaround
