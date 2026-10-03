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

---

## 6. Shared Controller Architecture & Anti-Divergence Rule

### Code Duplication Anti-Pattern:
Duplicating controller nodes across different demo scripts (e.g. copying `multi_robot_controller.py` into `conveyor_dual_controller.py`) inevitably leads to bug regressions. For example, fixing a race condition or grasp threshold in one mode leaves other modes vulnerable.

### Unified Inheritance Invariant:
All specialized multi-robot controllers must inherit directly from the canonical `MultiRobotController`:
- **Base Class (`MultiRobotController`)**: Provides DLS IK, SVD pseudoinverse, null-space decoupling, quintic polynomial minimum-jerk trajectory generation, `CENTER_WORKSPACE_STATES` mutual exclusion, read-only `verify_tower`, 300 ms dwell, and windowed physical grasp verification (`0.005 < current_gripper < 0.038`).
- **Derived Class (`ConveyorDualController`)**: Overrides only domain-specific behaviors (e.g., `active_robot_ids = [1, 2]`, dual-arm offset calculation for long bars, dynamic conveyor velocity forward prediction).

---

## 7. Motion Planning Roadmap: MoveIt 2 vs. cuMotion Decision

### The Architectural Choice:
Between **Path A** (Isaac Sim native cuMotion/cuRobo on Windows) and **Path B** (MoveIt 2 in ROS 2 Jazzy on WSL2):

**MoveIt 2 with Trajectory Adapter (Path B) is the superior architectural foundation:**
1. **Gemini VLA Co-Location**: MoveIt 2 lives in the same ROS 2 process environment as the Gemini VLA brain (`gemini_robotics_node.py`), allowing seamless action dispatch, TF tree querying, and collision-aware planning without cross-OS RPC latency.
2. **Standardized Manipulation Stack**: Provides deterministic OMPL and Pilz planners, multi-arm collision scene representation (`three_robot_scene.srdf`), and standard action interfaces (`FollowJointTrajectory`).
3. **Future-Proof GPU Acceleration**: NVIDIA's `isaac_ros_cumotion` is released as a **MoveIt 2 planner plugin**. Adopting MoveIt 2 now does not preclude GPU acceleration; it enables cuMotion to be plugged in transparently as an accelerated backend under MoveIt 2 without altering the ROS 2 application interface.

---

## 8. Manipulator Kinematic Azimuth Reachability & Joint 1 Blind Spot

### The Physical Root Cause of Pick Failures:
1. **Franka FR3 Joint 1 Hardstop**: The mechanical limit of Joint 1 on the Franka FR3 is $[-2.8973, +2.8973]\,\text{rad}$ ($\pm 166.004^\circ$). It has a physical **$28^\circ$ blind zone** directly behind its base ($|\theta| > 166^\circ$).
2. **The Collinear Workstation Anti-Pattern**: Mounting robot bases facing radial inward (FR3_1 at $90^\circ$, FR3_2 at $210^\circ$, FR3_3 at $330^\circ$) while placing source tables directly behind them at $180^\circ$ relative azimuth forces the robot to reach directly into its mechanical blind spot. Any spawn noise ($\pm 3\,\text{cm}$) or position variation clips Joint 1 at $166^\circ$, resulting in a $14^\circ$ azimuth offset ($15\,\text{cm}$ Cartesian error at the table).
3. **The Tangential Mounting Solution**:
   Orienting robot bases tangentially:
   - **FR3_1**: base yaw = $0^\circ$
   - **FR3_2**: base yaw = $120^\circ$
   - **FR3_3**: base yaw = $240^\circ$
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

# 📝 Lessons Learned: Why We Rolled Back

## The "Inaccurate Pick and Place" Issue & Why We Rolled Back ATAMP

Over the course of this project, we attempted to migrate to a highly advanced autonomous Task and Motion Planner (ATAMP) using external dependencies like MoveIt or custom path planners. However, we discovered several critical issues that led us to roll back to our deterministic, Rule-Based DLS IK framework combined with Gemini VLA:

