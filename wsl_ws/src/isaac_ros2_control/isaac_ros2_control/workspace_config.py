import sys
from pathlib import Path
import numpy as np

WORKSPACE = {
    'robots': {
        'FR3_1': {
            'base_xy': np.array([0.0, -0.45]),
            'table_center': np.array([0.0, -1.05]),
            'quadrant': 'bottom',
        },
        'FR3_2': {
            'base_xy': np.array([0.3897, 0.225]),
            'table_center': np.array([0.909, 0.525]),
            'quadrant': 'top-right',
        },
        'FR3_3': {
            'base_xy': np.array([-0.3897, 0.225]),
            'table_center': np.array([-0.909, 0.525]),
            'quadrant': 'top-left',
        },
    },
    'central_table': {
        'center': np.array([0.0, 0.0]),
        'bounds': ((-0.15, 0.15), (-0.15, 0.15)),
    },
    'block_height': 0.045,
    'table_surface_z': 0.30,
    'conveyor_speed': 0.08,
    'conveyor_direction': np.array([1.0, 0.0, 0.0]),
    'conveyor_surface_z': 0.50,
    'buffer_table_z': 0.32,
}

for _cand in (
    Path(__file__).resolve().parents[4] / "private" / "research" / "stamp_v2_sota",
):
    if _cand.is_dir():
        if str(_cand) not in sys.path:
            sys.path.insert(0, str(_cand))
        try:
            from sota_v2_overlay import SOTA_V2_WORKSPACE_OVERLAY

            WORKSPACE.update(SOTA_V2_WORKSPACE_OVERLAY)
        except Exception:
            pass
        break
