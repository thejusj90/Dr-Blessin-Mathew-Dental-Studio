from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    database_path: Path
    batch_size: int
    effort: str
    max_cost: float
    poll_seconds: float = 2.0

    @classmethod
    def load(cls):
        effort = os.getenv("EXA_EFFORT", "medium")
        if effort not in {"low", "medium", "high", "auto"}:
            raise ValueError("EXA_EFFORT must be low, medium, high, or auto")
        db = Path(os.getenv("DATABASE_PATH", "data/prospects.db"))
        if not db.is_absolute(): db = ROOT / db
        return cls(db, int(os.getenv("EXA_BATCH_SIZE", "10")), effort,
                   float(os.getenv("EXA_MAX_COST_DOLLARS", "5")))