### 1. The Block Size & Clearance Collision
When testing the multi-robot setup, FR3_1 and FR3_2 frequently missed blocks or grasped "empty space." We discovered that the grasping failure was not the fault of the VLM, but a fundamental kinematic modeling issue:
- **The Issue**: The cubes were spawned at 6cm wide. The Franka FR3 gripper's maximum opening is 8cm (4cm per finger). This left only 1cm of clearance on each side.
- **The Result**: Numerical inaccuracies in the IK (DLS numerical drift) caused the fingers to clip the edges of the blocks during the `DESCEND_PICK` phase, pushing the blocks away. When the gripper transitioned to `GRASP`, it squeezed empty space, causing the `LIFT` phase to abort (as it detected the fingers closing to < 0.5cm).
- **The Fix**: We reduced the block sizes to **4.5cm** (0.045m), allowing a healthy 3.5cm of clearance. We also increased the DLS Inverse Kinematics `max_iter` from 60 to 150 to guarantee convergence to the exact millimeter.

### 2. ROS 2 Jazzy & MoveIt 2 Instability
We attempted to integrate MoveIt 2 for full Cartesian trajectory planning. However:
- We faced missing `GTest` mocks and `pinocchio` CMake targets on WSL2 Ubuntu 24.04 (ROS 2 Jazzy). 
- Relying on external complex motion planners for a highly structured 3-robot environment introduced massive latency and frequent "No Motion Plan Found" errors, especially for FR3_1 and FR3_2 whose source tables are exactly at the edge of their kinematic reach (0.60m - 0.70m).
- **The Fix**: We rolled back to our robust `kinematics.py` module using DLS (Damped Least Squares) numerical IK with null-space posture regularization. It is mathematically predictable, has zero overhead, and works perfectly for vertical tower stacking.

### 3. The "4 Times in One Command" VLM Bug
During manual testing, users noticed that clicking "Send" in the React UI seemed to cause Gemini to be invoked 4 times.
- **The Issue**: React 18 Strict Mode and rapid UI double-clicks caused the `/gemini/custom_goal` ROS 2 topic to receive duplicate bursts of messages. The Python node attempted to rapidly abort and restart the agentic thread, causing runaway API calls.
- **The Fix**: We implemented a strict 2.0-second timestamp debouncer in `_custom_goal_callback` to completely isolate the node from frontend anomalies. 

