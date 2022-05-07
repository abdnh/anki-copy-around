import random
import re
from fileinput import filename
from typing import Iterable, List, Match, MutableSequence, Tuple, cast

from anki.collection import SearchNode
from anki.decks import DeckId
from anki.notes import Note
from aqt import mw

from . import consts

try:
    from anki.utils import strip_html as stripHTML
except ImportError:
    from anki.utils import stripHTML

HIGHLIGHT_COLOR = "#0000ff"
SOUND_REF_RE = re.compile(r"\[sound:(.*?)\]")
PLAY_BUTTON = """<a class="replay-button soundLink" href=# onclick="pycmd('{cmd}:play:{filename}'); return false;">
    <svg class="playImage" viewBox="0 0 64 64" version="1.1">
        <circle cx="32" cy="32" r="29" />
        <path d="M56.502,32.301l-37.502,20.101l0.329,-40.804l37.173,20.703Z" />
    </svg>
</a>"""


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
) -> Tuple[str, List[str]]:
    search_terms = [SearchNode(deck=mw.col.decks.get(did)["name"])]
    # search in all fields, then filter by chosen search field if any
    search_text = stripHTML(note[search_field].lower())
    search_terms.append(search_text)
    query = mw.col.build_search_string(*search_terms)
    nids = cast(MutableSequence, mw.col.find_notes(query))
    if not nids:
        return ("", [])
    if shuffle:
        random.shuffle(nids)
    copied = ""
    count = 0
    audios = []
    for nid in nids:
        if count >= max_notes:
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
                if delayed:
                    # We need to process audio filenames manually in the delayed=true case
                    # because Anki's processing of them will have finished at this stage.
                    def repl_sounds(match: Match) -> str:
                        filename = match.group(1)
                        audios.append(filename)
                        return PLAY_BUTTON.format(
                            cmd=consts.FILTER_NAME, filename=filename
                        )

                    field_contents = SOUND_REF_RE.sub(repl_sounds, field_contents)
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

    return copied, audios
