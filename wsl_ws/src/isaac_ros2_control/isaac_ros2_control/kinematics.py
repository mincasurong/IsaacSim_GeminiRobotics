"""Kinematics module for Franka FR3 (7-DOF) and UR5e (6-DOF) manipulators.

Features:
- Franka FR3: Forward Kinematics, Geometric Jacobian, Null-space regularized DLS IK
- UR5e: Analytical Closed-Form 8-Solution IK (Instantaneous, 100% exact, no local minima)
        with fallback to DLS numerical IK.
- Quaternion conversions, SLERP interpolation, and 4-fold symmetric grasp helpers.
"""

import numpy as np


# 1. Coordinate Transform & Geometry Utilities

def tf_matrix(xyz, rpy):
    """Create a 4x4 homogeneous transformation matrix from translation and RPY."""
    r, p, y = rpy
    cr, cp, cy = np.cos(r), np.cos(p), np.cos(y)
    sr, sp, sy = np.sin(r), np.sin(p), np.sin(y)
    
    # Rz(y) * Ry(p) * Rx(r)
    R = np.array([
        [cy*cp, cy*sp*sr - sy*cr, cy*sp*cr + sy*sr],
        [sy*cp, sy*sp*sr + cy*cr, sy*sp*cr - cy*sr],
        [-sp,   cp*sr,            cp*cr]
    ])
    
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = xyz
    return T


def rot_z(q):
    """Create a 4x4 Z-axis rotation matrix for joint angle q."""
    cq, sq = np.cos(q), np.sin(q)
    return np.array([
        [cq, -sq, 0.0, 0.0],
        [sq, cq, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0]
    ])


def rot_x(alpha):
    """Create a 4x4 X-axis rotation matrix for angle alpha."""
    ca, sa = np.cos(alpha), np.sin(alpha)
    return np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, ca, -sa, 0.0],
        [0.0, sa, ca, 0.0],
        [0.0, 0.0, 0.0, 1.0]
    ])


def trans_z(d):
    """Create a 4x4 Z-axis translation matrix."""
    T = np.eye(4)
    T[2, 3] = d
    return T


def trans_x(a):
    """Create a 4x4 X-axis translation matrix."""
    T = np.eye(4)
    T[0, 3] = a
    return T


def dh_matrix(th, d, a, alpha):
    """Standard Denavit-Hartenberg transformation matrix."""
    return rot_z(th) @ trans_z(d) @ trans_x(a) @ rot_x(alpha)


def quat_to_rot_matrix(quat):
    """Convert [w, x, y, z] quaternion to a 3x3 rotation matrix."""
    qw, qx, qy, qz = quat
    norm = np.sqrt(qw*qw + qx*qx + qy*qy + qz*qz)
    if norm > 1e-9:
        qw, qx, qy, qz = qw/norm, qx/norm, qy/norm, qz/norm
    return np.array([
        [1 - 2*qy**2 - 2*qz**2, 2*qx*qy - 2*qz*qw, 2*qx*qz + 2*qy*qw],
        [2*qx*qy + 2*qz*qw, 1 - 2*qx**2 - 2*qz**2, 2*qy*qz - 2*qx*qw],
        [2*qx*qz - 2*qy*qw, 2*qy*qz + 2*qx*qw, 1 - 2*qx**2 - 2*qy**2]
    ])


def rot_matrix_to_quat(R):
    """Convert a 3x3 rotation matrix to [w, x, y, z] quaternion."""
    tr = np.trace(R)
    if tr > 0:
        S = np.sqrt(tr + 1.0) * 2.0
        qw = 0.25 * S
        qx = (R[2, 1] - R[1, 2]) / S
        qy = (R[0, 2] - R[2, 0]) / S
        qz = (R[1, 0] - R[0, 1]) / S
    elif (R[0, 0] > R[1, 1]) and (R[0, 0] > R[2, 2]):
        S = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2.0
        qw = (R[2, 1] - R[1, 2]) / S
        qx = 0.25 * S
        qy = (R[0, 1] + R[1, 0]) / S
        qz = (R[0, 2] + R[2, 0]) / S
    elif R[1, 1] > R[2, 2]:
        S = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2.0
        qw = (R[0, 2] - R[2, 0]) / S
        qx = (R[0, 1] + R[1, 0]) / S
        qy = 0.25 * S
        qz = (R[1, 2] + R[2, 1]) / S
    else:
        S = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2.0
        qw = (R[1, 0] - R[0, 1]) / S
        qx = (R[0, 2] + R[2, 0]) / S
        qy = (R[1, 2] + R[2, 1]) / S
        qz = 0.25 * S
    q = np.array([qw, qx, qy, qz])
    return q / np.linalg.norm(q)


