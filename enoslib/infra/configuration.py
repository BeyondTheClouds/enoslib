import jsonschema
import logging
import json
from typing import Dict, Optional, Any, Union
from json2html import *

logger = logging.getLogger(__name__)


class BaseConfiguration:
    """Base class for all the provider configuration object.

    This should be used as it is.
    """

    # Setting this is defered to the inherited classes
    _SCHEMA: Optional[Dict[Any, Any]] = None

    def __init__(self):
        # A configuration has a least these two
        self.machines = []
        self.networks = []

        # Filling up with the right machine and network
        # constructor is deferred to the sub classes.
        self._machine_cls = str
        self._network_cls = str

    @classmethod
    def from_dictionnary(cls, dictionnary, validate=True):
        """Alternative constructor. Build the configuration from a
        dictionnary."""
        pass

    @classmethod
    def from_settings(cls, **kwargs):
        """Alternative constructor. Build the configuration from a
        the kwargs."""
        self = cls()
        self.set(**kwargs)
        return self

    @classmethod
    def validate(cls, dictionnary):
        jsonschema.validate(dictionnary, cls._SCHEMA)

    def to_dict(self):
        return {}

    def finalize(self):
        d = self.to_dict()
        import json
        logger.debug(json.dumps(d, indent=4))
        self.validate(d)
        return self

    def set(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        return self

    def add_machine_conf(self, machine):
        self.machines.append(machine)
        return self

    def add_machine(self, *args, **kwargs):
        self.machines.append(self._machine_cls(**kwargs))
        return self

    def add_network_conf(self, network):
        self.networks.append(network)
        return self

    def add_network(self, *args, **kwargs):
        self.networks.append(self._network_cls(*args, **kwargs))
        return self

    def __repr__(self):
        r = f"Conf@{hex(id(self))}\n"
        r += json.dumps(self.to_dict(), indent=4)
        return r

    def dict_to_html(self, d: dict) -> str:
        html = ""
        for k, v in d.items():
            if isinstance(v, dict):
                html += f"""
                    <input type="checkbox" id="{k}" class="att">
                    <label for="{k}">{k}</label>
                    <ul>
                    {self.dict_to_html(v)}
                    </ul>"""
            elif isinstance(v, list):
                tab = json2html.convert(json = v, table_attributes="")
                li = f""" <li>
                        <input type="checkbox" id="{k}" class="att">
                        <label for="{k}">{k}</label>
                        {tab}
                    """
                html += li
            else:
                html += f"""
                        <li>
                        <input type="checkbox" id="{k}" class="att" disabled="">
                        <label for="{k}">
                            <span>{k}</span>
                        </label>
                        <span>{v}</span>
                        </li>"""
        return html

    def _repr_html_(self) -> str:
        li = self.dict_to_html(self.to_dict())
        css = """     <style>
        .glob_conf {
            width: 540px;
            font-size: 75%;
            line-height: 1.5;
            background-color: #fff;
            font-family:'Segoe UI';
        }

        .glob_conf ul {
            padding: 0;
        }

        .glob_conf input+label {
            margin-bottom: 0%;
        }

        .Conf {
            padding: 6px 0 6px 3px;
            border-bottom-width: 1px;
            border-bottom-style: solid;
            border-bottom-color: #777;
            color: #555;
        }

        .Conf>div,
        .Conf>ul {
            display: inline;
            margin-top: 0;
            margin-bottom: 0;
        }

        ul.liste_conf {
            list-style: none !important;
            padding: 3px !important;
            margin: 0 !important;
        }



        input.att+label {
            display: inline-block;
            width: 140px;
            color: #555;
            font-weight: 500;
            padding: 4px 0 2px 0;
        }

        input.att:enabled+label,
        input.data_machine:enabled+label {
            cursor: pointer;
        }

        input.att,
        input.data_machine {
            display: none;
        }

        input.att+label:before {
            display: inline-block;
            content: '➕';
            font-size: 11px;
            width: 15px;
            text-align: center;
        }

        input.att:checked+label:before {
            content: '➖';
        }

        input.att:disabled+label:before {
            content: '►';
        }

        input.att+label>span {
            display: inline-block;
            margin-left: 4px;
        }



        input.att~ul {
            display: none;
        }

        input.att:checked~ul {
            display: block;
        }

        table {
            width: auto;
            border-collapse: collapse;
            margin: auto;
        }


        td,
        th {
            text-align: center;
            padding: 8px;
            height: 15px;
        }

        tr:nth-child(even) {
            background-color: #f2f2f2;
        }


        input~ul {
            
            position: relative;
            left: 25px;
        }

        input.att~table {
            display: none;
        }

        input.att:checked~table {
            display: block;

        }
        ul{
            list-style: none;
        }
    </style>"""

        res = f"""
            {css}
            <div class="glob_conf">
            <div class="Conf">Configuration</div>
            <ul class="liste_conf">
                {li}
            </ul>
             </div>"""

        return res
