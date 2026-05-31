from __future__ import annotations


class SpiderFootAdapter:
    """Optional adapter for SpiderFoot (https://github.com/smicallef/spiderfoot).

    SpiderFoot is an open-source intelligence automation tool.
    Integration is done via JSON import/export — not as a runtime dependency.

    To install:
      git clone https://github.com/smicallef/spiderfoot /path/to/spiderfoot
      cd /path/to/spiderfoot && pip install -r requirements.txt

    Export workflow:
      1. Run SpiderFoot scan with desired modules
      2. Export results as JSON
      3. Import via: import_spiderfoot_json(path)
    """

    @property
    def available(self) -> bool:
        return False  # Stub — import-only

    @property
    def install_hint(self) -> str:
        return (
            "SpiderFoot adapter is a stub.\n"
            "  See: https://github.com/smicallef/spiderfoot\n"
            "  Export SpiderFoot results as JSON and import via import_json()."
        )

    def import_json(self, path: str) -> list[dict]:
        import json
        with open(path) as f:
            data = json.load(f)
        results = []
        for item in data if isinstance(data, list) else data.get("results", []):
            results.append({
                "source": item.get("source", ""),
                "type": item.get("type", ""),
                "data": item.get("data", ""),
                "module": item.get("module", ""),
            })
        return results
