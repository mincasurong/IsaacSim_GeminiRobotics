import os
import yaml

def generate_limits():
    import subprocess
    path = subprocess.check_output("bash -c 'source /opt/ros/jazzy/setup.bash && source /mnt/d/git/IsaacSim_Gemini/wsl_ws/install/setup.bash && ros2 pkg prefix franka_description'", shell=True).decode().strip()
    orig_file = os.path.join(path, 'share/franka_description/robots/fr3/joint_limits.yaml')
    
    with open(orig_file, 'r') as f:
        limits = yaml.safe_load(f)
    
    new_data = {'joint_limits': {}}
    for i in range(1, 4):
        prefix = f'fr3_{i}_'
        for joint, props in limits.items():
            if 'limit' in props:
                new_data['joint_limits'][f'{prefix}{joint}'] = {
                    'has_velocity_limits': True,
                    'max_velocity': props['limit']['velocity'],
                    'has_acceleration_limits': True,
                    'max_acceleration': props.get('position_based_velocity_limits', {}).get('deceleration_limit', 5.0)
                }
            
    # Add finger joints manually just in case
    for i in range(1, 4):
        prefix = f'fr3_{i}_'
        new_data['joint_limits'][f'{prefix}finger_joint1'] = {
            'has_velocity_limits': True, 'max_velocity': 0.1,
            'has_acceleration_limits': True, 'max_acceleration': 0.1
        }
        new_data['joint_limits'][f'{prefix}finger_joint2'] = {
            'has_velocity_limits': True, 'max_velocity': 0.1,
            'has_acceleration_limits': True, 'max_acceleration': 0.1
        }
            
    out_dir = '/mnt/d/git/IsaacSim_Gemini/wsl_ws/src/multi_robot_moveit_config/config'
    with open(os.path.join(out_dir, 'joint_limits.yaml'), 'w') as f:
        yaml.dump(new_data, f)
    print("Joint limits generated successfully.")

if __name__ == '__main__':
    generate_limits()
