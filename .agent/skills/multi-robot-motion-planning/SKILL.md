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
   For a $6$ cm block with standard Franka fingers ($0.04$ m max per finger):
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
- Block dimension: $H = 0.06$ m (cube or cylinder).
- Base block center: $Z_1 = 0.30 + H/2 = 0.330$ m.
- $N$-th block center: $Z_N = Z_{N-1} + H$.

### Anti-Bounce Zero-Drop Rule:
Do not drop blocks from an elevated offset (e.g. $+5$ mm clearance) when stacking rigid bodies in PhysX. High restitution or solver impulse causes top blocks to tilt and tumble. Always command the descent directly to the contact height ($Z_N$), hold position during `RELEASE`, and then vertically `RETRACT`.

---

## 4. DLS Inverse Kinematics & Null-Space Decoupling

### Problem: Azimuth Fighting & Elbow Drift
When an iterative Damped Least Squares (DLS) solver includes a null-space posture regularization term:
$$\Delta q = J^{\dagger} e + (I - J^{\dagger} J) k_{\text{null}} (q_{\text{home}} - q)$$
If $q_{\text{home}}[0] = 0.0$ while the robot is tasked to pick from a rear table ($J_1 \approx \pi$), the null-space projection exerts an internal torque pulling Joint 1 away from the azimuth goal. This causes solver stagnation and joint limit clipping.

### Fix: Decouple Joint 1 from Null-Space Bias
```python
grad_null = k_null * (FR3_HOME_CONFIG - q)
grad_null[0] = 0.0  # Allow Joint 1 azimuth to be driven purely by task-space tracking
null_space_term = (np.eye(7) - inv_J @ J) @ grad_null
```

---

## 5. Verification Checklist for Multi-Robot Controllers

Before running full multi-robot simulations, verify:
- [ ] `steps_per_phase` $\ge 30$ ($0.6$ s) for stable Cartesian descent.
- [ ] `dwell_steps` $\ge 15$ ($0.3$ s) for gripper touch and friction engagement.
- [ ] `CENTER_WORKSPACE_STATES` guard active on all center transitions.
- [ ] `verify_tower` service / topic is strictly read-only and never issues joint commands.
- [ ] Grasp verification verifies upper and lower finger gap bounds.
