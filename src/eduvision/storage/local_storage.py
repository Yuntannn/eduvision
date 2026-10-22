import uuid
from pathlib import Path


class LocalStorage:
    """Stores uploaded files on local disk under generated names."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)

    def save(self, data: bytes, extension: str) -> str:
        """Write `data` under a generated `{uuid}.{ext}` name and return that name."""
        self._base_dir.mkdir(parents=True, exist_ok=True)
        stored_filename = f"{uuid.uuid4()}.{extension.lstrip('.').lower()}"
        (self._base_dir / stored_filename).write_bytes(data)
        return stored_filename

    def read(self, stored_filename: str) -> bytes:
        if Path(stored_filename).name != stored_filename:
            raise ValueError("Invalid stored filename.")
        return (self._base_dir / stored_filename).read_bytes()