def interpolate_quat(q1, q2, t):
    """Spherical linear interpolation (SLERP) between two [w, x, y, z] quaternions."""
    q1 = np.array(q1, dtype=float)
    q2 = np.array(q2, dtype=float)
    dot = np.dot(q1, q2)
    if dot < 0.0:
        q2 = -q2
        dot = -dot
    if dot > 0.9995:
        q = (1.0 - t) * q1 + t * q2
        norm = np.linalg.norm(q)
        return (q / norm).tolist() if norm > 1e-9 else q1.tolist()
    
    dot = np.clip(dot, -1.0, 1.0)
    theta_0 = np.arccos(dot)
    sin_theta_0 = np.sin(theta_0)
    
    if sin_theta_0 < 1e-6:
        return q1.tolist()
    
    theta_t = theta_0 * t
    s1 = np.cos(theta_t) - dot * np.sin(theta_t) / sin_theta_0
    s2 = np.sin(theta_t) / sin_theta_0
    q = s1 * q1 + s2 * q2
    return (q / np.linalg.norm(q)).tolist()


def compute_symmetric_grasp_quat(target_yaw, arm_yaw):
    """Compute optimal downward grasp quaternion [w, x, y, z] for a square object.
    
    Snaps to the closest 90-degree (pi/2) symmetric orientation relative to
    the arm approach angle (arm_yaw) to minimize wrist twist.
    """
    yaw_diff = target_yaw - arm_yaw
    # Wrap to [-pi/4, pi/4] due to 4-fold 90-degree symmetry
    yaw_diff_sym = (yaw_diff + np.pi / 4.0) % (np.pi / 2.0) - np.pi / 4.0
    best_yaw = arm_yaw + yaw_diff_sym
    
    # Downward grasping quaternion: 180-deg flip around axis [cos(yaw/2), sin(yaw/2), 0]
    qw = 0.0
    qx = np.cos(best_yaw / 2.0)
    qy = np.sin(best_yaw / 2.0)
    qz = 0.0
    return [qw, qx, qy, qz]


# 2. Franka FR3 Kinematics (7-DOF Arm + Parallel Gripper)

JOINT_ORIGINS_FR3 = [
    ([0.0, 0.0, 0.333], [0.0, 0.0, 0.0]),
    ([0.0, 0.0, 0.0], [-1.570796326794897, 0.0, 0.0]),
    ([0.0, -0.316, 0.0], [1.570796326794897, 0.0, 0.0]),
    ([0.0825, 0.0, 0.0], [1.570796326794897, 0.0, 0.0]),
    ([-0.0825, 0.384, 0.0], [-1.570796326794897, 0.0, 0.0]),
    ([0.0, 0.0, 0.0], [1.570796326794897, 0.0, 0.0]),
    ([0.088, 0.0, 0.0], [1.570796326794897, 0.0, 0.0]),
]

T_LINK7_TO_LINK8 = tf_matrix([0.0, 0.0, 0.107], [0.0, 0.0, 0.0])
T_LINK8_TO_HAND = tf_matrix([0.0, 0.0, 0.0], [0.0, 0.0, -0.7853981633974483])
T_HAND_TO_TCP = tf_matrix([0.0, 0.0, 0.1034], [0.0, 0.0, 0.0])
T_EE_FIXED_FR3 = T_LINK7_TO_LINK8 @ T_LINK8_TO_HAND @ T_HAND_TO_TCP

FR3_JOINT_LIMITS = [
    (-2.8973, 2.8973),   # Joint 1
    (-1.7628, 1.7628),   # Joint 2
    (-2.8973, 2.8973),   # Joint 3
    (-3.0718, -0.0698),  # Joint 4 (Elbow)
    (-2.8973, 2.8973),   # Joint 5
    (-0.0175, 3.7525),   # Joint 6
    (-2.8973, 2.8973)    # Joint 7
]

FR3_HOME_CONFIG = np.array([0.0, 0.0, 0.0, -1.5708, 0.0, 1.5708, 0.7854])


