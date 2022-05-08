import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from anki.cards import Card
from anki.hooks import field_filter
from anki.notes import Note
from anki.template import TemplateRenderContext
from aqt import mw
from aqt.browser.previewer import Previewer
from aqt.clayout import CardLayout
from aqt.gui_hooks import state_shortcuts_will_change, webview_did_receive_js_message
from aqt.qt import *
from aqt.webview import AnkiWebView

from . import consts
from .copy_around import get_related_content

# FIXME: doesn't work with values that contain double quotes
FILTER_OPTION_RE = re.compile(r'((?P<key>\w+)\s*=\s*(?P<value>(".*")|\S*))')

TRIGGER_FILTER_BUTTON_SHORTCUT = mw.addonManager.getConfig(__name__)[
    "trigger_filter_button_shortcut"
]
TOGGLE_BUTTON = """<button id="copyaround-toggle" title="Shortcut: {shortcut}" onclick="pycmd('{cmd}:show:{data}'); return false;" style="display: block; margin: 5px auto;">{label}</button>"""


@dataclass
class CardViewContext:
    card: Optional[Card]
    card_ord: int
    note: Optional[Note]
    side: str
    web: AnkiWebView


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
    elif isinstance(window, Previewer):
        side = window._state
        card = window.card()
        if card:
            card_ord = card.ord
            note = card.note()
        web = window._web  # pylint: disable=protected-access
    else:
        side = mw.reviewer.state
        card = mw.reviewer.card
        if card:
            card_ord = card.ord
            note = card.note()
        web = mw.reviewer.web

    return CardViewContext(card, card_ord, note, side, web)


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
    options = {}
    options_text = filter_name.split(maxsplit=1)[1]
    for match in FILTER_OPTION_RE.finditer(options_text):
        pair = match.groupdict()
        key = pair["key"]
        value = pair["value"].strip('"')
        options[key] = value

    did = mw.col.decks.id(options["deck"])
    search_in = options.get("search_in", "")
    leech_from = options["leech_from"].split(",")
    count = int(options.get("count", 1))
    shuffle = get_bool_filter_option(options, "shuffle")
    highlight = get_bool_filter_option(options, "highlight")
    delayed = get_bool_filter_option(options, "delayed", False)
    subs2srs = get_bool_filter_option(options, "subs2srs", False)
    label = options.get("label", consts.ADDON_NAME)
    context = get_active_card_view_context()
    if delayed:
        data = dict(
            cid=ctx.card().id,
            did=did,
            search_field=field_name,
            search_in_field=search_in,
            copy_from_fields=leech_from,
            max_notes=count,
            shuffle=shuffle,
            highlight=highlight,
            subs2srs=subs2srs,
            # FIXME: this should be the side where the filter was included,
            # but I don't know of a way to get that kind of info here
            side="a",
        )
        data_json = json.dumps(data).replace('"', "&quot;")
        ret = TOGGLE_BUTTON.format(
            cmd=consts.FILTER_NAME,
            data=data_json,
            label=label,
            shortcut=TRIGGER_FILTER_BUTTON_SHORTCUT,
        )
    else:
        ret = get_related_content(
            ctx.note(),
            did,
            field_name,
            search_in,
            leech_from,
            count,
            shuffle,
            highlight,
            delayed,
            subs2srs,
            context.card,
            side="a",
        )
    return ret


def show_copyaround_contents(data: str) -> None:
    context = get_active_card_view_context()
    web = context.web

    def show(rendered: bool) -> None:
        if rendered:
            return
        options = json.loads(data)
        options["delayed"] = True
        # FIXME: cause errors if the note was not written to the database yet (e.g. in the card layouts screen opened from the add screen)
        note = context.note
        card = context.card if context.card else note.cards()[context.card_ord]
        options["card"] = card
        options["note"] = note
        del options["cid"]
        contents = get_related_content(**options)
        if playback_controller := getattr(mw, "playback_controller", None):
            playback_controller.apply_to_card_avtags(card)
        web.eval(
            f"""
(() => {{
    var copyAroundToggle = document.getElementById('copyaround-toggle');
    copyAroundToggle.insertAdjacentHTML('afterend', {json.dumps(contents)});
}})();
            """
        )

    web.evalWithCallback(
        """
(() => {
    var copyAroundToggle = document.getElementById('copyaround-toggle');
    if(!copyAroundToggle.dataset.rendered) {
        copyAroundToggle.dataset.rendered = true;
        return false;
    } else {
        return true;
    }
})();""",
        show,
    )


def handle_js_msg(
    handled: Tuple[bool, Any], message: str, context: Any
) -> Tuple[bool, Any]:
    if not message.startswith(consts.FILTER_NAME):
        return handled
    _, subcmd, data = message.split(":", maxsplit=2)
    data = data.replace("&quot;", '"')
    if subcmd == "show":
        show_copyaround_contents(data)
    return (True, None)


def on_show_hotkey_triggered() -> None:
    web = get_active_card_view_context().web
    web.eval(
        """
(() => {
var copyAroundToggle = document.getElementById('copyaround-toggle');
copyAroundToggle.click();
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
