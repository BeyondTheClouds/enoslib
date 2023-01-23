import logging
import uuid
from html import escape as html_escape
from typing import Callable, Collection, List, Optional, Union

import pkg_resources

from enoslib.config import get_config

logger = logging.getLogger(__name__)

STATIC_FILES = "html/style.css"


def repr_html_check(f) -> Callable[..., str]:
    """Decorator for _repr_html_ for some routines checks."""
    if f.__name__ != "_repr_html_":
        raise ValueError("repr_check can only decorates a _repr_html_ function")

    def wrapped(self, *args, **kwargs) -> str:
        if get_config()["display"] != "html":
            return repr(self)
        try:
            return f(self, *args, **kwargs)
        except Exception as err:
            logger.error(
                "%s raised when rendering the HTML, proceeding with default __repr__",
                err,
            )
        return repr(self)

    return wrapped


def _html_escape(value, limit=50) -> str:
    """Truncate value as a string and html_escape it."""
    value = str(value) if len(str(value)) < limit else f"{str(value)[0:limit]}[...]"
    return html_escape(value)


def _load_css() -> str:
    return pkg_resources.resource_string("enoslib", STATIC_FILES).decode("utf8")


def html_to_foldable_section(
    name: str, html_objects: Union[str, List[str]], extra: str = ""
) -> str:
    """Generate a foldable section from html code.

    Wrap the html objects into something foldable
    """

    if isinstance(html_objects, str):
        html_objects = [html_objects]

    data_id = f"{name}-" + str(uuid.uuid4())

    html_extra = ""
    if extra:
        html_extra = f'<span class="len">({extra})</span>'

    return f"""
                <li>
                    <input type="checkbox" id="{data_id}" class="att">
                    <label for="{data_id}">{name} {html_extra}</label>
                    <ul id="{name}" class="enoslist">
                        {"".join(html_objects)}
                    </ul>
                </li>
                """


def inline_value(key: str, value: str) -> str:
    data_id = f"{key}-" + str(uuid.uuid4())
    return f"""
        <li>
        <input type="checkbox" id="{data_id}" class="att" disabled="">
        <label for="{data_id}">
            <span>{key}:&nbsp;</span>
        </label>
        <span>{_html_escape(value)}</span>
        </li>"""


def dict_to_html_foldable_sections(d: dict) -> str:
    """Transform a dictionary a set of foldable sections.

    Inner lists are transformed as table.
    """
    html = ""
    for k, v in d.items():
        if isinstance(v, dict) or hasattr(v, "keys"):
            # foldable_section
            html += html_to_foldable_section(
                k, dict_to_html_foldable_sections(v), extra=str(len(v))
            )
        elif isinstance(v, list):
            tab = convert_to_html_table(v)
            # table_section
            html += html_to_foldable_section(k, tab, extra=str(len(v)))
        else:
            # line_section
            html += inline_value(k, v)
    return html


def convert_to_html_table(input_data) -> str:
    """Convert something to a html table.

    Accepted input type: list, dict or regular str
    """
    if isinstance(input_data, str):
        return _html_escape(str(input_data))
    if isinstance(input_data, dict):
        return convert_dict_to_html_table(input_data)
    if hasattr(input_data, "__iter__") and hasattr(input_data, "__getitem__"):
        return convert_list_to_html_table(input_data)
    return _html_escape(str(input_data))


def html_table_header(input_data) -> Optional[Collection[str]]:
    """This code is borrowed from json2html (MIT)"""
    if (
        not input_data
        or not hasattr(input_data, "__getitem__")
        or not hasattr(input_data[0], "keys")
    ):
        return None
    headers = input_data[0].keys()
    for entry in input_data:
        if (
            not hasattr(entry, "keys")
            or not hasattr(entry, "__iter__")
            or len(entry.keys()) != len(headers)
        ):
            return None
        for header in headers:
            if header not in entry:
                return None
    return headers


def convert_list_to_html_table(list_input) -> str:
    """This code is borrowed from json2html (MIT)"""
    if not list_input:
        return ""
    headers = html_table_header(list_input)
    if headers is not None:
        output = f"""
        <table>
        <thead>
            <tr>
                <th>{'</th><th>'.join(headers)}</th>
            </tr>
        </thead>
        <tbody>
        """
        for list_entry in list_input:
            output += f"""
            <tr>
                <td>
                {"</td><td>".join([convert_to_html_table(list_entry[header]) for header in headers])} # noqa
                </td>
            </tr>
            """
        output += "</tbody></table>"
        return output
    # list_input = basic list
    output = f"""
    <ul class="list">
        <li>
        {"</li><li>".join([convert_to_html_table(child) for child in list_input])}
        </li>
    </ul>
    """
    return output


def convert_dict_to_html_table(input_data) -> str:
    """This code is borrowed from json2html (MIT)"""
    if not input_data:
        return ""
    converted_output = f"""
    <table>
    <tr>
    {"</tr><tr>".join(
        [
            f"<th>{convert_to_html_table(k)}</th><td>{convert_to_html_table(v)}</td>"
            for k, v in input_data.items()
        ]
    )}
    </tr>
    </table>
    """
    return converted_output


def html_object(name: str, foldable_sections: Union[str, List[str]]) -> str:
    if isinstance(foldable_sections, str):
        foldable_sections = [foldable_sections]

    s = f"""<div class="enoslib_object">
                <div class="object_name">
                    {html_escape(name)}
                </div>
                <ul class="enoslist">
                    {"".join(foldable_sections)}
                </ul>
            </div>"""

    return s


def html_base(content: str) -> str:
    """Wrap an existing html representation, include the css stylesheet."""
    css = f"<style> {_load_css()} </style>"
    res = f"""
        {css}
        <div class="enoslib">
        {content}
        </div>
    """
    return res


def html_from_sections(
    class_name: str, sections: Union[str, List[str]], content_only=False
) -> str:
    html = html_object(class_name, sections)

    if content_only:
        return html

    return html_base(html)


def html_from_dict(class_name: str, content: dict, content_only=False) -> str:
    html = dict_to_html_foldable_sections(content)

    return html_from_sections(class_name, html, content_only=content_only)
