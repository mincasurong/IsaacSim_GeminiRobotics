---
name: isaacsim-troubleshooting
description: >-
  Comprehensive troubleshooting guide and lessons learned for NVIDIA Isaac Sim, ROS 2 Jazzy,
  FastDDS cross-platform networking, React Flow digital twins, and multi-robot kinematics.
---

# Isaac Sim & Gemini Workspace Troubleshooting Guide

This guide compiles field-tested troubleshooting patterns, failure mode diagnoses, and architectural invariants across the Isaac Sim + ROS 2 + VLA ecosystem.

---

## 1. ROS 2 Execution & TF Timeouts in Control Loops
- **Anti-Pattern**: Using `timeout=Duration(...)` inside `tf_buffer.lookup_transform()` within high-frequency (50 Hz+) single-threaded timer callbacks.
- **Failure Mode**: When TF publishing experiences jitter or frames are temporarily unavailable, blocking calls starve incoming `/joint_states` topic subscriptions, causing cascade controller timeouts.
- **Fix**: Always perform non-blocking instantaneous lookups:
  ```python
  trans = self.tf_buffer.lookup_transform(frame, name, rclpy.time.Time())
  ```
  Surround with `try...except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException)` and retain the previous valid state or transition to an explicit fallback state.

---

## 2. Cross-OS FastDDS Unicast Network Discovery
- **Anti-Pattern**: Relying on DDS default multicast discovery between Windows 11 host and WSL2 Ubuntu guest over Hyper-V `vEthernet (WSL)`.
- **Failure Mode**: Windows Defender Firewall Public profile silently drops UDP multicast packets. Furthermore, WSL2 IP address is dynamically reassigned upon every Windows reboot.
- **Fix**:
  1. Exempt the `vEthernet (WSL)` interface in Windows Firewall (via `setup_firewall_wsl2.bat`).
  2. Maintain synchronized FastDDS Unicast XML profiles (`fastdds_profile.xml`) containing explicit `initialPeersList` for both the Windows host gateway IP (`172.x.x.1`) and WSL2 guest IP.
  3. Execute `setup_fastdds_wsl.py` during launcher bringup to dynamically detect current IPs and refresh the XML configuration.

---

## 3. Windows Batch Launcher Execution & CRLF Formatting
- **Anti-Pattern**: Saving `.bat` or `.cmd` launcher files with UNIX `LF` line terminators or containing multi-byte UTF-8 Unicode characters (such as emojis `🤖` or Unicode box-drawing glyphs `╔══╗`).
- **Failure Mode**: Windows `cmd.exe` miscalculates byte offsets when seeking `:LABEL` jump points during execution, throwing `"The system cannot find the batch label specified"`, executing incorrect label fallthroughs, or triggering Windows `"현재 PC에서는 이 앱을 실행할 수 없습니다"` on 0-byte/corrupted files.
- **Fix**: Always enforce strict ASCII encoding with standard Windows CRLF (`\r\n`) line endings for all `.bat` files.

---

## 4. Multi-Robot Spatial Mutual Exclusion & Mid-Air Collisions
- **Anti-Pattern**: Releasing the shared center table lock (`center_occupied_by`) at the onset of `RETURN_HOME` while the manipulator arm is still physically sweeping through the center staging volume.
- **Failure Mode**: Waiting robots acquire the center lock prematurely and swing into the center zone, resulting in mid-air arm collisions.
- **Fix**: Enforce state-gated mutual exclusion:
  ```python
  CENTER_WORKSPACE_STATES = {
      'TUCK_AFTER_PICK', 'ROTATE_TO_PLACE', 'HOVER_PLACE', 
      'DESCEND_PLACE', 'RELEASE', 'RETRACT', 'TUCK_AFTER_PLACE', 'RETURN_HOME'
  }
  ```
  A waiting robot in `WAIT_FOR_CENTER` may only enter if the center lock is free AND no other robot's current state is in `CENTER_WORKSPACE_STATES`. The lock must only be cleared when `step_counter >= total_steps` of `RETURN_HOME`.

