# -*- coding: utf-8 -*-
import sys
import re

f = 'wsl_ws/src/isaac_ros2_control/isaac_ros2_control/multi_robot_controller.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

func1 = """
    def _compute_j1_for_target(self, robot_id, target_pos_local):
        target_angle = np.arctan2(target_pos_local[1], target_pos_local[0])
        rot_dir = getattr(self, f'rotation_dir{robot_id}', 'shortest')
        
        q_current = getattr(self, f'q_current{robot_id}')
        j1_current = q_current[0]
        
        # normalize target_angle to be near j1_current
        diff = (target_angle - j1_current) % (2*np.pi)
        if diff > np.pi:
            diff -= 2*np.pi
        target_angle = j1_current + diff
        
        if rot_dir == 'cw':
            if target_angle > j1_current:
                target_angle -= 2*np.pi
        elif rot_dir == 'ccw':
            if target_angle < j1_current:
                target_angle += 2*np.pi
                
        return target_angle
"""
content = re.sub(
    r'    def _compute_j1_for_target\(self, robot_id, target_pos_local\):\s*return np.arctan2\(target_pos_local\[1\], target_pos_local\[0\]\)',
    func1.strip('\n'),
    content
)

# Also patch the __init__ to include rotation_dir1
init_patch = """
        self.q_current3 = list(self.q_home_fr3)
        
        self.rotation_dir1 = 'shortest'
        self.rotation_dir2 = 'shortest'
        self.rotation_dir3 = 'shortest'

        self.state1 = 'INIT'
"""
content = content.replace(
    "        self.q_current3 = list(self.q_home_fr3)\n\n        self.state1 = 'INIT'",
    init_patch.strip('\n')
)

# And action_cb
action_cb_patch = """
            if action == 'pick':
                target_label = cmd.get('target', '')
                block_name = self._resolve_block_name(target_label)
                if not block_name:
                    self._publish_result(False, f"Could not map target '{target_label}' to a block prim.", f"FR3_{r_id}")
                    return
                setattr(self, f'active_target{r_id}', block_name)
                setattr(self, f'rotation_dir{r_id}', cmd.get('rotation_dir', 'shortest'))
                self._set_state(r_id, 'INIT')

            elif action == 'place':
                setattr(self, f'target_x{r_id}', cmd.get('x', 0.0))
                setattr(self, f'target_y{r_id}', cmd.get('y', 0.0))
                setattr(self, f'rotation_dir{r_id}', cmd.get('rotation_dir', 'shortest'))
                curr_state = getattr(self, f'state{r_id}')
"""
content = re.sub(
    r'            if action == .pick.:\n.*?(?=elif action == .place.:)',
    """            if action == 'pick':
                target_label = cmd.get('target', '')
                block_name = self._resolve_block_name(target_label)
                if not block_name:
                    self._publish_result(False, f"Could not map target '{target_label}' to a block prim.", f"FR3_{r_id}")
                    return
                setattr(self, f'active_target{r_id}', block_name)
                setattr(self, f'rotation_dir{r_id}', cmd.get('rotation_dir', 'shortest'))
                self._set_state(r_id, 'INIT')

""", content, flags=re.DOTALL
)

content = re.sub(
    r'            elif action == .place.:\n.*?(?=curr_state = getattr)',
    """            elif action == 'place':
                setattr(self, f'target_x{r_id}', cmd.get('x', 0.0))
                setattr(self, f'target_y{r_id}', cmd.get('y', 0.0))
                setattr(self, f'rotation_dir{r_id}', cmd.get('rotation_dir', 'shortest'))
                """, content, flags=re.DOTALL
)

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Updated multi_robot_controller.py successfully.")
