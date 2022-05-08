import json
import re
from typing import Any, Dict, List, Tuple

from anki.hooks import field_filter
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


def get_active_webview() -> AnkiWebView:
    dialog = QApplication.activeModalWidget()
    window = QApplication.activeWindow()
    if isinstance(dialog, CardLayout):
        return dialog.preview_web
    if isinstance(window, Previewer):
        return window._web  # pylint: disable=protected-access
    return mw.reviewer.web


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
            side=mw.reviewer.state,
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
            mw.reviewer.state,
        )
    return ret


def show_copyaround_contents(data: str) -> None:
    web = get_active_webview()

    def show(rendered: bool) -> None:
        if rendered:
            return
        options = json.loads(data)
        options["delayed"] = True
        # FIXME: cause errors if the note was not written to the database yet (e.g. in the card layouts screen opened from the add screen)
        card = mw.col.get_card(options["cid"])
        note = card.note()
        options["card"] = card
        options["note"] = note
        del options["cid"]
        contents = get_related_content(**options)
        if playback_controller := getattr(mw, "playback_controller", None):
            playback_controller.apply_to_card_avtags(mw.reviewer.card)
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
    web = get_active_webview()
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
