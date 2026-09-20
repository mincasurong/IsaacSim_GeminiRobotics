"""Reference oracles and mathematical ground-truth models for simulation, kinematics, and reasoning."""
import numpy as np


class SimOracleFrankaKinematics:
    """Standard DH parameters and kinematics reference oracle for Franka FR3."""
    
    # Standard Franka FR3 DH parameters: [theta_offset, d, a, alpha]
    DH_PARAMS = [
        [0.0, 0.333, 0.0, -np.pi/2],
        [0.0, 0.0, 0.0, np.pi/2],
        [0.0, 0.316, 0.0825, np.pi/2],
        [0.0, 0.0, -0.0825, -np.pi/2],
        [0.0, 0.384, 0.0, np.pi/2],
        [0.0, 0.0, 0.0, -np.pi/2],
        [0.0, 0.107, 0.0, 0.0]
    ]

    @classmethod
    def forward_kinematics(cls, q, base_pos=None):
        """Compute end-effector 4x4 transform from joint angles q."""
        T = np.eye(4)
        if base_pos is not None:
            T[:3, 3] = base_pos

        for i in range(min(7, len(q))):
            th = q[i] + cls.DH_PARAMS[i][0]
            d = cls.DH_PARAMS[i][1]
            a = cls.DH_PARAMS[i][2]
            alpha = cls.DH_PARAMS[i][3]

            ct, st = np.cos(th), np.sin(th)
            ca, sa = np.cos(alpha), np.sin(alpha)

            A_i = np.array([
                [ct, -st * ca,  st * sa, a * ct],
                [st,  ct * ca, -ct * sa, a * st],
                [0.0,      sa,       ca,      d],
                [0.0,     0.0,      0.0,    1.0]
            ])
            T = T @ A_i

        # Tool offset to flange/gripper center (approx 0.1034m along Z)
        T_tool = np.eye(4)
        T_tool[2, 3] = 0.1034
        return T @ T_tool


class SimOracleDualArmTrajectory:
    """Mathematical reference oracle for dual-arm coupled Cartesian transport."""

    @staticmethod
    def generate_coupled_waypoints(start_center, target_center, bar_length, num_steps=20):
        """Generate synchronized waypoints for Robot 1 and Robot 2 maintaining constant distance."""
        half_l = bar_length / 2.0
        t_vals = np.linspace(0.0, 1.0, num_steps)
        
        # Linear interpolation of center with smooth parabolic blend
        # s(t) = 3*t^2 - 2*t^3
        s = 3 * (t_vals ** 2) - 2 * (t_vals ** 3)
        
        start_center = np.array(start_center)
        target_center = np.array(target_center)
        
        robot1_waypoints = []
        robot2_waypoints = []
        
        for u in s:
            c = (1.0 - u) * start_center + u * target_center
            # Endpoints along X-axis offset by half_l
            p1 = np.array([c[0] - half_l, c[1], c[2]])
            p2 = np.array([c[0] + half_l, c[1], c[2]])
            robot1_waypoints.append(p1)
            robot2_waypoints.append(p2)
            
        return np.array(robot1_waypoints), np.array(robot2_waypoints)


class SimOracleAffordanceClassifier:
    """Cognitive classification oracle determining manipulation category from object geometry."""

    @staticmethod
    def classify(name, length=None, diameter=None, mass=None):
        name_lower = name.lower()
        if "bar" in name_lower or "tray" in name_lower or (length is not None and length >= 0.40):
            return "dual_arm"
        elif "dish" in name_lower or "plate" in name_lower:
            return "single_arm_dish"
        elif "cup" in name_lower or "mug" in name_lower:
            return "single_arm_cup"
        else:
            return "single_arm_generic"


class SimOracleRelativePlacement:
    """Reference placement coordinate calculator for relative arrangements."""

    @staticmethod
    def compute_target_xyz(anchor_xyz, relation, object_height=0.06, spacing=0.12):
        x, y, z = anchor_xyz
        if relation == "on_top_of":
            return [x, y, z + object_height]
        elif relation == "left_of":
            return [x - spacing, y, z]
        elif relation == "right_of":
            return [x + spacing, y, z]
        elif relation == "front_of":
            return [x, y - spacing, z]
        elif relation == "back_of":
            return [x, y + spacing, z]
        else:
            raise ValueError(f"Unknown relation: {relation}")
