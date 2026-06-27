"""SharePoint READ tool -- STUBBED on purpose.

The brief explicitly allows empty functions with descriptive comments where real
integration would be time-consuming. The tool is still *registered* with the same
contract so it appears in the manifest and proves the pattern generalizes; only
the handler body is deferred.

Production: call Microsoft Graph with the user's OBO-exchanged Graph token, e.g.
``POST https://graph.microsoft.com/v1.0/search/query`` with an entityTypes filter
for driveItem/listItem, then map hits to {title, url, last_modified}. Because the
call uses the user's delegated token, SharePoint trims results to documents the
user is permitted to open -- no extra authorization code needed here.
"""
from __future__ import annotations

from ..core.identity import DownstreamToken
from ..core.policy import ToolKind, Risk
from ..core.registry import Tool, register


def _search_documents(token: DownstreamToken, args: dict) -> dict:
    raise NotImplementedError("SharePoint search is stubbed for this POC")


register(Tool(
    name="sharepoint.search_documents",
    system="sharepoint",
    kind=ToolKind.READ,
    risk=Risk.LOW,
    description="Search SharePoint for documents related to an account (stubbed).",
    input_schema={"query": {"type": "string", "required": True, "min_length": 2, "max_length": 200}},
    handler=_search_documents,
))
