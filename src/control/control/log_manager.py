from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Sequence


class LogManager:
    """
    Minimal JSON logger that packages CSI data with the latest Pose and writes as NDJSON (one JSON object per line).

    Entry shape:
    {
        "t": <epoch_seconds>,
        "pose": {"position": [x,y,z], "orientation": [w,x,y,z]},
        "csi":   {"amplitude": [...], "phase": [...], "num_subcarriers": N}
    }
    """

    def __init__(self, file_path: Path | str):
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # open in text mode, utf-8
        self._fh = self.path.open('w', encoding='utf-8')
        self._fh.write("# CSI+Pose NDJSON log\n")
        self._fh.flush()
        self._latest_pose_pos: Optional[Sequence[float]] = None
        self._latest_pose_quat: Optional[Sequence[float]] = None
        self._is_closed = False

    def close(self):
        if not self._is_closed:
            try:
                self._fh.flush()
            finally:
                self._fh.close()
                self._is_closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # ------------------------ Pose/CSI API ------------------------
    def update_pose(self, position: Sequence[float], quaternion: Sequence[float]):
        self._latest_pose_pos = list(map(float, position))
        self._latest_pose_quat = list(map(float, quaternion))

    def log_csi(self, amplitude: Sequence[float], phase: Sequence[float], num_subcarriers: int):
        entry = {
            "t": time.time(),
            "pose": {
                "position": self._latest_pose_pos if self._latest_pose_pos is not None else None,
                "orientation": self._latest_pose_quat if self._latest_pose_quat is not None else None,
            },
            "csi": {
                "amplitude": list(map(float, amplitude)),
                "phase": list(map(float, phase)),
                "num_subcarriers": int(num_subcarriers),
            },
        }
        self._fh.write(json.dumps(entry) + "\n")
        # Light flush for safety without too much overhead
        self._fh.flush()