def forward_kinematics(q):
    """Compute 4x4 end-effector pose matrix from 7 joint angles for Franka FR3."""
    T = np.eye(4)
    for i in range(7):
        xyz, rpy = JOINT_ORIGINS_FR3[i]
        T_joint = tf_matrix(xyz, rpy)
        T = T @ T_joint @ rot_z(q[i])
    return T @ T_EE_FIXED_FR3


def get_jacobian(q):
    """Compute 6x7 geometric Jacobian matrix for the Franka FR3 TCP."""
    T = np.eye(4)
    transforms = []
    for i in range(7):
        xyz, rpy = JOINT_ORIGINS_FR3[i]
        T_joint = tf_matrix(xyz, rpy)
        T = T @ T_joint @ rot_z(q[i])
        transforms.append(T.copy())
    
    T_ee = T @ T_EE_FIXED_FR3
    p_ee = T_ee[:3, 3]
    
    J = np.zeros((6, 7))
    for i in range(7):
        T_i = transforms[i]
        z_i = T_i[:3, 2]
        p_i = T_i[:3, 3]
        J[:3, i] = np.cross(z_i, p_ee - p_i)
        J[3:, i] = z_i
    return J


def inverse_kinematics(target_pos, target_quat, q_init, max_iter=60, tol=1e-4):
    """Solve Franka FR3 inverse kinematics using Damped Least Squares (DLS)."""
    q = np.array(q_init, dtype=float)
    if np.any(np.isnan(target_pos)):
        return q, False
        
    R_target = quat_to_rot_matrix(target_quat)
    
    for _ in range(max_iter):
        T_ee = forward_kinematics(q)
        p_ee = T_ee[:3, 3]
        R_ee = T_ee[:3, :3]
        
        err_pos = target_pos - p_ee
        
        R_err = R_target @ R_ee.T
        tr = np.trace(R_err)
        theta_err = np.arccos(np.clip((tr - 1.0) / 2.0, -1.0, 1.0))
        
        if np.abs(theta_err) < 1e-6:
            err_rot = np.zeros(3)
        else:
            axis = np.array([
                R_err[2, 1] - R_err[1, 2],
                R_err[0, 2] - R_err[2, 0],
                R_err[1, 0] - R_err[0, 1]
            ]) / (2.0 * np.sin(theta_err))
            err_rot = axis * theta_err
            
        error = np.hstack((err_pos, err_rot))
        if np.linalg.norm(error) < tol:
            return q, True
            
        J = get_jacobian(q)
        
        # Damped Least Squares
        damping = 0.02
        inv_J = J.T @ np.linalg.inv(J @ J.T + damping**2 * np.eye(6))
        
        # Null-space posture regularization towards home config
        k_null = 0.05
        grad_null = k_null * (FR3_HOME_CONFIG - q)
        null_space_term = (np.eye(7) - inv_J @ J) @ grad_null
        
        dq = inv_J @ error + null_space_term
        
        # Step limiter
        step_limit = 0.15
        dq_norm = np.linalg.norm(dq)
        if dq_norm > step_limit:
            dq = dq * (step_limit / dq_norm)
            
        q += dq
        
        for i in range(7):
            q[i] = np.clip(q[i], FR3_JOINT_LIMITS[i][0], FR3_JOINT_LIMITS[i][1])
            
    return q, False


# 3. Universal Robots UR5e Kinematics (Analytical Closed-Form IK)

# UR5e DH parameters
UR5E_D1 = 0.1625
UR5E_A2 = -0.425
UR5E_A3 = -0.3922
UR5E_D4 = 0.1333
UR5E_D5 = 0.0997
# Flange to Robotiq TCP is 0.1128m along Z
UR5E_D6 = 0.0996 + 0.1128

UR5E_JOINT_LIMITS = [
    (-2*np.pi, 2*np.pi), # Joint 1 (shoulder_pan)
    (-2*np.pi, 2*np.pi), # Joint 2 (shoulder_lift)
    (-np.pi, np.pi),     # Joint 3 (elbow)
    (-2*np.pi, 2*np.pi), # Joint 4 (wrist_1)
    (-2*np.pi, 2*np.pi), # Joint 5 (wrist_2)
    (-2*np.pi, 2*np.pi)  # Joint 6 (wrist_3)
]

UR5E_HOME_CONFIG = np.array([0.0, -1.5708, 1.5708, -1.5708, -1.5708, 0.0])