### 4. VLA Cognitive Strategy vs Motion Planning
We successfully separated concerns:
- **Gemini-Robotics-ER2** acts purely as the Cognitive VLA Orchestrator. It receives a visual frame and outputs the high-level functional strategy.
- **RuleBasedTaskVerifier** intercepts every VLA tool call, auto-correcting any hallucinations (e.g. assigning a block to the wrong robot).
- **Kinematics & State Machine** handles the actual deterministic execution, shielding the VLM from low-level joint math.
- - -  
 n a m e :   m u l t i - r o b o t - m o t i o n - p l a n n i n g  
 d e s c r i p t i o n :   > -  
     A d v a n c e d   m u l t i - r o b o t   m a n i p u l a t i o n ,   c o l l i s i o n - f r e e   w o r k s p a c e   c o o r d i n a t i o n ,   a n d   h i g h - r e l i a b i l i t y  
     p i c k - a n d - p l a c e   e x e c u t i o n   f o r   m u l t i - a r m   F r a n k a   F R 3   s t a t i o n s   i n   N V I D I A   I s a a c   S i m   a n d   R O S   2   J a z z y .  
     C o v e r s   k i n e m a t i c   s o l v e r s ,   n u l l - s p a c e   d e c o u p l i n g ,   m u t u a l - e x c l u s i o n   s p a t i a l   z o n e s ,   g r i p p e r   d w e l l   d y n a m i c s ,  
     a n d   c o n t a c t - s a f e   t o w e r   s t a c k i n g .  
 - - -  
  
 #   M u l t i - R o b o t   M o t i o n   P l a n n i n g   &   C o o r d i n a t i o n   S k i l l  
  
 T h i s   s k i l l   d i s t i l l s   t h e   e n g i n e e r i n g   p r a c t i c e s ,   m a t h e m a t i c a l   f o r m u l a t i o n s ,   a n d   o p e r a t i o n a l   r u l e s   f o r   r e l i a b l e   m u l t i - r o b o t   m a n i p u l a t i o n   w i t h i n   N V I D I A   I s a a c   S i m   a n d   R O S   2 .  
  
 # #   1 .   M u l t i - R o b o t   S p a t i a l   D e c o n f l i c t i o n   &   M u t u a l   E x c l u s i o n  
  
 # # #   P r o b l e m :   M i d - A i r   A r m   C o l l i s i o n s  
 I n   m u l t i - a r m   c i r c u l a r   w o r k s t a t i o n s   ( e . g . ,   3 x   F r a n k a   F R 3   a r o u n d   a   c e n t r a l   s t a g i n g   t a b l e ) ,   c o l l i s i o n s   o c c u r   w h e n :  
 1 .   T w o   r o b o t s   e n t e r   t h e   c e n t e r   w o r k s p a c e   s i m u l t a n e o u s l y .  
 2 .   A   r o b o t   r e l e a s e s   t h e   m u t u a l - e x c l u s i o n   l o c k   w h i l e   i t s   a r m   i s   s t i l l   p h y s i c a l l y   s w e e p i n g   t h r o u g h   t h e   c e n t e r   z o n e   d u r i n g   r e t r a c t i o n   o r   h o m i n g .  
 3 .   P u r e   j o i n t - s p a c e   i n t e r p o l a t i o n   s w e e p s   e l b o w s   t h r o u g h   u n m o d e l e d   i n t e r m e d i a t e   v o l u m e s .  
  
 # # #   S o l u t i o n :   S t a t e - G a t e d   S p a t i a l   M u t u a l   E x c l u s i o n  
 A   s i m p l e   b i n a r y   l o c k   ( ` c e n t e r _ o c c u p i e d _ b y ` )   i s   n e c e s s a r y   b u t   n o t   s u f f i c i e n t .   I t   m u s t   b e   p a i r e d   w i t h   a n   i n v a r i a n t   s t a t e   g a t e :  
  
 ` ` ` p y t h o n  
 C E N T E R _ W O R K S P A C E _ S T A T E S   =   {  
         ' T U C K _ A F T E R _ P I C K ' ,   ' R O T A T E _ T O _ P L A C E ' ,   ' H O V E R _ P L A C E ' ,    
         ' D E S C E N D _ P L A C E ' ,   ' R E L E A S E ' ,   ' R E T R A C T ' ,   ' T U C K _ A F T E R _ P L A C E ' ,   ' R E T U R N _ H O M E '  
 }  
 ` ` `  
  
 * * I n v a r i a n t   R u l e * * :   A   r o b o t   e n t e r i n g   ` W A I T _ F O R _ C E N T E R `   m a y   o n l y   c l a i m   t h e   c e n t e r   i f :  
 ` ` ` p y t h o n  
 i s _ f r e e   =   ( s e l f . c e n t e r _ o c c u p i e d _ b y   i s   N o n e   o r   s e l f . c e n t e r _ o c c u p i e d _ b y   = =   r o b o t _ i d )   a n d   \  
                     n o t   a n y ( g e t a t t r ( s e l f ,   f ' s t a t e { o } ' )   i n   C E N T E R _ W O R K S P A C E _ S T A T E S   f o r   o   i n   [ 1 ,   2 ,   3 ]   i f   o   ! =   r o b o t _ i d )  
 ` ` `  
  
 * * L o c k   R e l e a s e   B o u n d a r y * * :   T h e   c e n t e r   m u t e x   M U S T   N O T   b e   r e l e a s e d   a t   t h e   b e g i n n i n g   o f   ` R E T U R N _ H O M E ` .   I t   m u s t   o n l y   b e   r e l e a s e d   w h e n   ` s t e p _ c o u n t e r   > =   t o t a l _ s t e p s `   o f   ` R E T U R N _ H O M E ` ,   w h e n   t h e   p h y s i c a l   m a n i p u l a t o r   h a s   c l e a r e d   t h e   b o u n d a r y   o f   t h e   c e n t r a l   s t a g i n g   t a b l e .  
  
 - - -  
  
 # #   2 .   H i g h - R e l i a b i l i t y   G r a s p i n g   &   F i n g e r   D y n a m i c s   i n   I s a a c   S i m  
  
 # # #   P r o b l e m :   R o b o t s   L i f t i n g   o n   E m p t y   A i r  
 1 .   * * D w e l l   T i m e   U n d e r s h o o t * * :   P h y s X   j o i n t   d r i v e s   o n   F r a n k a   p a r a l l e l   f i n g e r s   r e q u i r e   2 5 0 ? ? 5 0   m s   u n d e r   d y n a m i c   s o l v e r   i t e r a t i o n s   t o   c l o s e   o n   a n   o b j e c t   a n d   d e v e l o p   n o r m a l   f o r c e .   S e t t i n g   ` d w e l l _ s t e p s   <   1 5 `   ( a t   5 0   H z ,   <   3 0 0   m s )   c a u s e s   t h e   a r m   t o   l i f t   w h i l e   f i n g e r s   a r e   s t i l l   t r a v e l i n g .  
 2 .   * * F a l s e - P o s i t i v e   G r a s p   D e t e c t i o n * * :   T e s t i n g   ` g r i p p e r _ p o s   >   0 . 0 1 `   t r e a t s   a   w i d e - o p e n   g r i p p e r   ( $ 0 . 0 4 $   m )   a s   a   s u c c e s s f u l   g r a s p   i f   t h e   c l o s e   c o m m a n d   l a g g e d   o r   t i m e d   o u t .  
 3 .   * * A r m   D r i f t   D u r i n g   G r a s p i n g * * :   U s i n g   m e a s u r e d   j o i n t   s t a t e   d u r i n g   t h e   d w e l l   p h a s e   a l l o w s   c o n t a c t   r e a c t i o n   f o r c e s   t o   b a c k d r i v e   t h e   a r m .  
  
 # # #   R u l e s   f o r   R e l i a b l e   G r a s p i n g :  
 1 .   * * D w e l l   D u r a t i o n * * :   A l w a y s   a l l o w   a t   l e a s t   $ 0 . 3 0 $   s   ( $ \ g e   1 5 $   s t e p s   a t   5 0   H z )   f o r   f i n g e r   c l o s u r e   b e f o r e   i n i t i a t i n g   ` L I F T ` .  
 2 .   * * R i g i d   T a r g e t   H o l d i n g * * :   I n   ` G R A S P `   a n d   ` R E L E A S E ` ,   h o l d   t h e   n o m i n a l   w a y p o i n t   ` e n d _ q `   r a t h e r   t h a n   t h e   m e a s u r e d   ` q _ c u r r e n t ` :  
       ` ` ` p y t h o n  
       q _ s o l   =   n p . a r r a y ( e n d _ q )  
       ` ` `  
 3 .   * * W i n d o w e d   G r a s p   V e r i f i c a t i o n * * :  
       F o r   a   $ 6 $   c m   b l o c k   w i t h   s t a n d a r d   F r a n k a   f i n g e r s   ( $ 0 . 0 4 $   m   m a x   p e r   f i n g e r ) :  
       -   F u l l y   c l o s e d   o n   e m p t y   s p a c e :   $ \ l e   0 . 0 0 5 $   m .  
       -   F u l l y   o p e n   ( m i s s e d   c l o s e   c o m m a n d ) :   $ \ g e   0 . 0 3 8 $   m .  
       -   S u c c e s s f u l   p h y s i c a l   g r a s p :  
       ` ` ` p y t h o n  
       p i c k _ s u c c e s s   =   0 . 0 0 5   <   c u r r e n t _ g r i p p e r   <   0 . 0 3 8  
       ` ` `  
  
 - - -  
  
 # #   3 .   P r e c i s i o n   T o w e r   S t a c k i n g   &   C o n t a c t   S u r f a c e   A l i g n m e n t  
  
 # # #   S t a c k i n g   H e i g h t   I n v a r i a n t :  
 -   S t a c k i n g   s u r f a c e   o f   t a r g e t   t a b l e :   $ Z _ { \ t e x t { t a b l e } }   =   0 . 3 0 $   m .  
 -   B l o c k   d i m e n s i o n :   $ H   =   0 . 0 6 $   m   ( c u b e   o r   c y l i n d e r ) .  
 -   B a s e   b l o c k   c e n t e r :   $ Z _ 1   =   0 . 3 0   +   H / 2   =   0 . 3 3 0 $   m .  
 -   $ N $ - t h   b l o c k   c e n t e r :   $ Z _ N   =   Z _ { N - 1 }   +   H $ .  
  
 # # #   A n t i - B o u n c e   Z e r o - D r o p   R u l e :  
 D o   n o t   d r o p   b l o c k s   f r o m   a n   e l e v a t e d   o f f s e t   ( e . g .   $ + 5 $   m m   c l e a r a n c e )   w h e n   s t a c k i n g   r i g i d   b o d i e s   i n   P h y s X .   H i g h   r e s t i t u t i o n   o r   s o l v e r   i m p u l s e   c a u s e s   t o p   b l o c k s   t o   t i l t   a n d   t u m b l e .   A l w a y s   c o m m a n d   t h e   d e s c e n t   d i r e c t l y   t o   t h e   c o n t a c t   h e i g h t   ( $ Z _ N $ ) ,   h o l d   p o s i t i o n   d u r i n g   ` R E L E A S E ` ,   a n d   t h e n   v e r t i c a l l y   ` R E T R A C T ` .  
  
 - - -  
  
 # #   4 .   D L S   I n v e r s e   K i n e m a t i c s   &   N u l l - S p a c e   D e c o u p l i n g  
  
 # # #   P r o b l e m :   A z i m u t h   F i g h t i n g   &   E l b o w   D r i f t  
 W h e n   a n   i t e r a t i v e   D a m p e d   L e a s t   S q u a r e s   ( D L S )   s o l v e r   i n c l u d e s   a   n u l l - s p a c e   p o s t u r e   r e g u l a r i z a t i o n   t e r m :  
 $ $ \ D e l t a   q   =   J ^ { \ d a g g e r }   e   +   ( I   -   J ^ { \ d a g g e r }   J )   k _ { \ t e x t { n u l l } }   ( q _ { \ t e x t { h o m e } }   -   q ) $ $  
 I f   $ q _ { \ t e x t { h o m e } } [ 0 ]   =   0 . 0 $   w h i l e   t h e   r o b o t   i s   t a s k e d   t o   p i c k   f r o m   a   r e a r   t a b l e   ( $ J _ 1   \ a p p r o x   \ p i $ ) ,   t h e   n u l l - s p a c e   p r o j e c t i o n   e x e r t s   a n   i n t e r n a l   t o r q u e   p u l l i n g   J o i n t   1   a w a y   f r o m   t h e   a z i m u t h   g o a l .   T h i s   c a u s e s   s o l v e r   s t a g n a t i o n   a n d   j o i n t   l i m i t   c l i p p i n g .  
  
 # # #   F i x :   D e c o u p l e   J o i n t   1   f r o m   N u l l - S p a c e   B i a s  
 ` ` ` p y t h o n  
 g r a d _ n u l l   =   k _ n u l l   *   ( F R 3 _ H O M E _ C O N F I G   -   q )  
 g r a d _ n u l l [ 0 ]   =   0 . 0     #   A l l o w   J o i n t   1   a z i m u t h   t o   b e   d r i v e n   p u r e l y   b y   t a s k - s p a c e   t r a c k i n g  
 n u l l _ s p a c e _ t e r m   =   ( n p . e y e ( 7 )   -   i n v _ J   @   J )   @   g r a d _ n u l l  
 ` ` `  
  
 - - -  
  
 # #   5 .   V e r i f i c a t i o n   C h e c k l i s t   f o r   M u l t i - R o b o t   C o n t r o l l e r s  
  
 B e f o r e   r u n n i n g   f u l l   m u l t i - r o b o t   s i m u l a t i o n s ,   v e r i f y :  
 -   [   ]   ` s t e p s _ p e r _ p h a s e `   $ \ g e   3 0 $   ( $ 0 . 6 $   s )   f o r   s t a b l e   C a r t e s i a n   d e s c e n t .  
 -   [   ]   ` d w e l l _ s t e p s `   $ \ g e   1 5 $   ( $ 0 . 3 $   s )   f o r   g r i p p e r   t o u c h   a n d   f r i c t i o n   e n g a g e m e n t .  
 -   [   ]   ` C E N T E R _ W O R K S P A C E _ S T A T E S `   g u a r d   a c t i v e   o n   a l l   c e n t e r   t r a n s i t i o n s .  
 -   [   ]   ` v e r i f y _ t o w e r `   s e r v i c e   /   t o p i c   i s   s t r i c t l y   r e a d - o n l y   a n d   n e v e r   i s s u e s   j o i n t   c o m m a n d s .  
 -   [   ]   G r a s p   v e r i f i c a t i o n   v e r i f i e s   u p p e r   a n d   l o w e r   f i n g e r   g a p   b o u n d s .  
  
 - - -  
  
 # #   6 .   S h a r e d   C o n t r o l l e r   A r c h i t e c t u r e   &   A n t i - D i v e r g e n c e   R u l e  
  
 # # #   C o d e   D u p l i c a t i o n   A n t i - P a t t e r n :  
 D u p l i c a t i n g   c o n t r o l l e r   n o d e s   a c r o s s   d i f f e r e n t   d e m o   s c r i p t s   ( e . g .   c o p y i n g   ` m u l t i _ r o b o t _ c o n t r o l l e r . p y `   i n t o   ` c o n v e y o r _ d u a l _ c o n t r o l l e r . p y ` )   i n e v i t a b l y   l e a d s   t o   b u g   r e g r e s s i o n s .   F o r   e x a m p l e ,   f i x i n g   a   r a c e   c o n d i t i o n   o r   g r a s p   t h r e s h o l d   i n   o n e   m o d e   l e a v e s   o t h e r   m o d e s   v u l n e r a b l e .  
  
 # # #   U n i f i e d   I n h e r i t a n c e   I n v a r i a n t :  
 A l l   s p e c i a l i z e d   m u l t i - r o b o t   c o n t r o l l e r s   m u s t   i n h e r i t   d i r e c t l y   f r o m   t h e   c a n o n i c a l   ` M u l t i R o b o t C o n t r o l l e r ` :  
 -   * * B a s e   C l a s s   ( ` M u l t i R o b o t C o n t r o l l e r ` ) * * :   P r o v i d e s   D L S   I K ,   S V D   p s e u d o i n v e r s e ,   n u l l - s p a c e   d e c o u p l i n g ,   q u i n t i c   p o l y n o m i a l   m i n i m u m - j e r k   t r a j e c t o r y   g e n e r a t i o n ,   ` C E N T E R _ W O R K S P A C E _ S T A T E S `   m u t u a l   e x c l u s i o n ,   r e a d - o n l y   ` v e r i f y _ t o w e r ` ,   3 0 0   m s   d w e l l ,   a n d   w i n d o w e d   p h y s i c a l   g r a s p   v e r i f i c a t i o n   ( ` 0 . 0 0 5   <   c u r r e n t _ g r i p p e r   <   0 . 0 3 8 ` ) .  
 -   * * D e r i v e d   C l a s s   ( ` C o n v e y o r D u a l C o n t r o l l e r ` ) * * :   O v e r r i d e s   o n l y   d o m a i n - s p e c i f i c   b e h a v i o r s   ( e . g . ,   ` a c t i v e _ r o b o t _ i d s   =   [ 1 ,   2 ] ` ,   d u a l - a r m   o f f s e t   c a l c u l a t i o n   f o r   l o n g   b a r s ,   d y n a m i c   c o n v e y o r   v e l o c i t y   f o r w a r d   p r e d i c t i o n ) .  
  
 - - -  
  
 # #   7 .   M o t i o n   P l a n n i n g   R o a d m a p :   M o v e I t   2   v s .   c u M o t i o n   D e c i s i o n  
  
 # # #   T h e   A r c h i t e c t u r a l   C h o i c e :  
 B e t w e e n   * * P a t h   A * *   ( I s a a c   S i m   n a t i v e   c u M o t i o n / c u R o b o   o n   W i n d o w s )   a n d   * * P a t h   B * *   ( M o v e I t   2   i n   R O S   2   J a z z y   o n   W S L 2 ) :  
  
 * * M o v e I t   2   w i t h   T r a j e c t o r y   A d a p t e r   ( P a t h   B )   i s   t h e   s u p e r i o r   a r c h i t e c t u r a l   f o u n d a t i o n : * *  
 1 .   * * G e m i n i   V L A   C o - L o c a t i o n * * :   M o v e I t   2   l i v e s   i n   t h e   s a m e   R O S   2   p r o c e s s   e n v i r o n m e n t   a s   t h e   G e m i n i   V L A   b r a i n   ( ` g e m i n i _ r o b o t i c s _ n o d e . p y ` ) ,   a l l o w i n g   s e a m l e s s   a c t i o n   d i s p a t c h ,   T F   t r e e   q u e r y i n g ,   a n d   c o l l i s i o n - a w a r e   p l a n n i n g   w i t h o u t   c r o s s - O S   R P C   l a t e n c y .  
 2 .   * * S t a n d a r d i z e d   M a n i p u l a t i o n   S t a c k * * :   P r o v i d e s   d e t e r m i n i s t i c   O M P L   a n d   P i l z   p l a n n e r s ,   m u l t i - a r m   c o l l i s i o n   s c e n e   r e p r e s e n t a t i o n   ( ` t h r e e _ r o b o t _ s c e n e . s r d f ` ) ,   a n d   s t a n d a r d   a c t i o n   i n t e r f a c e s   ( ` F o l l o w J o i n t T r a j e c t o r y ` ) .  
 3 .   * * F u t u r e - P r o o f   G P U   A c c e l e r a t i o n * * :   N V I D I A ' s   ` i s a a c _ r o s _ c u m o t i o n `   i s   r e l e a s e d   a s   a   * * M o v e I t   2   p l a n n e r   p l u g i n * * .   A d o p t i n g   M o v e I t   2   n o w   d o e s   n o t   p r e c l u d e   G P U   a c c e l e r a t i o n ;   i t   e n a b l e s   c u M o t i o n   t o   b e   p l u g g e d   i n   t r a n s p a r e n t l y   a s   a n   a c c e l e r a t e d   b a c k e n d   u n d e r   M o v e I t   2   w i t h o u t   a l t e r i n g   t h e   R O S   2   a p p l i c a t i o n   i n t e r f a c e .  
  
 - - -  
  
 # #   8 .   M a n i p u l a t o r   K i n e m a t i c   A z i m u t h   R e a c h a b i l i t y   &   J o i n t   1   B l i n d   S p o t  
  
 # # #   T h e   P h y s i c a l   R o o t   C a u s e   o f   P i c k   F a i l u r e s :  
 1 .   * * F r a n k a   F R 3   J o i n t   1   H a r d s t o p * * :   T h e   m e c h a n i c a l   l i m i t   o f   J o i n t   1   o n   t h e   F r a n k a   F R 3   i s   $ [ - 2 . 8 9 7 3 ,   + 2 . 8 9 7 3 ] \ , \ t e x t { r a d } $   ( $ \ p m   1 6 6 . 0 0 4 ^ \ c i r c $ ) .   I t   h a s   a   p h y s i c a l   * * $ 2 8 ^ \ c i r c $   b l i n d   z o n e * *   d i r e c t l y   b e h i n d   i t s   b a s e   ( $ | \ t h e t a |   >   1 6 6 ^ \ c i r c $ ) .  
 2 .   * * T h e   C o l l i n e a r   W o r k s t a t i o n   A n t i - P a t t e r n * * :   M o u n t i n g   r o b o t   b a s e s   f a c i n g   r a d i a l   i n w a r d   ( F R 3 _ 1   a t   $ 9 0 ^ \ c i r c $ ,   F R 3 _ 2   a t   $ 2 1 0 ^ \ c i r c $ ,   F R 3 _ 3   a t   $ 3 3 0 ^ \ c i r c $ )   w h i l e   p l a c i n g   s o u r c e   t a b l e s   d i r e c t l y   b e h i n d   t h e m   a t   $ 1 8 0 ^ \ c i r c $   r e l a t i v e   a z i m u t h   f o r c e s   t h e   r o b o t   t o   r e a c h   d i r e c t l y   i n t o   i t s   m e c h a n i c a l   b l i n d   s p o t .   A n y   s p a w n   n o i s e   ( $ \ p m   3 \ , \ t e x t { c m } $ )   o r   p o s i t i o n   v a r i a t i o n   c l i p s   J o i n t   1   a t   $ 1 6 6 ^ \ c i r c $ ,   r e s u l t i n g   i n   a   $ 1 4 ^ \ c i r c $   a z i m u t h   o f f s e t   ( $ 1 5 \ , \ t e x t { c m } $   C a r t e s i a n   e r r o r   a t   t h e   t a b l e ) .  
 3 .   * * T h e   T a n g e n t i a l   M o u n t i n g   S o l u t i o n * * :  
       O r i e n t i n g   r o b o t   b a s e s   t a n g e n t i a l l y :  
       -   * * F R 3 _ 1 * * :   b a s e   y a w   =   $ 0 ^ \ c i r c $  
       -   * * F R 3 _ 2 * * :   b a s e   y a w   =   $ 1 2 0 ^ \ c i r c $  
       -   * * F R 3 _ 3 * * :   b a s e   y a w   =   $ 2 4 0 ^ \ c i r c $  
       T r a n s f o r m s   t h e   o p e r a t i o n a l   w o r k s p a c e :  
       -   C e n t r a l   p l a c e m e n t   t a r g e t :   l o c a l   $ + 9 0 ^ \ c i r c $   ( $ + 1 . 5 7 0 8 \ , \ t e x t { r a d } $ )   $ \ t o $   $ 7 6 ^ \ c i r c $   m a r g i n   t o   j o i n t   l i m i t .  
       -   S o u r c e   p i c k   t a b l e s   &   b l o c k s :   l o c a l   $ - 7 8 ^ \ c i r c $   t o   $ - 1 0 1 ^ \ c i r c $   ( $ - 1 . 3 7 $   t o   $ - 1 . 7 7 \ , \ t e x t { r a d } $ )   $ \ t o $   $ 6 5 ^ \ c i r c + $   m a r g i n   t o   j o i n t   l i m i t .  
       -   B o t h   p i c k   a n d   p l a c e   t a r g e t s   r e s i d e   c o m f o r t a b l y   i n   t h e   h i g h - m a n i p u l a b i l i t y   r e g i o n   o f   t h e   a r m .  
  
 # # #   J o i n t   V e l o c i t y   L i m i t   &   T r a j e c t o r y   S c a l i n g :  
 -   F R 3   J o i n t   1   m a x   v e l o c i t y :   $ \ d o t { q } _ { 1 , \ t e x t { m a x } }   =   2 . 1 7 5 \ , \ t e x t { r a d / s } $ .  
 -   A   $ 1 8 0 ^ \ c i r c $   s w i n g   ( $ \ p i   =   3 . 1 4 \ , \ t e x t { r a d } $ )   b e t w e e n   s o u r c e   a n d   c e n t e r   t a b l e s   r e q u i r e s :  
     $ $ t _ { \ t e x t { m i n } }   \ g e   \ f r a c { 1 . 8 7 5   \ c d o t   \ p i } { 2 . 1 7 5 }   \ a p p r o x   2 . 7 \ , \ t e x t { s   ( q u i n t i c   p e a k ) } $ $  
 -   A l l o c a t i n g   f e w e r   t h a n   5 0   s t e p s   a t   5 0   H z   ( $ <   1 . 0 \ , \ t e x t { s } $ )   c a u s e s   s e v e r e   j o i n t   l a g   i n   s i m u l a t i o n ,   c a u s i n g   t h e   a r m   t o   a r r i v e   l a t e   a n d   d e s c e n d   d u r i n g   r e s i d u a l   r o t a t i o n a l   m o m e n t u m .  
 -   * * R u l e * * :   A l w a y s   a l l o c a t e   ` t o t a l _ s t e p s   =   m a x ( s t e p s _ p e r _ p h a s e ,   5 0 ) `   f o r   l a r g e   r o t a t i o n a l   p h a s e s   ( ` R O T A T E _ T O _ P I C K ` ,   ` R O T A T E _ T O _ P L A C E ` ,   ` R E T U R N _ H O M E ` ) .  
  
 