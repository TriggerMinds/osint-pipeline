from __future__ import annotations

from typing import Optional


class PhotonAdapter:
    """Optional adapter for Photon (https://github.com/s0md3v/Photon).

    Photon is an external OSINT crawler for extracting URLs, emails,
    social media handles, etc. from a target domain.

    To install:
      git clone https://github.com/s0md3v/Photon /path/to/photon
      pip install -r /path/to/photon/requirements.txt

    Usage (manual):
      python /path/to/photon/photon.py -u https://example.com -o output.json
    """

    def __init__(self, binary_path: str = "photon") -> None:
        self.binary = binary_path

    @property
    def available(self) -> bool:
        return False  # Stub — not implemented

    @property
    def install_hint(self) -> str:
        return (
            "Photon adapter is a stub.\n"
            "  See: https://github.com/s0md3v/Photon\n"
            "  Manual integration required via file-based JSON import."
        )

    async def run(self, url: str, output: str = "photon_output.json") -> list[dict]:
        raise NotImplementedError(self.install_hint)
