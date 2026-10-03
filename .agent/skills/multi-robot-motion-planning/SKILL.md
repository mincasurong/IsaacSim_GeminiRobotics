---
name: multi-robot-motion-planning
description: >-
  Advanced multi-robot manipulation, collision-free workspace coordination, and high-reliability
  pick-and-place execution for multi-arm Franka FR3 stations in NVIDIA Isaac Sim and ROS 2 Jazzy.
  Covers kinematic solvers, null-space decoupling, mutual-exclusion spatial zones, gripper dwell dynamics,
  and contact-safe tower stacking.
---

# Multi-Robot Motion Planning & Coordination Skill

This skill distills the engineering practices, mathematical formulations, and operational rules for reliable multi-robot manipulation within NVIDIA Isaac Sim and ROS 2.

## 1. Multi-Robot Spatial Deconfliction & Mutual Exclusion

### Problem: Mid-Air Arm Collisions
In multi-arm circular workstations (e.g., 3x Franka FR3 around a central staging table), collisions occur when:
1. Two robots enter the center workspace simultaneously.
2. A robot releases the mutual-exclusion lock while its arm is still physically sweeping through the center zone during retraction or homing.
3. Pure joint-space interpolation sweeps elbows through unmodeled intermediate volumes.

### Solution: State-Gated Spatial Mutual Exclusion
A simple binary lock (`center_occupied_by`) is necessary but not sufficient. It must be paired with an invariant state gate:

```python
CENTER_WORKSPACE_STATES = {
    'TUCK_AFTER_PICK', 'ROTATE_TO_PLACE', 'HOVER_PLACE', 
    'DESCEND_PLACE', 'RELEASE', 'RETRACT', 'TUCK_AFTER_PLACE', 'RETURN_HOME'
}
```

**Invariant Rule**: A robot entering `WAIT_FOR_CENTER` may only claim the center if:
```python
is_free = (self.center_occupied_by is None or self.center_occupied_by == robot_id) and \
          not any(getattr(self, f'state{o}') in CENTER_WORKSPACE_STATES for o in [1, 2, 3] if o != robot_id)
```

**Lock Release Boundary**: The center mutex MUST NOT be released at the beginning of `RETURN_HOME`. It must only be released when `step_counter >= total_steps` of `RETURN_HOME`, when the physical manipulator has cleared the boundary of the central staging table.

---

## 2. High-Reliability Grasping & Finger Dynamics in Isaac Sim

### Problem: Robots Lifting on Empty Air
1. **Dwell Time Undershoot**: PhysX joint drives on Franka parallel fingers require 250–350 ms under dynamic solver iterations to close on an object and develop normal force. Setting `dwell_steps < 15` (at 50 Hz, < 300 ms) causes the arm to lift while fingers are still traveling.
2. **False-Positive Grasp Detection**: Testing `gripper_pos > 0.01` treats a wide-open gripper ($0.04$ m) as a successful grasp if the close command lagged or timed out.
3. **Arm Drift During Grasping**: Using measured joint state during the dwell phase allows contact reaction forces to backdrive the arm.

### Rules for Reliable Grasping:
1. **Dwell Duration**: Always allow at least $0.30$ s ($\ge 15$ steps at 50 Hz) for finger closure before initiating `LIFT`.
2. **Rigid Target Holding**: In `GRASP` and `RELEASE`, hold the nominal waypoint `end_q` rather than the measured `q_current`:
   ```python
   q_sol = np.array(end_q)
   ```
3. **Windowed Grasp Verification**:
   For a $4.5$ cm block with standard Franka fingers ($0.04$ m max stroke per finger):
   - Fully closed on empty space: $\le 0.005$ m.
   - Fully open (missed close command): $\ge 0.038$ m.
   - Successful physical grasp:
   ```python
   pick_success = 0.005 < current_gripper < 0.038
   ```

---

## 3. Precision Tower Stacking & Contact Surface Alignment

### Stacking Height Invariant:
- Stacking surface of target table: $Z_{\text{table}} = 0.30$ m.
- Block dimension: $H = 0.06$ m (nominal height).
- Base block center: $Z_1 = 0.30 + H/2 = 0.330$ m.
- $N$-th block center: $Z_N = Z_1 + (N - 1) \cdot H$.

### Anti-Bounce Zero-Drop Rule:
Do not drop blocks from an elevated offset (e.g. $+5$ mm clearance) when stacking rigid bodies in PhysX. High restitution or solver impulse causes top blocks to tilt and tumble. Always command the descent directly to the contact height ($Z_N$), hold position during `RELEASE`, and then vertically `RETRACT`.

---

## 4. DLS Inverse Kinematics & Null-Space Decoupling

### Problem: Azimuth Fighting & Elbow Drift
When an iterative Damped Least Squares (DLS) solver includes a null-space posture regularization term:
$$\Delta \mathbf{q} = J^{\dagger} \mathbf{e} + (I - J^{\dagger} J) \mathbf{k}_{\text{null}} (\mathbf{q}_{\text{home}} - \mathbf{q})$$
If $q_{\text{home}}[0] = \pi/2$ while the robot is tasked to pick from a rear table ($q_1 \approx -\pi/2$), the null-space projection exerts an internal torque pulling Joint 1 away from the azimuth goal. This causes solver stagnation and joint limit clipping.

### Fix: Decouple Joint 1 from Null-Space Bias
```python
grad_null = k_null * (FR3_HOME_CONFIG - q)
grad_null[0] = 0.0  # Allow Joint 1 azimuth to be driven purely by task-space tracking
null_space_term = (np.eye(7) - inv_J @ J) @ grad_null
```