---

## 5. Isaac Sim PhysX Gripper Dwell Dynamics
- **Anti-Pattern**: Setting gripper dwell duration to $\le 5$ ticks ($< 100$ ms) at 50 Hz.
- **Failure Mode**: The arm commands `LIFT` while the PhysX parallel fingers are still traveling inward, before contact normal forces develop. The gripper slips off the block, leaving the object on the table.
- **Fix**: Franka parallel fingers require 250–350 ms under PhysX joint drive dynamics to contact a rigid block and develop normal grasp force. Always configure `dwell_steps >= 15` (at 50 Hz, $\ge 300$ ms) for both `GRASP` and `RELEASE` phases.

---

## 6. Windowed Physical Grasp Verification
- **Anti-Pattern**: Checking `gripper_pos > 0.01` to determine grasp success.
- **Failure Mode**: If the gripper command was dropped or delayed and fingers remained wide open ($0.04$ m), this condition evaluates to true, registering a false-positive pick and attempting to stack air.
- **Fix**: Implement a windowed physical grasp verification check tailored to block geometry ($4.5$ cm):
  ```python
  pick_success = 0.005 < current_gripper < 0.038
  ```
  Under-travel ($< 5$ mm) signals empty-hand closure; over-travel ($> 38$ mm) indicates unactuated open fingers.

---

## 7. Zero-Drop Anti-Bounce Tower Stacking
- **Anti-Pattern**: Releasing stacked blocks from an elevated offset (e.g. $+5$ mm clearance) to avoid contacting the underlying block.
- **Failure Mode**: In rigid body simulation engines (PhysX 5 TGS), dropped blocks experience contact restitution and numerical solver impulses, causing stacked towers ($N \ge 4$) to tilt, slide, or collapse.
- **Fix**: Calculate the continuous surface contact height directly:
  $$Z_{\text{target}} = Z_{\text{table\_top}} + \left(N - \frac{1}{2}\right) H_{\text{block}}$$
  Command the descent directly to $Z_{\text{target}}$, hold nominal joint targets during `RELEASE`, and vertically `RETRACT`.

---

## 8. Front-End Goal Debouncing & Runaway VLA Requests
- **Anti-Pattern**: Allowing direct unthrottled dispatch of UI button clicks or React 18 Strict Mode double-invocations to the `/gemini/custom_goal` ROS 2 topic.
- **Failure Mode**: Rapid duplicate goal dispatches abort in-flight agentic threads mid-execution, triggering cascading cancellation warnings and runaway API billing.
- **Fix**: Implement a mandatory timestamp debouncer ($\ge 2.0$ s) inside the goal callback (`_custom_goal_callback`) to filter duplicate bursts.

---

## 9. Fabric Scene Delegate & Duplicate TF Link Overrides
- **Anti-Pattern**: Adding static environment objects (`/Table1`, `/Table2`, `/TargetTable`) to the `targetPrims` of the `ROS2PublishTransformTree` OmniGraph node, or publishing multiple identical robot links without namespaces.
- **Failure Mode**: Isaac Sim Fabric generates `getObjectType eInvalid` PoseTree warnings and floods the console with duplicate TF frame resolution conflicts.
- **Fix**: Omit static table prims from dynamic TF publisher targets (publish their transforms once via static TF or URDF). For multiple identical robots, set explicit `isaac:nameOverride` attributes on articulation prims (e.g., `FR3_1_fr3_link0`, `FR3_2_fr3_link0`).

---

## 10. Read-Only Verification Services
- **Anti-Pattern**: Issuing joint homing commands or opening grippers inside inspection services like `verify_tower`.
- **Failure Mode**: Querying tower health causes active robots holding blocks to immediately open their grippers, dropping blocks and destroying the construction.
- **Fix**: Verification routines must remain strictly **read-only**: inspect TF buffers, query tower layer counts, return status messages, and NEVER mutate joint or gripper targets.
