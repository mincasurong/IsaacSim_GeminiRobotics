import os

def generate_srdf():
    srdf = '<?xml version="1.0" encoding="UTF-8"?>\n'
    srdf += '<robot name="three_robot_scene">\n'

    # Define groups
    for i in range(1, 4):
        prefix = f'fr3_{i}_'
        
        # Arm group
        srdf += f'  <group name="{prefix}arm">\n'
        srdf += f'    <chain base_link="{prefix}link0" tip_link="{prefix}hand_tcp"/>\n'
        srdf += f'  </group>\n'
        
        # Hand group
        srdf += f'  <group name="{prefix}hand">\n'
        srdf += f'    <link name="{prefix}hand"/>\n'
        srdf += f'    <link name="{prefix}leftfinger"/>\n'
        srdf += f'    <link name="{prefix}rightfinger"/>\n'
        srdf += f'  </group>\n'

        # End effector
        srdf += f'  <end_effector name="{prefix}hand_tcp" parent_link="{prefix}hand_tcp" group="{prefix}hand" parent_group="{prefix}arm"/>\n'
        
        # Group states (Home pose)
        srdf += f'  <group_state name="{prefix}home" group="{prefix}arm">\n'
        srdf += f'    <joint name="{prefix}joint1" value="0.0"/>\n'
        srdf += f'    <joint name="{prefix}joint2" value="-0.7854"/>\n'
        srdf += f'    <joint name="{prefix}joint3" value="0.0"/>\n'
        srdf += f'    <joint name="{prefix}joint4" value="-2.356"/>\n'
        srdf += f'    <joint name="{prefix}joint5" value="0.0"/>\n'
        srdf += f'    <joint name="{prefix}joint6" value="1.571"/>\n'
        srdf += f'    <joint name="{prefix}joint7" value="0.7854"/>\n'
        srdf += f'  </group_state>\n'

    # Disable adjacent collisions for each arm
    # Note: For strict correctness, we disable collisions only between known adjacent links in the chain
    # plus common internal intersections for Franka.
    for i in range(1, 4):
        p = f'fr3_{i}_'
        links = ['link0', 'link1', 'link2', 'link3', 'link4', 'link5', 'link6', 'link7', 'link8', 'hand', 'leftfinger', 'rightfinger']
        
        # Adjacent links
        for j in range(len(links)-1):
            if links[j] != 'hand':
                srdf += f'  <disable_collisions link1="{p}{links[j]}" link2="{p}{links[j+1]}" reason="Adjacent"/>\n'
        
        # Extra common internal safe pairs
        safe_pairs = [
            ('link0', 'link2'), ('link1', 'link3'), ('link2', 'link4'), 
            ('link3', 'link5'), ('link4', 'link6'), ('link5', 'link7'), 
            ('link6', 'hand'), ('link7', 'hand'), ('link7', 'leftfinger'), 
            ('link7', 'rightfinger'), ('hand', 'leftfinger'), ('hand', 'rightfinger'),
            ('leftfinger', 'rightfinger')
        ]
        for l1, l2 in safe_pairs:
            srdf += f'  <disable_collisions link1="{p}{l1}" link2="{p}{l2}" reason="Never"/>\n'
            
        # Arm 1 & 2 & 3 vs Main Table
        srdf += f'  <disable_collisions link1="{p}link0" link2="main_table_link" reason="Adjacent"/>\n'
        srdf += f'  <disable_collisions link1="{p}link1" link2="main_table_link" reason="Never"/>\n'
        srdf += f'  <disable_collisions link1="{p}link2" link2="main_table_link" reason="Never"/>\n'
        
        # Arm 1 & 2 & 3 vs Target Table
        # Only base links are inherently collision-free. Others should be checked!
        # Actually Target Table is far from link0, so we don't disable it (we want collision checking).

    # Also Main Table vs Target Table
    srdf += '  <disable_collisions link1="main_table_link" link2="target_table_link" reason="Adjacent"/>\n'

    srdf += '</robot>\n'
    return srdf

if __name__ == '__main__':
    out_dir = '/mnt/d/git/IsaacSim_Gemini/wsl_ws/src/multi_robot_moveit_config/config'
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'three_robot_scene.srdf'), 'w') as f:
        f.write(generate_srdf())
    print("SRDF generated successfully.")