def forward_kinematics_ur5e(q):
    """Compute 4x4 TCP pose matrix using exact DH parameters for UR5e."""
    T1 = dh_matrix(q[0], UR5E_D1, 0.0, np.pi/2)
    T2 = dh_matrix(q[1], 0.0, UR5E_A2, 0.0)
    T3 = dh_matrix(q[2], 0.0, UR5E_A3, 0.0)
    T4 = dh_matrix(q[3], UR5E_D4, 0.0, np.pi/2)
    T5 = dh_matrix(q[4], UR5E_D5, 0.0, -np.pi/2)
    T6 = dh_matrix(q[5], UR5E_D6, 0.0, 0.0)
    return T1 @ T2 @ T3 @ T4 @ T5 @ T6


def solve_all_ik_ur5e(T_target):
    """Compute all 8 analytical closed-form IK solutions for UR5e.
    
    Returns list of valid 6-element joint angle arrays.
    """
    sols = []
    
    R06 = T_target[:3, :3]
    P06 = T_target[:3, 3]
    
    # 1. Shoulder Pan (theta1) - 2 solutions
    P05 = P06 - UR5E_D6 * R06[:, 2]
    p5x, p5y = P05[0], P05[1]
    r_xy = np.sqrt(p5x**2 + p5y**2)
    if r_xy < UR5E_D4:
        return sols
        
    psi = np.arctan2(p5y, p5x)
    phi1 = np.arccos(np.clip(UR5E_D4 / r_xy, -1.0, 1.0))
    
    th1_candidates = [
        psi + phi1 + np.pi/2.0,
        psi - phi1 + np.pi/2.0
    ]
    
    for th1 in th1_candidates:
        # 2. Wrist 2 (theta5) - 2 solutions per th1
        val = (P06[0] * np.sin(th1) - P06[1] * np.cos(th1) - UR5E_D4) / UR5E_D6
        if np.abs(val) > 1.0:
            continue
        acos_val = np.arccos(np.clip(val, -1.0, 1.0))
        th5_candidates = [acos_val, -acos_val]
        
        for th5 in th5_candidates:
            if np.abs(np.sin(th5)) < 1e-5:
                # Wrist singularity
                continue
                
            # 3. Wrist 3 (theta6)
            T01 = dh_matrix(th1, UR5E_D1, 0.0, np.pi/2.0)
            T16 = np.linalg.inv(T01) @ T_target
            
            th6 = np.arctan2(-T16[1, 1] / np.sin(th5), T16[1, 0] / np.sin(th5))
            
            # 4. Theta2, Theta3, Theta4 (Planar 3R)
            T45 = dh_matrix(th5, UR5E_D5, 0.0, -np.pi/2.0)
            T56 = dh_matrix(th6, UR5E_D6, 0.0, 0.0)
            T14 = T16 @ np.linalg.inv(T45 @ T56)
            
            P14 = T14[:3, 3]
            p14x, p14z = P14[0], P14[2]
            
            D_sq = p14x**2 + p14z**2
            cos_th3 = (D_sq - UR5E_A2**2 - UR5E_A3**2) / (2.0 * UR5E_A2 * UR5E_A3)
            if np.abs(cos_th3) > 1.0:
                continue
                
            th3_candidates = [
                np.arccos(np.clip(cos_th3, -1.0, 1.0)),
                -np.arccos(np.clip(cos_th3, -1.0, 1.0))
            ]
            
            for th3 in th3_candidates:
                gamma = np.arctan2(p14z, p14x)
                beta = np.arctan2(UR5E_A3 * np.sin(th3), UR5E_A2 + UR5E_A3 * np.cos(th3))
                th2 = gamma - beta
                
                # Theta4 from planar link orientation
                R14 = T14[:3, :3]
                th234 = np.arctan2(R14[2, 0], R14[0, 0])
                th4 = th234 - th2 - th3
                
                sol = np.array([th1, th2, th3, th4, th5, th6])
                sols.append(sol)
                
    return sols


