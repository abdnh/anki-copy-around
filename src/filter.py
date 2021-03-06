import dataclasses
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from anki.cards import Card
from anki.hooks import field_filter
from anki.notes import Note, NoteId
from anki.template import TemplateRenderContext
from aqt import mw
from aqt.browser.previewer import Previewer
from aqt.clayout import CardLayout
from aqt.editor import Editor
from aqt.gui_hooks import state_shortcuts_will_change, webview_did_receive_js_message
from aqt.qt import *
from aqt.utils import tooltip
from aqt.webview import AnkiWebView

from . import consts
from .copy_around import (
    CopyAroundRelated,
    SaveInfo,
    Subs2srsOptions,
    format_note_for_saving,
    get_related_content,
)

# FIXME: doesn't work with values that contain double quotes
FILTER_OPTION_RE = re.compile(r'((?P<key>\w+)\s*=\s*(?P<value>(".*")|\S*))')

TRIGGER_FILTER_BUTTON_SHORTCUT = consts.CONFIG["trigger_filter_button_shortcut"]
TOGGLE_BUTTON = """<button id="copyaround-toggle-{toggle_id}" class="copyaround-toggle" title="Shortcut: {shortcut}" onclick="pycmd('{cmd}:show:{data}'); return false;" style="display: block; margin: 5px auto;">{label}</button>"""

FILTER_CONTEXT: List[CopyAroundRelated] = []


@dataclasses.dataclass
class CardViewContext:
    card: Optional[Card]
    card_ord: int
    note: Optional[Note]
    side: str
    web: AnkiWebView
    editor: Optional[Editor]


def get_active_card_view_context() -> CardViewContext:
    dialog = QApplication.activeModalWidget()
    window = QApplication.activeWindow()
    card_ord = 0
    note = None
    if isinstance(dialog, CardLayout):
        side = "question" if dialog.pform.preview_front.isChecked() else "answer"
        card = getattr(dialog, "rendered_card", None)
        card_ord = dialog.ord
        note = dialog.note
        web = dialog.preview_web
        # TODO: how to get the editor's instance here?
        editor = None
    elif isinstance(window, Previewer):
        side = window._state  # pylint: disable=protected-access
        card = window.card()
        if card:
            card_ord = card.ord
            note = card.note()
        web = window._web  # pylint: disable=protected-access
        if browser := getattr(window, "_parent", None):
            editor = browser.editor
        else:
            editor = None
    else:
        side = mw.reviewer.state
        card = mw.reviewer.card
        if card:
            card_ord = card.ord
            note = card.note()
        web = mw.reviewer.web
        editor = None

    return CardViewContext(card, card_ord, note, side, web, editor)


def get_bool_filter_option(options: Dict, key: str, default: bool = True) -> bool:
    return (options[key].lower() == "true") if key in options else default


def add_filter(
    field_text: str,
    field_name: str,
    filter_name: str,
    ctx: TemplateRenderContext,
) -> str:

    if not filter_name.startswith(consts.FILTER_NAME):
        return field_text

    if not ctx.extra_state.get(consts.FILTER_NAME, None):
        # Reset global context at render time of each card
        global FILTER_CONTEXT
        FILTER_CONTEXT = []
        ctx.extra_state[consts.FILTER_NAME] = FILTER_CONTEXT
    filter_id = len(ctx.extra_state.get(consts.FILTER_NAME))

    options = {}
    options_text = filter_name.split(maxsplit=1)[1]
    for match in FILTER_OPTION_RE.finditer(options_text):
        pair = match.groupdict()
        key = pair["key"]
        value = pair["value"].strip('"')
        options[key] = value

    notetype_name = options.get("notetype", "Basic")
    search_in = options.get("search_in", "")
    leech_from = options["leech_from"].split(",")
    count = int(options.get("count", 1))
    shuffle = get_bool_filter_option(options, "shuffle")
    highlight = get_bool_filter_option(options, "highlight")
    cloze = get_bool_filter_option(options, "cloze", False)
    delayed = get_bool_filter_option(options, "delayed", False)
    subs2srs = get_bool_filter_option(options, "subs2srs", False)
    use_other_col = get_bool_filter_option(options, "other_col", False)
    subs2srs_fontsize = options.get("subs2srs-fontsize", "smaller")
    save_field = options.get("save_field", "")
    save_info = SaveInfo(save_field, filter_id)
    save_subs2srs = consts.CONFIG["save_subs2srs"]
    subs2srs_info = None
    if subs2srs:
        subs2srs_info = Subs2srsOptions(subs2srs_fontsize, save_subs2srs)

    label = options.get("label", consts.ADDON_NAME)
    context = get_active_card_view_context()
    if delayed:
        data = dict(
            toggle_id=filter_id,
            cid=ctx.card().id,
            notetype_name=notetype_name,
            search_field=field_name,
            search_in_field=search_in,
            copy_from_fields=leech_from,
            max_notes=count,
            shuffle=shuffle,
            highlight=highlight,
            cloze=cloze,
            subs2srs_info=dataclasses.asdict(subs2srs_info) if subs2srs_info else {},
            # FIXME: this should be the side where the filter was included,
            # but I don't know of a way to get that kind of info here
            side="a",
            save_info=dataclasses.asdict(save_info),
            use_other_col=use_other_col,
        )
        data_json = json.dumps(data).replace('"', "&quot;")
        ret = TOGGLE_BUTTON.format(
            toggle_id=filter_id,
            cmd=consts.FILTER_NAME,
            data=data_json,
            label=label,
            shortcut=TRIGGER_FILTER_BUTTON_SHORTCUT,
        )
        FILTER_CONTEXT.append(CopyAroundRelated(ctx.note().id, {}))
    else:
        other_col = None
        if use_other_col:
            other_col = mw.copyaround_colman.col
        ret, rel = get_related_content(
            ctx.note(),
            notetype_name,
            field_name,
            search_in,
            leech_from,
            count,
            shuffle,
            highlight,
            cloze,
            delayed,
            subs2srs_info,
            context.card,
            side="a",
            save_info=save_info,
            other_col=other_col,
        )
        FILTER_CONTEXT.append(rel)

    ctx.extra_state[consts.FILTER_NAME] = FILTER_CONTEXT

    return ret


