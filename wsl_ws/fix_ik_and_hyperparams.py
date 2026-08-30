# -*- coding: utf-8 -*-
import sys
import re

f = 'wsl_ws/src/isaac_ros2_control/isaac_ros2_control/multi_robot_controller.py'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

# 1. Revert _compute_j1_for_target to pure arctan2
j1_old = """
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
j1_new = """
    def _compute_j1_for_target(self, robot_id, target_pos_local):
        # Using pure arctan2 to prevent Joint 1 limit violations ([-2.89, 2.89])
        return np.arctan2(target_pos_local[1], target_pos_local[0])
"""
content = content.replace(j1_old.strip('\n'), j1_new.strip('\n'))

# 2. Add hyperparameter support in action_cb
action_cb_pick_old = """
            if action == 'pick':
                target_label = cmd.get('target', '')
                block_name = self._resolve_block_name(target_label)
                if not block_name:
                    self._publish_result(False, f"Could not map target '{target_label}' to a block prim.", f"FR3_{r_id}")
                    return
                setattr(self, f'active_target{r_id}', block_name)
                setattr(self, f'rotation_dir{r_id}', cmd.get('rotation_dir', 'shortest'))
                self._set_state(r_id, 'INIT')
"""
action_cb_pick_new = """
            if action == 'pick':
                target_label = cmd.get('target', '')
                block_name = self._resolve_block_name(target_label)
                if not block_name:
                    self._publish_result(False, f"Could not map target '{target_label}' to a block prim.", f"FR3_{r_id}")
                    return
                setattr(self, f'active_target{r_id}', block_name)
                
                # Dynamic Hyperparameters
                speed = cmd.get('speed', 'normal')
                if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 30)
                elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 90)
                else: setattr(self, f'steps_per_phase{r_id}', 60)
                
                setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', 0.1)))
                self._set_state(r_id, 'INIT')
"""
content = content.replace(action_cb_pick_old.strip('\n'), action_cb_pick_new.strip('\n'))

action_cb_place_old = """
            elif action == 'place':
                setattr(self, f'target_x{r_id}', cmd.get('x', 0.0))
                setattr(self, f'target_y{r_id}', cmd.get('y', 0.0))
                setattr(self, f'rotation_dir{r_id}', cmd.get('rotation_dir', 'shortest'))
                curr_state = getattr(self, f'state{r_id}')
"""
action_cb_place_new = """
            elif action == 'place':
                setattr(self, f'target_x{r_id}', cmd.get('x', 0.0))
                setattr(self, f'target_y{r_id}', cmd.get('y', 0.0))
                
                # Dynamic Hyperparameters
                speed = cmd.get('speed', 'normal')
                if speed == 'fast': setattr(self, f'steps_per_phase{r_id}', 30)
                elif speed == 'slow': setattr(self, f'steps_per_phase{r_id}', 90)
                else: setattr(self, f'steps_per_phase{r_id}', 60)
                
                setattr(self, f'hover_height{r_id}', float(cmd.get('approach_height', 0.1)))
                curr_state = getattr(self, f'state{r_id}')
"""
content = content.replace(action_cb_place_old.strip('\n'), action_cb_place_new.strip('\n'))


# 3. Ensure steps_per_phase{r_id} is used during timer
timer_old = """
            # Determine duration for this phase
            total_steps = self.dwell_steps if state in ['GRASP', 'RELEASE'] else self.steps_per_phase
"""
timer_new = """
            # Determine duration for this phase
            robot_steps = getattr(self, f'steps_per_phase{r_id}', self.steps_per_phase)
            total_steps = self.dwell_steps if state in ['GRASP', 'RELEASE'] else robot_steps
"""
content = content.replace(timer_old.strip('\n'), timer_new.strip('\n'))

# 4. Use custom hover height
hover_pick_old = """
                elif state == 'ROTATE_TO_PICK':
                    block_pos, block_quat = self.get_block_local_pose(robot_id)
                    if block_pos is None: return
                    hover_pick_pos = np.array([block_pos[0], block_pos[1], block_pos[2] + self.hover_height])
"""
hover_pick_new = """
                elif state == 'ROTATE_TO_PICK':
                    block_pos, block_quat = self.get_block_local_pose(robot_id)
                    if block_pos is None: return
                    hover_h = getattr(self, f'hover_height{robot_id}', self.hover_height)
                    hover_pick_pos = np.array([block_pos[0], block_pos[1], block_pos[2] + hover_h])
"""
content = content.replace(hover_pick_old.strip('\n'), hover_pick_new.strip('\n'))

hover_place_old = """
                elif state == 'ROTATE_TO_PLACE':
                    place_pos, place_quat = self.get_place_local_pose(robot_id)
                    if place_pos is None: return
                    hover_place_pos = np.array([place_pos[0], place_pos[1], place_pos[2] + self.hover_height])
"""
hover_place_new = """
                elif state == 'ROTATE_TO_PLACE':
                    place_pos, place_quat = self.get_place_local_pose(robot_id)
                    if place_pos is None: return
                    hover_h = getattr(self, f'hover_height{robot_id}', self.hover_height)
                    hover_place_pos = np.array([place_pos[0], place_pos[1], place_pos[2] + hover_h])
"""
content = content.replace(hover_place_old.strip('\n'), hover_place_new.strip('\n'))

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Updated multi_robot_controller.py successfully.")
