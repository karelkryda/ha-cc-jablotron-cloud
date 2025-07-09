from typing import TypedDict

from jablotronpy import JablotronSections

JablotronServiceData = TypedDict(
    "JablotronServiceData",
    {
        "name": str,
        "type": str,
        "alarm": JablotronSections
    }
)
