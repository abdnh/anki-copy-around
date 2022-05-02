import re
from anki.hooks import field_filter
from anki.template import TemplateRenderContext
from aqt import mw

from . import consts
from .copy_around import get_related_content

# FIXME: doesn't work with values that contain double quotes
FILTER_OPTION_RE = re.compile(r'((?P<key>\w+)\s*=\s*(?P<value>(".*")|\S*))')


def add_filter(
    field_text: str,
    field_name: str,
    filter_name: str,
    ctx: TemplateRenderContext,
) -> str:
    """
    Adds a "copyaround" template filter. E.g.
    ```
    {{copyaround deck=leech_deck_2 search_in=Expression leech_from=Snapshot count=2 shuffle=true:word}}
    ```
    """
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
    shuffle = (
        (True if options["random"].lower() == "true" else False)
        if "random" in options
        else True
    )
    ret = get_related_content(
        ctx.note(),
        did,
        field_name,
        options.get("search_in", ""),
        options["leech_from"].split(","),
        int(options.get("count", 1)),
        shuffle=shuffle,
    )
    return ret


def init_filter():
    field_filter.append(add_filter)
