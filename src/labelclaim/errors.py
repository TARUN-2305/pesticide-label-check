"""Exception taxonomy (L1 §9). Every error the build can raise derives from LabelClaimError."""


class LabelClaimError(Exception):
    """Base class for all labelclaim errors."""


class ManifestError(LabelClaimError):
    """The source manifest is malformed."""


class SourceIntegrityError(LabelClaimError):
    """A source document does not match its pinned SHA-256."""


class SourceUnavailableError(LabelClaimError):
    """A source document could not be obtained (offline cache miss, network failure)."""


class ProvenanceError(LabelClaimError):
    """A stored value cannot be re-derived from its recorded bounding boxes (a bug, not data)."""


class AnomalyBudgetExceeded(LabelClaimError):
    """A release build found anomalies that are not on the reviewed allow-list."""


class CorrectionError(LabelClaimError):
    """A reviewed correction is malformed, stale (matches no row) or ambiguous (matches several)."""
