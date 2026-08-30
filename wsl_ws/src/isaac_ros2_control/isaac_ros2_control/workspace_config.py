# isaac_ros2_control/workspace_config.py
import numpy as np

WORKSPACE = {
    'robots': {
        'FR3_1': {
            'base_xy': np.array([0.0, -0.45]),
            'table_center': np.array([0.0, -1.05]),
            'quadrant': 'bottom'
        },
        'FR3_2': {
            'base_xy': np.array([0.3897, 0.225]),
            'table_center': np.array([0.909, 0.525]),
            'quadrant': 'top-right'
        },
        'FR3_3': {
            'base_xy': np.array([-0.3897, 0.225]),
            'table_center': np.array([-0.909, 0.525]),
            'quadrant': 'top-left'
        },
    },
    'central_table': {
        'center': np.array([0.0, 0.0]),
        'bounds': ((-0.15, 0.15), (-0.15, 0.15))
    },
    'block_height': 0.06,
    'table_surface_z': 0.30,
}
