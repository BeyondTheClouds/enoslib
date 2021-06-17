import pkg_resources
import uuid
from html import escape as html_escape


STATIC_FILES = "html/style.css"


def _load_css():
    return pkg_resources.resource_string("enoslib", STATIC_FILES).decode("utf8")


def dict_to_html(d: dict) -> str:
    html = ""
    for k, v in d.items():
        data_id = f"{k}-" + str(uuid.uuid4())
        if isinstance(v, dict):
            html += f"""
                    <input type="checkbox" id="{data_id}" class="att">
                    <label for="{data_id}">{k}</label>
                    <ul>
                    {dict_to_html(v)}
                    </ul>"""
        elif isinstance(v, list):
            tab = convert_to_html_table(v)
            li = f""" <li>
                        <input type="checkbox" id="{data_id}" class="att">
                        <label for="{data_id}">{k}</label>
                        {tab}
                        </li>"""
            html += li
        else:
            html += f"""
                        <li>
                        <input type="checkbox" id="{data_id}" class="att" disabled="">
                        <label for="{data_id}">
                            <span>{k}</span>
                        </label>
                        <span>{v}</span>
                        </li>"""
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
