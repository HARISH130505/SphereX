"""Application product keys are distinct from unchanged archive provenance."""
from urllib.parse import quote, urlsplit, urlunsplit


def product_id(obs_id: str, band: str) -> str:
    return f"{quote(obs_id, safe='')}::{quote(band, safe='')}"


def archive_product_id(cutout_url: str, publisher_did: str | None = None) -> str | None:
    if publisher_did:
        return publisher_did
    parts = urlsplit(cutout_url)
    if parts.scheme and parts.netloc and parts.path:
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return None


class AmbiguousObservationError(ValueError):
    def __init__(self, identifier, candidates):
        self.identifier = identifier
        self.product_ids = sorted(o.product_id for o in candidates)
        super().__init__(f"Ambiguous observation ID {identifier!r}; select an explicit product_id")
