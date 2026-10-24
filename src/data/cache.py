from __future__ import annotations
from pathlib import Path
import hashlib
import pandas as pd
class CsvCache:
    def __init__(self, directory: str = ".cache/market-data"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
    def _path(self, key: str) -> Path:
        safe = hashlib.sha256(key.encode()).hexdigest()
        return self.directory / f"{safe}.csv"
    def get(self, key: str) -> pd.DataFrame | None:
        path = self._path(key)
        if not path.exists(): return None
        try:
            frame = pd.read_csv(path, index_col=0, parse_dates=True)
            return frame if not frame.empty else None
        except (OSError, ValueError, pd.errors.ParserError):
            return None
    def put(self, key: str, frame: pd.DataFrame) -> None:
        if frame is None or frame.empty: return
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        frame.to_csv(tmp)
        tmp.replace(path)
