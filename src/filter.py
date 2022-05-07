import json
import re
from typing import Any, Dict, Tuple

from anki.hooks import field_filter
from anki.template import TemplateRenderContext
from aqt import mw
from aqt.browser.previewer import Previewer
from aqt.clayout import CardLayout
from aqt.gui_hooks import webview_did_receive_js_message
from aqt.qt import *
from aqt.sound import play
from aqt.webview import AnkiWebView

from . import consts
from .copy_around import get_related_content

# FIXME: doesn't work with values that contain double quotes
FILTER_OPTION_RE = re.compile(r'((?P<key>\w+)\s*=\s*(?P<value>(".*")|\S*))')

TOGGLE_BUTTON = """<button id="copyaround-toggle" onclick="pycmd('{cmd}:show:{data}'); return false;" style="display: block; margin: 5px auto;">{label}</button>"""


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
            nid=ctx.note().id,
            did=did,
            search_field=field_name,
            search_in_field=search_in,
            copy_from_fields=leech_from,
            matched_notes_count=count,
            shuffle=shuffle,
            highlight=highlight,
            subs2srs=subs2srs,
        )
        data_json = json.dumps(data).replace('"', "&quot;")
        ret = TOGGLE_BUTTON.format(cmd=consts.FILTER_NAME, data=data_json, label=label)
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
            subs2srs,
        )
    return ret


def handle_js_msg(
    handled: Tuple[bool, Any], message: str, context: Any
) -> Tuple[bool, Any]:
    if not message.startswith(consts.FILTER_NAME):
        return handled
    _, subcmd, data = message.split(":", maxsplit=2)
    data = data.replace("&quot;", '"')
    if subcmd == "play":
        filename = data
        play(filename)
    elif subcmd == "show":
        web = get_active_webview()

        def show(rendered: bool) -> None:
            if rendered:
                return
            options = json.loads(data)
            options["delayed"] = True
            options["note"] = mw.col.get_note(options["nid"])
            del options["nid"]
            contents = get_related_content(**options)
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
    return (True, None)


def init_filter() -> None:
    field_filter.append(add_filter)
    webview_did_receive_js_message.append(handle_js_msg)
