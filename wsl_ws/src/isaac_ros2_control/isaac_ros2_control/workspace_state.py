import numpy as np
from rclpy.duration import Duration
import rclpy

try:
    from isaac_ros2_control.workspace_config import WORKSPACE
except ImportError:
    try:
        from .workspace_config import WORKSPACE
    except ImportError:
        from workspace_config import WORKSPACE

class WorkspaceState:
    def __init__(self):
        self.block_status = {f'Block{i}': {'location': 'unknown', 'pos': None} for i in range(1, 10)}
        self.robot_status = {r: 'idle' for r in WORKSPACE['robots']}
        self.tower_height = 0
        self.blocks_on_tower = []
        self.action_history = []
        
    def update_from_tf(self, tf_buffer):
        """Query TF to update block positions and tower state."""
        target_x, target_y = WORKSPACE['central_table']['center']
        
        tower_blocks = []
        max_block_z = 0.0
        
        for block_name in self.block_status:
            try:
                trans = tf_buffer.lookup_transform('world', block_name, rclpy.time.Time(), timeout=Duration(seconds=0.05))
                x = trans.transform.translation.x
                y = trans.transform.translation.y
                z = trans.transform.translation.z
                
                self.block_status[block_name]['pos'] = (x, y, z)
                
                # Determine location
                dist_to_center = np.hypot(x - target_x, y - target_y)
                if dist_to_center < 0.045 and z >= 0.28:
                    self.block_status[block_name]['location'] = 'tower'
                    tower_blocks.append((block_name, z))
                    if z > max_block_z:
                        max_block_z = z
                elif z > 0.4:
                    self.block_status[block_name]['location'] = 'held'
                else:
                    self.block_status[block_name]['location'] = 'table'
            except Exception:
                pass
                
        tower_blocks.sort(key=lambda item: item[1])
        self.blocks_on_tower = [b[0] for b in tower_blocks]
        self.tower_height = len(self.blocks_on_tower)
        
    def record_action(self, action, success, message):
        self.action_history.append({'action': action, 'success': success, 'message': message})
        if len(self.action_history) > 5:
            self.action_history.pop(0)
            
    def set_robot_status(self, robot_id, status):
        if robot_id in self.robot_status:
            self.robot_status[robot_id] = status
            
    def get_summary(self):
        """Return a structured dictionary for Gemini."""
        available_blocks = {r: [] for r in WORKSPACE['robots']}
        
        for block_name, status in self.block_status.items():
            if status['location'] == 'table' and status['pos'] is not None:
                x, y, _ = status['pos']
                
                # Find closest robot
                closest_robot = None
                min_dist = float('inf')
                for r, r_cfg in WORKSPACE['robots'].items():
                    dist = np.hypot(x - r_cfg['base_xy'][0], y - r_cfg['base_xy'][1])
                    if dist < min_dist:
                        min_dist = dist
                        closest_robot = r
                
                if closest_robot:
                    available_blocks[closest_robot].append({
                        'name': block_name,
                        'distance_m': round(min_dist, 3)
                    })
        
        for r in available_blocks:
            available_blocks[r].sort(key=lambda b: b['distance_m'])
            
        return {
            'tower': {
                'layers': self.tower_height,
                'blocks': self.blocks_on_tower
            },
            'available_blocks': available_blocks,
            'robots': self.robot_status,
            'recent_history': self.action_history,
            'progress': f"{self.tower_height}/9 blocks placed ({int(self.tower_height/9*100)}%)"
        }
