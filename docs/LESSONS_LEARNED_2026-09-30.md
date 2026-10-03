# Lessons Learned — 2026-09-30

> **Session Summary**: A series of "upgrade" attempts to the multi-robot motion planner and multi-agent VLA system caused cascading regressions that broke pick-and-place. All algorithmic changes were rolled back to the stable baseline at commit `d914cdf6`. One critical bug (`verify_tower` opening grippers) was re-fixed on top of the rollback.

---

## 🔴 What Went Wrong

### 1. IK Solver Velocity Clipping Destroyed Trajectory Tracking

**Change attempted:** Added per-joint velocity limits (`np.clip`) inside the iterative DLS (Damped Least Squares) Inverse Kinematics solver loop in `kinematics.py`.

```python
# BAD: Component-wise clipping inside the IK gradient descent loop
_VEL_LIMITS = np.array([2.175, 2.175, 2.175, 2.175, 2.61, 2.61, 2.61])
dq = np.clip(dq, -_VEL_LIMITS * _DT, _VEL_LIMITS * _DT)
```

**Why it broke:** The DLS IK solver uses a Jacobian pseudo-inverse to compute a joint-space step `dq` that moves the end-effector toward the target. Clipping individual components of `dq` **destroys the gradient direction** — the solver can no longer converge to the correct Cartesian target. The robots veered off-course during `DESCEND_PICK`, missing blocks entirely and grasping empty air.

**Lesson:** Velocity limits belong in the **trajectory executor** (command publishing layer), NOT inside the numerical IK solver. The IK solver must be free to compute geometrically correct solutions; rate-limiting should happen afterward.

### 2. VIA_PICK / VIA_PLACE States Caused State Machine Deadlock

**Change attempted:** Added intermediate `VIA_PICK` and `VIA_PLACE` waypoints to create vertical "plunge" trajectories (preventing wide arcs that miss blocks).

**Why it broke:** The new states introduced logical holes in the finite state machine. When `get_block_local_pose()` returned `None` (TF frame not yet available), the state handler hit an early `return` that skipped the phase transition — freezing the robot indefinitely. The Gemini node timed out after 25 seconds with `Pick failed. Enclosing fresh workspace status.`

**Lesson:** Every state in the FSM must have a **timeout or fallback transition**. Never add a new state without also verifying its failure path. Add aggressive logging (`self.get_logger().info(f"State: {state} ...")`) inside new states during development.

### 3. Smoothstep Interpolation + 100Hz Loop Rate Change

**Change attempted:** Upgraded the control loop from 50Hz to 100Hz and replaced linear interpolation with cubic Hermite smoothstep.

**Why it broke (in combination):** Halving the timer period doubled the number of state machine ticks per trajectory segment. Combined with the smoothstep curve (which has zero velocity at endpoints), trajectories became extremely slow in practice — the robot appeared to "freeze" near waypoints. The `steps_per_phase` parameter wasn't adjusted to compensate.

**Lesson:** Control loop frequency and trajectory parameters are **tightly coupled**. Changing one without the other is a recipe for broken behavior. Always test parameter changes in isolation.

### 4. VERIFY_GRASP State Threshold Too Aggressive

**Change attempted:** Added a `VERIFY_GRASP` state that checks `current_gripper > 0.004` (4mm finger gap) before allowing lift.

**Why it broke:** The Isaac Sim gripper physics simulation doesn't settle in exactly 60ms (6 ticks × 10ms). The 4mm threshold was tuned for physical hardware — in simulation, the gripper reports sub-millimeter gaps even when successfully grasping, causing false "empty grasp" aborts.

**Lesson:** Sensor thresholds must be **tuned for the simulation environment**, not copied from hardware specs. Always validate thresholds empirically with `rostopic echo` before hardcoding.

---

## 🟡 Recurring Bug: `verify_tower` Opens All Grippers

### Root Cause

The `verify_tower` action handler in `multi_robot_controller.py` called `_send_home_cmd()` for all 3 robots:

```python
elif action == 'verify_tower':
    self.center_occupied_by = None
    for i in [1, 2, 3]:
        self._send_home_cmd(i)        # ← BUG: opens grippers!
        self._set_state(i, 'FINISHED')
```

The `_send_home_cmd()` method **hardcodes `self.gripper_open`**:

```python
cmd.position = self.q_home_fr3 + [self.gripper_open, self.gripper_open]
```

This means every `verify_tower` call forces ALL robots to open their grippers — dropping any blocks they're currently holding.

### Fix Applied

Changed `verify_tower` to a **purely read-only** operation that reports tower status without mutating any robot state:

```python
elif action == 'verify_tower':
    # READ-ONLY — never changes gripper or robot state
    result_data = {
        'success': True,
        'action': 'verify_tower',
        'tower_height': self.tower_height,
        'robot_states': { 'FR3_1': self.state1, ... },
        'message': f'Tower has {self.tower_height} blocks stacked.',
    }
    self.result_pub.publish(msg)
    return  # CRITICAL: early return — no state mutation
```

---

## 🟢 What We Rolled Back To

**Stable baseline:** Git commit `d914cdf6cc15f2624eef9bbed2c3fd7c5ef093eb`

The rollback restored the following files from that commit:
- `multi_robot_controller.py` — Original 50Hz state machine with linear interpolation
- `kinematics.py` — Original DLS IK without velocity clipping
- `gemini_robotics_node.py` — Original VLA orchestration node
- `gemini_prompts.py` — Original multi-agent prompt templates
- `gemini_tools.py` — Original function calling tool definitions
- `gemini_config.py`, `gemini_utils.py`, `workspace_state.py` — Supporting modules

**Kept intact (not rolled back):**
- `gemini_web_gui/` — Frontend React dashboard (new features preserved)
- `isaacsim_scripts/` — Isaac Sim scene scripts (new scenes preserved)
- `start_dashboard.bat` — Launch script
- MoveIt 2 integration files (new addition, not yet integrated into main pipeline)

---

## 📋 Build Environment Fixes

### WSL2 ROS 2 Build Errors

The full `colcon build` was failing on C++ hardware driver packages (`realtime_tools`, `franka_selfcollision`, `franka_gripper`). These packages require:
- `ros2_control_cmake` — Installed via `apt install ros-jazzy-ros2-control-cmake`
- `test_msgs` — Installed via `apt install ros-jazzy-test-msgs`
- `pinocchio` — Required by `franka_selfcollision` (not needed for simulation)

**Resolution:** Placed `COLCON_IGNORE` markers in `franka_ros2/` and `franka_description/` directories. These are physical hardware driver packages that are unnecessary when Isaac Sim acts as the digital twin.

```bash
touch /home/isaac/catkin_ws/src/franka_ros2/COLCON_IGNORE
touch /home/isaac/catkin_ws/src/franka_description/COLCON_IGNORE
```

---

## 📏 Rules for Future Controller Changes

1. **Never modify the IK solver and the state machine in the same commit.** Test each in isolation.
2. **Every new FSM state must have a timeout transition** — never rely on TF data being available.
3. **Velocity/acceleration limits go in the command publisher**, not the IK solver.
4. **Always validate gripper thresholds in simulation** before hardcoding — sim ≠ hardware.
5. **`verify_tower` must be read-only** — it must NEVER call `_send_home_cmd()` or modify robot state.
6. **After editing Python files on Windows, ALWAYS rebuild in WSL:**
   ```bash
   wsl -u isaac -- bash -c "cd /home/isaac/catkin_ws && colcon build --packages-select isaac_ros2_control"
   ```
7. **Keep `steps_per_phase` and control loop frequency coupled.** Document the relationship.
