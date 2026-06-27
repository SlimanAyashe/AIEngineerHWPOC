"""AI Sales Assistant -- connector / tool POC.

Importing this package registers every tool (read and write, across all systems)
into the central registry via each connector module's module-level ``register()``
calls. After ``import connectors`` the registry is fully populated and
``connectors.core.registry.invoke`` / ``manifest`` are ready to use.
"""
from .salesforce import reads as _sf_reads      # noqa: F401
from .salesforce import writes as _sf_writes    # noqa: F401
from .jira import writes as _jira_writes        # noqa: F401
from .sharepoint import reads as _sp_reads      # noqa: F401