def inverse_kinematics_ur5e(target_pos, target_quat, q_init):
    """Solve UR5e inverse kinematics using closed-form analytical equations.
    
    Selects the optimal branch closest to q_init with elbow-up human-like posture.
    """
    q_init_arr = np.array(q_init, dtype=float)
    if np.any(np.isnan(target_pos)):
        return q_init_arr, False
        
    T_target = np.eye(4)
    T_target[:3, :3] = quat_to_rot_matrix(target_quat)
    T_target[:3, 3] = target_pos
    
    all_sols = solve_all_ik_ur5e(T_target)
    
    if len(all_sols) == 0:
        # Fallback to DLS if target is on exact mathematical singularity
        return _inverse_kinematics_ur5e_dls(target_pos, target_quat, q_init)
        
    valid_candidates = []
    
    for raw_sol in all_sols:
        # Continuous joint angle unwrapping closest to q_init
        unwrapped = np.zeros(6)
        for i in range(6):
            diff = (raw_sol[i] - q_init_arr[i] + np.pi) % (2.0 * np.pi) - np.pi
            unwrapped[i] = q_init_arr[i] + diff
            
        # Check joint limits
        within_limits = True
        for i in range(6):
            if unwrapped[i] < UR5E_JOINT_LIMITS[i][0] or unwrapped[i] > UR5E_JOINT_LIMITS[i][1]:
                within_limits = False
                break
                
        if within_limits:
            # Score candidate: prefer elbow up (th3 > 0), smooth distance to q_init
            dist = np.linalg.norm(unwrapped - q_init_arr)
            # Penalty for inverted elbow (th3 < 0)
            elbow_penalty = 10.0 if unwrapped[2] < 0 else 0.0
            score = dist + elbow_penalty
            valid_candidates.append((score, unwrapped))
            
    if len(valid_candidates) > 0:
        valid_candidates.sort(key=lambda x: x[0])
        best_sol = valid_candidates[0][1]
        return best_sol, True
        
    return q_init_arr, False


def get_jacobian_ur5e(q):
    """Compute 6x6 geometric Jacobian matrix for the UR5e TCP."""
    T = np.eye(4)
    transforms = []
    
    # Forward pass through DH frames
    dh_params = [
        (q[0], UR5E_D1, 0.0, np.pi/2),
        (q[1], 0.0, UR5E_A2, 0.0),
        (q[2], 0.0, UR5E_A3, 0.0),
        (q[3], UR5E_D4, 0.0, np.pi/2),
        (q[4], UR5E_D5, 0.0, -np.pi/2),
        (q[5], UR5E_D6, 0.0, 0.0),
    ]
    
    for th, d, a, alpha in dh_params:
        T = T @ dh_matrix(th, d, a, alpha)
        transforms.append(T.copy())
        
    p_ee = T[:3, 3]
    J = np.zeros((6, 6))
    
    T_prev = np.eye(4)
    for i in range(6):
        z_i = T_prev[:3, 2]
        p_i = T_prev[:3, 3]
        J[:3, i] = np.cross(z_i, p_ee - p_i)
        J[3:, i] = z_i
        T_prev = transforms[i]
        
    return J


def _inverse_kinematics_ur5e_dls(target_pos, target_quat, q_init, max_iter=40, tol=1e-3):
    """Numerical DLS fallback for UR5e near singularities."""
    q = np.array(q_init, dtype=float)
    R_target = quat_to_rot_matrix(target_quat)
    
    for _ in range(max_iter):
        T_ee = forward_kinematics_ur5e(q)
        err_pos = target_pos - T_ee[:3, 3]
        
        R_err = R_target @ T_ee[:3, :3].T
        tr = np.trace(R_err)
        theta_err = np.arccos(np.clip((tr - 1.0) / 2.0, -1.0, 1.0))
        
        if np.abs(theta_err) < 1e-6:
            err_rot = np.zeros(3)
        else:
            axis = np.array([
                R_err[2, 1] - R_err[1, 2],
                R_err[0, 2] - R_err[2, 0],
                R_err[1, 0] - R_err[0, 1]
            ]) / (2.0 * np.sin(theta_err))
            err_rot = axis * theta_err
            
        error = np.hstack((err_pos, err_rot))
        if np.linalg.norm(error) < tol:
            return q, True
            
        J = get_jacobian_ur5e(q)
        damping = 0.02
        inv_J = J.T @ np.linalg.inv(J @ J.T + damping**2 * np.eye(6))
        dq = inv_J @ error
        
        step_limit = 0.1
        dq_norm = np.linalg.norm(dq)
        if dq_norm > step_limit:
            dq = dq * (step_limit / dq_norm)
            
        q += dq
        for i in range(6):
            q[i] = np.clip(q[i], UR5E_JOINT_LIMITS[i][0], UR5E_JOINT_LIMITS[i][1])
            
    return q, False
