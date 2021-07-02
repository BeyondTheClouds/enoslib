from typing import List, Union
import pkg_resources
import uuid
from html import escape as html_escape


STATIC_FILES = "html/style.css"


def _load_css():
    return pkg_resources.resource_string("enoslib", STATIC_FILES).decode("utf8")


def html_object(name: str, foldable_sections: Union[str, List[str]]):
    if isinstance(foldable_sections, str):
        foldable_sections = [foldable_sections]

    s = f"""<div class="enoslib_object">
            <div class="object_name">
                {html_escape(name)}
            </div>
            <ul class="list">
                {"".join(foldable_sections)}
            </ul>
                </div>"""

    return s


def foldable_section(name: str, html_objects: Union[str, List[str]], extra: str = ""):
    """Generate a foldable section."""

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
                    <ul id="{name}">
                        {"".join(html_objects)}
                    </ul>
                </li>
                """


def inline_value(key: str, value: str):
    data_id = f"{key}-" + str(uuid.uuid4())
    return f"""
        <li>
        <input type="checkbox" id="{data_id}" class="att" disabled="">
        <label for="{data_id}">
            <span>{key}</span>
        </label>
        <span>{value}</span>
        </li>"""


def dict_to_html(d: dict) -> str:
    html = ""
    for k, v in d.items():
        if isinstance(v, dict) or hasattr(v, "keys"):
            # foldable_section
            html += foldable_section(k, dict_to_html(v), extra=str(len(v)))
        elif isinstance(v, list):
            tab = convert_to_html_table(v)
            # table_section
            html += foldable_section(k, tab, extra=str(len(v)))
        else:
            # line_section
            html += inline_value(k, v)
    return html


def convert_to_html_table(input):
    if isinstance(input, str):
        return html_escape(str(input))
    if isinstance(input, dict):
        return convert_dict(input)
    if hasattr(input, "__iter__") and hasattr(input, "__getitem__"):
        return convert_list_to_html(input)
    return html_escape(str(input))


def html_table_header(input):
    """This code is borrowed from json2html (MIT)"""
    if not input or not hasattr(input, "__getitem__") or not hasattr(input[0], "keys"):
        return None
    headers = input[0].keys()
    for entry in input:
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


def convert_list_to_html(list_input):
    """This code is borrowed from json2html (MIT)"""
    table_init_tag = "<table>"
    if not list_input:
        return ""
    output = ""
    headers = html_table_header(list_input)
    if headers is not None:
        output += table_init_tag
        output += "<thead>"
        output += "<tr><th>" + "</th><th>".join(headers) + "</th></tr>"
        output += "</thead>"
        output += "<tbody>"
        for list_entry in list_input:
            output += "<tr><td>"
            output += "</td><td>".join(
                [convert_to_html_table(list_entry[header]) for header in headers]
            )
            output += "</td></tr>"
        output += "</tbody>"
        output += "</table>"
        return output
    # list_input = basic list
    output = "<ul><li>"
    output += "</li><li>".join([convert_to_html_table(child) for child in list_input])
    output += "</li></ul>"
    return output


def convert_dict(input):
    """This code is borrowed from json2html (MIT)"""
    table_init_tag = "<table>"
    if not input:
        return ""
    converted_output = table_init_tag + "<tr>"
    converted_output += "</tr><tr>".join(
        [
            "<th>%s</th><td>%s</td>"
            % (convert_to_html_table(k), convert_to_html_table(v))
            for k, v in input.items()
        ]
    )
    converted_output += "</tr></table>"
    return converted_output


def html_from_dict(class_name: str, content: dict, content_only=False):
    html = dict_to_html(content)
    html = html_object(class_name, html)

    if content_only:
        return html

    return html_base(html)


def html_from_section(
    class_name: str, content: Union[str, List[str]], content_only=False
):
    html = html_object(class_name, content)

    if content_only:
        return html

    return html_base(html)


def html_base(content: str):
    css = f"<style> {_load_css()} </style>"
    res = f"""
        {css}
        <div class="enoslib">
        {content}
        </div>
    """
    return res
