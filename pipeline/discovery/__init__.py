"""Discovery sources. Importing this package registers every source.

Keep imports here so `import pipeline.discovery` wires up the registry.
"""
from pipeline.discovery import sec_edgar        # noqa: F401
from pipeline.discovery import propublica_990    # noqa: F401
from pipeline.discovery import news              # noqa: F401
from pipeline.discovery import opencorporates    # noqa: F401
from pipeline.discovery import cik_registry      # noqa: F401
from pipeline.discovery import wikidata_fo        # noqa: F401
