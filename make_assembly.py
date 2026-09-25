import re
import os

filepath = r'd:\git\IsaacSim_Gemini\isaacsim_scripts\assembly_dual_robot.py'
os.system(r'copy /y d:\git\IsaacSim_Gemini\isaacsim_scripts\conveyor_dual_robot.py ' + filepath)

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Let's replace the block/bar spawning with the long-horizon components
new_spawn = """
    # ------------------------------------------------------------------------------------
    # LONG-HORIZON ASSEMBLY COMPONENTS (Skill-based ATAMP)
    # ------------------------------------------------------------------------------------

    def add_chassis(prim_path, position, name):
        # Heavy Chassis (Requires Dual-Arm Transport)
        from omni.isaac.core.objects import DynamicCuboid
        obj = DynamicCuboid(
            prim_path=prim_path,
            name=name,
            position=position,
            scale=np.array([0.6, 0.4, 0.1]),
            color=np.array([0.2, 0.2, 0.2]), # Dark Grey
            mass=3.0
        )
        return obj

    def add_gear(prim_path, position, color, name):
        # Small Gear (Requires Precision Insert)
        from omni.isaac.core.objects import DynamicCylinder
        obj = DynamicCylinder(
            prim_path=prim_path,
            name=name,
            position=position,
            radius=0.08,
            height=0.04,
            color=color,
            mass=0.5
        )
        return obj

    def add_debris(prim_path, position, name):
        # Obstacle (Requires Compliant Push)
        from omni.isaac.core.objects import DynamicCuboid
        obj = DynamicCuboid(
            prim_path=prim_path,
            name=name,
            position=position,
            scale=np.array([0.2, 0.8, 0.2]),
            color=np.array([0.8, 0.1, 0.1]), # Red Obstacle
            mass=1.5
        )
        return obj

    # Spawn Components
    add_chassis("/World/HeavyChassis", np.array([0.0, 0.8, 0.28]), "HeavyChassis")
    add_gear("/World/Gear1", np.array([-0.3, 0.4, 0.3]), np.array([0.8, 0.8, 0.2]), "Gear1")
    add_gear("/World/Gear2", np.array([0.3, 0.4, 0.3]), np.array([0.2, 0.8, 0.8]), "Gear2")
    add_debris("/World/DebrisObstacle", np.array([0.0, 0.5, 0.28]), "DebrisObstacle")
"""

content = re.sub(r'    # ------------------------------------------------------------------------------------\n    # BLOCK SPAWN PROCEDURES.*?    # CREATE ROS 2 ACTION GRAPH FOR CLOCK & TF', new_spawn + '\n    # CREATE ROS 2 ACTION GRAPH FOR CLOCK & TF', content, flags=re.DOTALL)

# Also update the Action Graph targets
content = content.replace(
    'usdrt.Sdf.Path("/Block1"), usdrt.Sdf.Path("/Block2"),\n                    usdrt.Sdf.Path("/LongBar"), usdrt.Sdf.Path("/HeavyEnginePart"),', 
    'usdrt.Sdf.Path("/HeavyChassis"), usdrt.Sdf.Path("/Gear1"), usdrt.Sdf.Path("/Gear2"), usdrt.Sdf.Path("/DebrisObstacle"),'
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
