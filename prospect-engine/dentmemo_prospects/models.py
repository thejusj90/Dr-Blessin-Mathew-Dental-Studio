from dataclasses import dataclass, field, asdict
from typing import Any

@dataclass
class Dentist:
    dentist_id: str
    registration_number: str
    original_name: str
    normalized_name: str
    source_state: str
    source_city: str = ""
    source_address: str = ""
    source_file: str = ""
    source: str = "registry"
    import_batch: str = ""
    def asdict(self): return asdict(self)

@dataclass
class Enrichment:
    input_dentist_id: str
    dentist_name: str
    google_business_presence: str = "unknown"
    practice_owner_likelihood: str = "unknown"
    confidence: float = 0.0
    values: dict[str, Any] = field(default_factory=dict)

