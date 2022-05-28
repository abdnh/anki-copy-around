import os
import random
import re
import shutil
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Match, MutableSequence, Optional, Tuple, Union, cast

from anki.cards import Card
from anki.collection import Collection, SearchNode
from anki.notes import Note, NoteId
from aqt import mw

try:
    from anki.utils import strip_html as stripHTML
except ImportError:
    from anki.utils import stripHTML

from . import consts

CLOZE_HTML = """<span class="cloze" data-text={text} onmouseover="this.textContent = this.dataset.text;" onmouseout="this.textContent = '[...]';">[...]</span>"""
HIGHLIGHT_COLOR = "#0000ff"
# Credit: adapted from  https://icons.getbootstrap.com/icons/plus-circle/
ADD_BUTTON = """<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="#414141" class="bi bi-plus-circle" viewBox="0 0 16 16">
  <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
  <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"/>
</svg>"""


@dataclass
class Subs2srsOptions:
    font_size: str
    # whether to include subs2srs context when clicking the add button besides a context line in the filter
    save: bool


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
    raw_subs2srs_text: str


@dataclass
class CopyAroundRelated:
    nid: NoteId
    related_notes: Dict[NoteId, RelatedNote]


@dataclass
class SaveInfo:
    """Data used for saving a context line via the Add button in the filter."""

    field: str
    filter_id: int


# ported from rslib/src/text.rs
WILDCARD_RE = re.compile(r"\\[\\*]|[*%]")


def to_sql(txt: str) -> str:
    def repl(match: Match) -> str:
        s = match.group(0)
        if s == r"\\":
            return r"\\"
        if s == r"\*":
            return "*"
        if s == "*":
            return "%"
        if s == "%":
            return r"\%"
        return s

    return WILDCARD_RE.sub(repl, txt)


SQL_RE = re.compile(r"[\\%_]")


def escape_sql_wildcards(txt: str) -> str:
    return SQL_RE.sub(r"\\\0", txt)


def get_related(
    note: Note,
    notetype_name: str,
    search_field: str,
    search_in_field: str,
    copy_from_fields: List[str],
    max_notes: int = -1,
    shuffle: bool = False,
    subs2srs_info: Optional[Subs2srsOptions] = None,
    other_col: Optional[Collection] = None,
) -> Tuple[str, CopyAroundRelated]:

    copyaround = CopyAroundRelated(note.id, {})
    if other_col:
        col = other_col
    else:
        col = mw.col
    notetype = col.models.by_name(notetype_name)
    if not notetype:
        return "", copyaround
    mid = notetype["id"]
    field_ords = {}
    for f in notetype["flds"]:
        field_ords[f["name"]] = f["ord"]
    search_text = stripHTML(note[search_field])
    search_text = unicodedata.normalize("NFC", search_text)
    escaped_search = to_sql(search_text)
    where_params: List[Any] = []
    field_params: List[Any] = []
    if search_in_field:
        if search_in_field not in field_ords:
            return search_text, copyaround
        where_clause = "field_at_index(n.flds, ?) like '%' || ? || '%' escape '\\'"
        where_params.append(field_ords[search_in_field])
        where_params.append(escaped_search)
    else:
        where_clause = "(sfld like '%' || ? || '%' escape '\\' or flds like '%' || ? || '%' escape '\\')"
        where_params.append(escaped_search)
        where_params.append(escaped_search)
    where_clause += " and n.id != ? and n.mid = ?"
    where_params.append(note.id)
    where_params.append(mid)
    subqueries = []
    for i, field in enumerate(copy_from_fields):
        subqueries.append(f"f{i} != ''")

    where_clause += f' and ({" or ".join(subqueries)})'
    query = "select n.id, {field_subquery} from notes n where {where_clause}"
    subqueries = []
    for i, field in enumerate(copy_from_fields):
        if field in field_ords:
            subqueries.append(f"field_at_index(n.flds, ?) as f{i}")
            field_params.append(field_ords[field])
    if not subqueries:
        # no requested fields exist in target notetype
        return search_text, copyaround

    query = query.format(
        field_subquery=", ".join(subqueries), where_clause=where_clause
    )
    params = field_params + where_params
    # print(
    #     f"copyaround: {query=} {search_text=} {escaped_search=} {params=} {other_col=}"
    # )
    results_list = col.db.all(query, *params)
    # print(f"{results_list=}")
    if shuffle:
        random.shuffle(results_list)
    if max_notes >= 0:
        results_list = results_list[:max_notes]
    for nid, *field_contents in results_list:
        dest_note: Dict[str, str] = {}
        for i, val in enumerate(field_contents):
            if val:
                dest_note[copy_from_fields[i]] = val
        copied_fields = {}
        subs2srs_text = ""
        raw_subs2srs_text = ""
        for copy_from_field in copy_from_fields:
            if copy_from_field in dest_note:
                contents = dest_note[copy_from_field]
                if other_col:
                    # UGLY HACK: copy media files from the other collection to the current collection
                    # FIXME: find a better way to do this
                    filenames = col.media.filesInStr(mid, contents)
                    for filename in filenames:
                        shutil.copy(
                            os.path.join(
                                os.path.dirname(col.path), "collection.media", filename
                            ),
                            mw.col.media.dir(),
                        )
                copied_fields[copy_from_field] = RelatedField(
                    copy_from_field, contents, contents
                )
        if subs2srs_info and (
            subs2srs_context := getattr(mw, "subs2srs_context", None)
        ):
            # get info from previous and next sub2srs notes using the subs2srs-context add-on
            # TODO: maybe factor out some of this logic to subs2srs-context
            audio_buttons = subs2srs_context.get_audio_buttons(nid, flip=True)
            audio_filenames = [
                subs2srs_context.get_audio_filename(nid - 1),
                subs2srs_context.get_audio_filename(nid + 1),
            ]
            audio_tags = [
                f"[sound:{filename}]" if filename else ""
                for filename in audio_filenames
            ]
            expressions = subs2srs_context.get_expressions(nid)
            subs2srs_text += f'<div class="copyaround-subs2srs-context" style="font-size: {subs2srs_info.font_size};">{expressions[0]}{audio_buttons[0]}{audio_buttons[1]}{expressions[1]}</div>'
            if subs2srs_info.save:
                raw_subs2srs_text += f'<div class="copyaround-subs2srs-context" style="font-size: {subs2srs_info.font_size};">{expressions[0]}{audio_tags[0]}{audio_tags[1]}{expressions[1]}</div>'

        if copied_fields:
            related_note = RelatedNote(
                nid, copied_fields, subs2srs_text, raw_subs2srs_text
            )
            copyaround.related_notes[nid] = related_note

    return search_text, copyaround