def show_copyaround_contents(data: str) -> None:
    context = get_active_card_view_context()
    web = context.web
    options = json.loads(data)
    toggle_id = options["toggle_id"]
    del options["toggle_id"]

    def show(rendered: bool) -> None:
        if rendered:
            return
        options["delayed"] = True
        # FIXME: cause errors if the note was not written to the database yet (e.g. in the card layouts screen opened from the add screen)
        note = context.note
        card = context.card if context.card else note.cards()[context.card_ord]
        options["card"] = card
        options["note"] = note
        del options["cid"]
        if options["subs2srs_info"]:
            options["subs2srs_info"] = Subs2srsOptions(**options["subs2srs_info"])
        options["save_info"] = SaveInfo(**options["save_info"])
        other_col = None
        if options["use_other_col"]:
            other_col = mw.copyaround_colman.col
        del options["use_other_col"]
        options["other_col"] = other_col
        contents, rel = get_related_content(**options)
        FILTER_CONTEXT[options["save_info"].filter_id] = rel
        if playback_controller := getattr(mw, "playback_controller", None):
            playback_controller.apply_to_card_avtags(card)
        web.eval(
            f"""
(() => {{
    var copyAroundToggle = document.getElementById('copyaround-toggle-{toggle_id}');
    copyAroundToggle.insertAdjacentHTML('afterend', {json.dumps(contents)});
}})();
            """
        )

    web.evalWithCallback(
        f"""
(() => {{
    var copyAroundToggle = document.getElementById('copyaround-toggle-{toggle_id}');
    if(!copyAroundToggle.dataset.rendered) {{
        copyAroundToggle.dataset.rendered = true;
        return false;
    }} else {{
        return true;
    }}
}})();""",
        show,
    )


# FIXME: only works in the reviewer
def save_related_note(nid: str, filter_id: int, save_field: str) -> None:
    context = get_active_card_view_context()
    note = context.note
    if not save_field in note:
        tooltip(
            f"""Field "{save_field}" doesn\'t exist in the current note.<br>
            Please change the save_field option of the {consts.FILTER_NAME} filter from the templates screen."""
        )
        return
    related_note = FILTER_CONTEXT[filter_id].related_notes[NoteId(int(nid))]
    note[save_field] += format_note_for_saving(related_note)
    tooltip(f'Added content from note {nid} to field "{save_field}"')
    if note.id:
        note.flush()
    if context.editor:
        context.editor.set_note(note)


def handle_js_msg(
    handled: Tuple[bool, Any], message: str, context: Any
) -> Tuple[bool, Any]:
    if not message.startswith(consts.FILTER_NAME):
        return handled
    _, subcmd, data = message.split(":", maxsplit=2)
    data = data.replace("&quot;", '"')
    if subcmd == "show":
        show_copyaround_contents(data)
    elif subcmd == "add":
        nid, filter_id, save_field = data.split(":")
        save_related_note(nid, int(filter_id), save_field)
    return (True, None)


def on_show_hotkey_triggered() -> None:
    web = get_active_card_view_context().web
    web.eval(
        """
(() => {
    const copyAroundToggles = document.getElementsByClassName('copyaround-toggle');
    for(const toggle of copyAroundToggles) {
        toggle.click();
    }
})();""",
    )


def modify_replay_shortcut(state: str, shortcuts: List[Tuple[str, Callable]]) -> None:
    if state != "review":
        return
    shortcuts.append((TRIGGER_FILTER_BUTTON_SHORTCUT, on_show_hotkey_triggered))


def init_filter() -> None:
    field_filter.append(add_filter)
    webview_did_receive_js_message.append(handle_js_msg)
    state_shortcuts_will_change.append(modify_replay_shortcut)
