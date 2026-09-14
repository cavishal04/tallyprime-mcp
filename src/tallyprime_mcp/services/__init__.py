"""Service layer: maps TallyClient's raw TallyRecord data onto the project's
Pydantic domain models. Kept separate from tallyprime_mcp.tally so that
"talk to Tally" and "shape the response" can be tested and changed
independently.
"""

from __future__ import annotations