# TODO: remove this
def get_related_old(
    note: Note,
    deck: str,
    search_field: str,
    search_in_field: str,
    copy_from_fields: List[str],
    max_notes: int = -1,
    shuffle: bool = False,
    subs2srs_info: Optional[Subs2srsOptions] = None,
    other_col: Optional[Collection] = None,
) -> Tuple[str, CopyAroundRelated]:

    copyaround = CopyAroundRelated(note.id, {})
    search_terms: List[Union[str, SearchNode]] = []
    if other_col:
        col = other_col
    else:
        col = mw.col
        search_terms.append(SearchNode(deck=deck))

    search_text = stripHTML(note[search_field])
    search_terms.append(search_text)
    field_terms = []
    for copy_from_field in copy_from_fields:
        field_terms.append(SearchNode(field_name=copy_from_field))
    search_terms.append(col.build_search_string(*field_terms, joiner="OR"))
    query = col.build_search_string(*search_terms)
    nids = cast(MutableSequence, col.find_notes(query))
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
        dest_note = col.get_note(nid)
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
        raw_subs2srs_text = ""
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
            # TODO: maybe factor out some of this logic to subs2srs-context
            audio_buttons = subs2srs_context.get_audio_buttons(nid, flip=True)
            audio_filenames = [
                subs2srs_context.get_audio_filename(nid - 1),
                subs2srs_context.get_audio_filename(nid + 1),
            ]
            audio_tags = [
                f"[sound:{filename}]" if filename else ""
                for filename in audio_filenames
            ]
            expressions = subs2srs_context.get_expressions(nid)
            subs2srs_text += f'<div class="copyaround-subs2srs-context" style="font-size: {subs2srs_info.font_size};">{expressions[0]}{audio_buttons[0]}{audio_buttons[1]}{expressions[1]}</div>'
            if subs2srs_info.save:
                raw_subs2srs_text += f'<div class="copyaround-subs2srs-context" style="font-size: {subs2srs_info.font_size};">{expressions[0]}{audio_tags[0]}{audio_tags[1]}{expressions[1]}</div>'

        if copied_fields:
            count += 1
            related_note = RelatedNote(
                nid, copied_fields, subs2srs_text, raw_subs2srs_text
            )
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
    fields.append(note.raw_subs2srs_text)
    return format_note(note.nid, fields)


