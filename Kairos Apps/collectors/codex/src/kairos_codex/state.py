from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

STATE_VERSION = 1


class SyncStateError(ValueError):
	pass


@dataclass(frozen=True)
class FileFingerprint:
	mtime_ns: int
	size: int


@dataclass(frozen=True)
class SyncState:
	files: dict[str, FileFingerprint]


def default_state_path() -> Path:
	return Path.home() / ".local" / "state" / "kairos" / "codex-sync-state.json"


def load_state(path: Path) -> SyncState:
	if not path.exists():
		return SyncState(files={})

	try:
		payload = json.loads(path.read_text(encoding="utf-8"))
	except (OSError, json.JSONDecodeError) as error:
		raise SyncStateError(f"Could not read sync state {path}: {error}") from error

	if not isinstance(payload, dict) or payload.get("version") != STATE_VERSION:
		raise SyncStateError(f"Sync state {path} has an unsupported format.")

	files = payload.get("files")
	if not isinstance(files, dict):
		raise SyncStateError(f"Sync state {path} is missing file fingerprints.")

	parsed_files = {}
	for file_path, fingerprint in files.items():
		if not isinstance(file_path, str) or not isinstance(fingerprint, dict):
			raise SyncStateError(f"Sync state {path} contains an invalid file fingerprint.")
		mtime_ns = fingerprint.get("mtime_ns")
		size = fingerprint.get("size")
		if not isinstance(mtime_ns, int) or not isinstance(size, int):
			raise SyncStateError(f"Sync state {path} contains an invalid file fingerprint.")
		parsed_files[file_path] = FileFingerprint(mtime_ns=mtime_ns, size=size)

	return SyncState(files=parsed_files)


def changed_paths(paths: tuple[Path, ...], state: SyncState) -> tuple[Path, ...]:
	return tuple(path for path in paths if state.files.get(_path_key(path)) != fingerprint(path))


def save_state(path: Path, state: SyncState, paths: tuple[Path, ...]) -> None:
	try:
		updated_files = dict(state.files)
		for session_path in paths:
			updated_files[_path_key(session_path)] = fingerprint(session_path)

		payload = {
			"version": STATE_VERSION,
			"files": {file_path: asdict(value) for file_path, value in sorted(updated_files.items())},
		}
		path.parent.mkdir(parents=True, exist_ok=True)
		temporary_path = path.with_suffix(f"{path.suffix}.tmp")
		temporary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
		temporary_path.replace(path)
	except OSError as error:
		raise SyncStateError(f"Could not write sync state {path}: {error}") from error


def fingerprint(path: Path) -> FileFingerprint:
	stat = path.stat()
	return FileFingerprint(mtime_ns=stat.st_mtime_ns, size=stat.st_size)


def _path_key(path: Path) -> str:
	return str(path.resolve())