---

## 5. Manipulator Kinematic Azimuth Reachability & Joint 1 Blind Spot

### Physical Root Cause of Pick Failures:
1. **Franka FR3 Joint 1 Hardstop**: The mechanical limit of Joint 1 on the Franka FR3 is $[-2.8973, +2.8973]\,\text{rad}$ ($\pm 166.004^\circ$). It has a physical **$28^\circ$ blind zone** directly behind its base ($|\theta| > 166^\circ$).
2. **The Collinear Workstation Anti-Pattern**: Mounting robot bases facing radially inward (FR3_1 at $90^\circ$, FR3_2 at $210^\circ$, FR3_3 at $330^\circ$) while placing source tables directly behind them forces the robot to reach directly into its mechanical blind spot. Any spawn noise ($\pm 3\,\text{cm}$) clips Joint 1 at $166^\circ$, resulting in a $14^\circ$ azimuth offset ($15\,\text{cm}$ Cartesian error at the table).
3. **The Tangential Mounting Solution**:
   Orienting robot bases tangentially:
   - **FR3_1**: base yaw = $0^\circ$, position $[0.0, -0.45, 0.20]\,\text{m}$
   - **FR3_2**: base yaw = $120^\circ$, position $[0.3897, 0.225, 0.20]\,\text{m}$
   - **FR3_3**: base yaw = $240^\circ$, position $[-0.3897, 0.225, 0.20]\,\text{m}$
   Transforms the operational workspace:
   - Central placement target: local $+90^\circ$ ($+1.5708\,\text{rad}$) $\to$ $76^\circ$ margin to joint limit.
   - Source pick tables & blocks: local $-78^\circ$ to $-101^\circ$ ($-1.37$ to $-1.77\,\text{rad}$) $\to$ $65^\circ+$ margin to joint limit.
   - Both pick and place targets reside comfortably in the high-manipulability region of the arm.

### Joint Velocity Limit & Trajectory Scaling:
- FR3 Joint 1 max velocity: $\dot{q}_{1,\text{max}} = 2.175\,\text{rad/s}$.
- A $180^\circ$ swing ($\pi = 3.14\,\text{rad}$) between source and center tables requires:
  $$t_{\text{min}} \ge \frac{1.875 \cdot \pi}{2.175} \approx 2.7\,\text{s (quintic peak)}$$
- Allocating fewer than 50 steps at 50 Hz ($< 1.0\,\text{s}$) causes severe joint lag in simulation, causing the arm to arrive late and descend during residual rotational momentum.
- **Rule**: Always allocate `total_steps = max(steps_per_phase, 50)` for large rotational phases (`ROTATE_TO_PICK`, `ROTATE_TO_PLACE`, `RETURN_HOME`).

---

## 6. Shared Controller Architecture & Anti-Divergence Rule

### Unified Inheritance Invariant:
All specialized multi-robot controllers must inherit directly from the canonical `MultiRobotController`:
- **Base Class (`MultiRobotController`)**: Provides DLS IK, SVD pseudoinverse, null-space decoupling, quintic polynomial minimum-jerk trajectory generation, `CENTER_WORKSPACE_STATES` mutual exclusion, read-only `verify_tower`, 300 ms dwell, and windowed physical grasp verification (`0.005 < current_gripper < 0.038`).
- **Derived Class (`ConveyorDualController`)**: Overrides only domain-specific behaviors (e.g., `active_robot_ids = [1, 2]`, dual-arm offset calculation for long bars, dynamic conveyor velocity forward prediction).

---

## 7. Motion Planning Roadmap: MoveIt 2 vs. DLS Kinematics

### Comparative Evaluation:
| Aspect | Numerical DLS + FSM | MoveIt 2 (OMPL / Pilz) |
|---|---|---|
| **Determinism** | 100% predictable cycle times (20ms) | Variable search latency (50ms–500ms) |
| **Compute Overhead** | Negligible CPU (< 5% per core) | Higher memory/CPU footprint |
| **Workspace Contention** | Fast state-gated mutual exclusion | Requires continuous Scene planning updates |
| **High-Obstacle Scenes** | Limited to geometric waypoints | Dynamic obstacle avoidance with meshes |

**Architecture Decision**:
- Use **DLS Kinematics with FSM Mutual Exclusion** as the real-time core for vertical tower stacking and fast cyclical sorting (zero latency, zero planning failures).
- Use **MoveIt 2** (`multi_robot_moveit_controller.py`) for arbitrary obstacle-rich environments and irregular Cartesian obstacle avoidance.
- Forward GPU acceleration via `isaac_ros_cumotion` directly mounts as a MoveIt 2 planning plugin.

---

## 8. Verification Checklist for Multi-Robot Controllers

Before running full multi-robot simulations, verify:
- [ ] `steps_per_phase` $\ge 30$ ($0.6$ s) for stable Cartesian descent.
- [ ] `dwell_steps` $\ge 15$ ($0.3$ s) for gripper touch and friction engagement.
- [ ] `CENTER_WORKSPACE_STATES` guard active on all center transitions.
- [ ] `verify_tower` service / topic is strictly read-only and never issues joint commands.
- [ ] Grasp verification verifies upper and lower finger gap bounds (`0.005 < gap < 0.038`).
- [ ] Zero-drop contact height used for all stacking layers (no artificial bounce gaps).
- [ ] FastDDS Unicast profile verified with matching Windows/WSL2 IPs.