def get_related_content(
    note: Note,
    notetype_name: str,
    search_field: str,
    search_in_field: str,
    copy_from_fields: List[str],
    max_notes: int = -1,
    shuffle: bool = False,
    highlight: bool = False,
    cloze: bool = False,
    delayed: bool = False,
    subs2srs_info: Optional[Subs2srsOptions] = None,
    card: Optional[Card] = None,
    side: str = "question",
    save_info: Optional[SaveInfo] = None,
    other_col: Optional[Collection] = None,
) -> Tuple[str, CopyAroundRelated]:

    # benchmark()

    search_text, copyaround = get_related(
        note,
        notetype_name,
        search_field,
        search_in_field,
        copy_from_fields,
        max_notes,
        shuffle,
        subs2srs_info,
        other_col,
    )
    copied = ""
    for related in copyaround.related_notes.values():
        copied_fields = []
        for field_name, related_field in related.fields.items():
            processed_contents = related_field.processed_contents

            def wrap(match: Match) -> str:
                text = match.group(0)
                if cloze:
                    text = CLOZE_HTML.format(text=text)
                if highlight:
                    text = f'<span style="color: {HIGHLIGHT_COLOR}">{text}</span>'
                return text

            # FIXME: do not touch filenames inside [sound:foo.mp3]
            processed_contents = re.sub(
                f"(?i){re.escape(search_text)}", wrap, processed_contents
            )
            if delayed and (
                playback_controller := getattr(mw, "playback_controller", None)
            ):
                # We need to process audio filenames manually in the delayed=true case
                # because Anki's processing of them will have finished at this stage.
                # I use my control-audio-playback add-on here.
                processed_contents, _ = playback_controller.add_sound_tags_from_text(
                    processed_contents,
                    "q" if side == "question" else "a",
                    card and card.autoplay(),
                )
            related_field.processed_contents = processed_contents
            copied_fields.append(format_field(field_name, processed_contents))
        if save_info and save_info.field:
            copied_fields.append(
                f"""<a class="copyaround-add-button"
                style="text-decoration: none; display: inline-flex; vertical-align: middle; margin: 3px;"
                href=#
                onclick="pycmd('{consts.FILTER_NAME}:add:{related.nid}:{save_info.filter_id}:{save_info.field}'); return false;">{ADD_BUTTON}</a>"""
            )

        if related.subs2srs_text:
            copied_fields.append(related.subs2srs_text)
        if copied_fields:
            copied += format_note(related.nid, copied_fields)

    return copied, copyaround


def benchmark() -> None:
    from timeit import timeit

    words = [
        "不良少年",
        "注定",
        "占便宜",
        "没的说",
        "节骨眼儿",
        "纳闷儿",
        "郎才女貌",
        "划不来",
        "悠着",
        "心血",
        "一无所获",
        "一语成谶",
        "不巧的",
        "悬念",
        "马大哈",
        "入关",
        "鬼地方",
        "断片",
        "心里有数",
        "非分",
        "分手费",
        "面都没",
        "负责到底",
        "不修哪里幅",
        "熟悉感",
        "划清界限",
        "替他",
        "恶性竞争",
        "坏我好事",
        "老派",
        "铲屎官",
        "入手了",
        "多得多",
        "一晚上",
        "保证你",
        "老大不小",
        "以下几点",
        "长胖",
        "扯着",
        "图什么",
        "生我气",
        "人家属",
        "会时刻",
        "难道说",
        "凑什么",
        "中等偏上",
    ]
    tl1 = []
    tl2 = []
    args = [
        "Word",
        "Expression",
        ["Expression", "Audio"],
        2,
        True,
        Subs2srsOptions(font_size="12", save=False),
        None,
    ]

    class DummyNote(dict):
        id = 1

    for word in words:
        nt = cast(Note, DummyNote(Word=word))
        t1 = timeit(
            lambda nt=nt: get_related_old(nt, "bulk", *args),
            number=1,
        )
        t2 = timeit(
            lambda nt=nt: get_related(nt, "subs2srs", *args),
            number=1,
        )
        tl1.append(t1)
        tl2.append(t2)
        print(f"{t1=} {t2=}")
    print("Average: t1={} , t2={}".format(sum(tl1) / len(words), sum(tl2) / len(words)))
