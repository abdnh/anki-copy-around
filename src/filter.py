import re
from typing import Dict
from anki.hooks import field_filter
from anki.template import TemplateRenderContext
from aqt import mw

from . import consts
from .copy_around import get_related_content

# FIXME: doesn't work with values that contain double quotes
FILTER_OPTION_RE = re.compile(r'((?P<key>\w+)\s*=\s*(?P<value>(".*")|\S*))')


def get_bool_filter_option(options: Dict, key: str) -> bool:
    return (
        (True if options[key].lower() == "true" else False) if key in options else True
    )


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
    shuffle = get_bool_filter_option(options, "shuffle")
    highlight = get_bool_filter_option(options, "highlight")
    ret = get_related_content(
        ctx.note(),
        did,
        field_name,
        options.get("search_in", ""),
        options["leech_from"].split(","),
        int(options.get("count", 1)),
        shuffle=shuffle,
        highlight=highlight,
    )
    return ret


def init_filter():
    field_filter.append(add_filter)
