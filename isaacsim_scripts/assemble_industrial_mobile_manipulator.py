import sys
import numpy as np
import argparse

# Parse arguments first
parser = argparse.ArgumentParser()
parser.add_argument("--mobile-base", default="carter_v1", help="Mobile base type: nova_carter, carter_v1")
parser.add_argument("--environment", default="simple_room", help="Environment type: warehouse, office, simple_room, hospital")
args, unknown_args = parser.parse_known_args()

# Remove our custom args from sys.argv so SimulationApp doesn't complain about them
sys.argv = [sys.argv[0]] + unknown_args

from isaacsim import SimulationApp

# Start SimulationApp headlessly to build the scene
simulation_app = SimulationApp({"headless": True})

import carb
import omni.usd
import isaacsim.core.experimental.utils.stage as stage_utils
from isaacsim.core.experimental.utils.app import enable_extension
from isaacsim.storage.native import get_assets_root_path
from pxr import Gf, UsdGeom, UsdPhysics, Sdf, PhysxSchema

# Enable the robot schema extension and update
enable_extension("isaacsim.robot.schema")
simulation_app.update()

# Import from the correct namespace
from usd.schema.isaac.robot_schema import ApplyRobotAPI, Attributes
from usd.schema.isaac.robot_schema.utils import PopulateRobotSchemaFromArticulation

assets_root = get_assets_root_path()
if assets_root is None:
    print("Error: Could not find Isaac Sim assets folder")
    simulation_app.close()
    sys.exit(1)

# Define asset mappings
MOBILE_BASES = {
    "nova_carter": {
        "usd_path": "/Isaac/Robots/NVIDIA/NovaCarter/nova_carter.usd",
        "mount_height": 0.28
    },
    "carter_v1": {
        "usd_path": "/Isaac/Robots/NVIDIA/Carter/carter_v1.usd",
        "mount_height": 0.412
    }
}

ENVIRONMENTS = {
    "warehouse": "/Isaac/Environments/Simple_Warehouse/warehouse_with_forklifts.usd",
    "office": "/Isaac/Environments/Office/office.usd",
    "simple_room": "/Isaac/Environments/Simple_Room/simple_room.usd",
    "hospital": "/Isaac/Environments/Hospital/hospital.usd"
}

base_info = MOBILE_BASES.get(args.mobile_base, MOBILE_BASES["nova_carter"])
env_path = ENVIRONMENTS.get(args.environment, ENVIRONMENTS["simple_room"])

# Paths to assets
BACKGROUND_USD = assets_root + env_path
CARTER_USD = assets_root + base_info["usd_path"]
FR3_USD = assets_root + "/Isaac/Robots/FrankaRobotics/FrankaFR3/fr3.usd"
TABLE_USD = assets_root + "/Isaac/Props/Mounts/table.usd"
mount_height = base_info["mount_height"]

# 1. Create a new stage
print("Creating new USD stage...")
stage_utils.create_new_stage()
stage = omni.usd.get_context().get_stage()
stage_utils.set_stage_units(meters_per_unit=1.0)

# 2. Add background environment
print("Adding background environment...")
background_prim = stage.DefinePrim("/World/Background", "Xform")
background_prim.GetReferences().AddReference(BACKGROUND_USD)

# Remove table_low_327 if it exists in the background
for prim in stage.TraverseAll():
    if "table_low_327" in prim.GetName():
        print(f"Removing {prim.GetPath()}...")
        prim.SetActive(False)

# 3. Add Physics Scene
print("Setting up PhysicsScene...")
physics_scene = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
physics_scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0, 0, -1))
physics_scene.CreateGravityMagnitudeAttr().Set(9.81)

physx_scene = PhysxSchema.PhysxSceneAPI.Apply(physics_scene.GetPrim())
physx_scene.CreateEnableCCDAttr().Set(True)
physx_scene.CreateEnableStabilizationAttr().Set(True)
physx_scene.CreateSolverTypeAttr().Set("TGS")
physx_scene.CreateTimeStepsPerSecondAttr().Set(60)

# 4. Add the Mobile Manipulator
print(f"Adding mobile base ({args.mobile_base})...")
robot_prim = stage.DefinePrim("/World/Robot", "Xform")
robot_prim.GetReferences().AddReference(CARTER_USD)

# Position the robot chassis
xform_robot = UsdGeom.Xformable(robot_prim)
xform_robot.ClearXformOpOrder()
xform_robot.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, 0.15)) # slightly off the ground to settle nicely

# 5. Add the FR3 Arm on top of the mobile base
print("Adding FR3 arm...")
arm_prim = stage.DefinePrim("/World/Robot/chassis_link/fr3", "Xform")
arm_prim.GetReferences().AddReference(FR3_USD)

# Set mount height and translation
xform_arm = UsdGeom.Xformable(arm_prim)
xform_arm.ClearXformOpOrder()
xform_arm.AddTranslateOp().Set(Gf.Vec3d(0.08, 0.0, mount_height))

# Remove ArticulationRootAPI from the arm so the chassis remains the single articulation root
print("Configuring articulation root structure...")
fr3_root = stage.GetPrimAtPath("/World/Robot/chassis_link/fr3")
if fr3_root.HasAPI(UsdPhysics.ArticulationRootAPI):
    print("Removing ArticulationRootAPI from /World/Robot/chassis_link/fr3")
    fr3_root.RemoveAPI(UsdPhysics.ArticulationRootAPI)
    
fr3_link0 = stage.GetPrimAtPath("/World/Robot/chassis_link/fr3/fr3_link0")
if fr3_link0.HasAPI(UsdPhysics.ArticulationRootAPI):
    print("Removing ArticulationRootAPI from /World/Robot/chassis_link/fr3/fr3_link0")
    fr3_link0.RemoveAPI(UsdPhysics.ArticulationRootAPI)

# Dynamically find the root joint of the FR3 arm to avoid conflicts with our mount joint
found_root_joint = False
for child in fr3_root.GetChildren():
    if child.IsA(UsdPhysics.FixedJoint):
        print(f"Deactivating original FR3 fixed joint: {child.GetPath()}...")
        child.SetActive(False)
        found_root_joint = True

if not found_root_joint:
    print("Warning: Could not find a FixedJoint under FR3 to deactivate. It might be deeper in the hierarchy.")
    for prim in stage.TraverseAll():
        if prim.GetPath().pathString.startswith("/World/Robot/chassis_link/fr3") and prim.IsA(UsdPhysics.FixedJoint):
            # Deactivate any fixed joint that might anchor it to world
            # usually the root joint connects to nothing or 'world'
            body0 = UsdPhysics.FixedJoint(prim).GetBody0Rel().GetTargets()
            body1 = UsdPhysics.FixedJoint(prim).GetBody1Rel().GetTargets()
            if not body0 or not body1 or "world" in str(body0) or "world" in str(body1):
                print(f"Deactivating deep FR3 root joint: {prim.GetPath()}...")
                prim.SetActive(False)

# Define FixedJoint to attach FR3 arm to chassis_link
print("Defining FixedJoint mount...")
mount_joint = UsdPhysics.FixedJoint.Define(stage, "/World/Robot/chassis_link/fr3_mount")
mount_joint.CreateBody0Rel().SetTargets([Sdf.Path("/World/Robot/chassis_link")])
mount_joint.CreateBody1Rel().SetTargets([Sdf.Path("/World/Robot/chassis_link/fr3/fr3_link0")])
mount_joint.CreateLocalPos0Attr().Set(Gf.Vec3f(0.08, 0.0, mount_height))
mount_joint.CreateLocalPos1Attr().Set(Gf.Vec3f(0.0, 0.0, 0.0))

from pxr import PhysxSchema
PhysxSchema.PhysxJointAPI.Apply(mount_joint.GetPrim())

# Disable collision between chassis_link and fr3_link0
filtered_pairs_api = UsdPhysics.FilteredPairsAPI.Apply(stage.GetPrimAtPath("/World/Robot/chassis_link"))
filtered_pairs_api.GetFilteredPairsRel().AddTarget(Sdf.Path("/World/Robot/chassis_link/fr3/fr3_link0"))

# 6. Apply Isaac Robot Schema
print("Applying Robot Schema overlay...")
chassis_prim = stage.GetPrimAtPath("/World/Robot/chassis_link")
ApplyRobotAPI(chassis_prim)
chassis_prim.GetAttribute(Attributes.ROBOT_TYPE.name).Set("Mobile Manipulators")
PopulateRobotSchemaFromArticulation(stage, chassis_prim)

# 7. Add Industrial Tables
print("Adding tables...")
table1 = stage.DefinePrim("/World/Table_1", "Xform")
table1.GetReferences().AddReference(TABLE_USD)
xform_table1 = UsdGeom.Xformable(table1)
xform_table1.ClearXformOpOrder()
xform_table1.AddTranslateOp().Set(Gf.Vec3d(1.8, 0.0, 0.0)) # In front of robot

table2 = stage.DefinePrim("/World/Table_2", "Xform")
table2.GetReferences().AddReference(TABLE_USD)
xform_table2 = UsdGeom.Xformable(table2)
xform_table2.ClearXformOpOrder()
xform_table2.AddTranslateOp().Set(Gf.Vec3d(0.0, 1.8, 0.0)) # On the side of the robot

# Apply static collision properties to the tables so they are interactive and do not fall
print("Applying collision properties to tables...")
for path in ["/World/Table_1", "/World/Table_2"]:
    prim = stage.GetPrimAtPath(path)
    if prim.IsValid():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            prim.RemoveAPI(UsdPhysics.RigidBodyAPI)
        rb_enabled = prim.GetAttribute("physics:rigidBodyEnabled")
        if rb_enabled.IsValid():
            rb_enabled.Set(False)
            
for path in ["/World/Table_1/DemoTable", "/World/Table_2/DemoTable"]:
    prim = stage.GetPrimAtPath(path)
    if prim.IsValid():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            prim.RemoveAPI(UsdPhysics.RigidBodyAPI)
        rb_enabled = prim.GetAttribute("physics:rigidBodyEnabled")
        if rb_enabled.IsValid():
            rb_enabled.Set(False)
        kin_enabled = prim.GetAttribute("physics:kinematicEnabled")
        if kin_enabled.IsValid():
            kin_enabled.Set(False)
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            UsdPhysics.CollisionAPI.Apply(prim)

# 8. Add Pick and Place Blocks on Table 1
print("Adding blocks...")
block_initial_positions = [
    [1.6, 0.15, 0.735],
    [1.6, -0.15, 0.735],
    [1.7, 0.15, 0.735],
    [1.7, -0.15, 0.735]
]
for i, pos in enumerate(block_initial_positions):
    block_path = f"/World/Block{i+1}"
    cube = UsdGeom.Cube.Define(stage, block_path)
    cube.GetSizeAttr().Set(1.0) # size 1.0 means scale acts as dimensions
    
    xform_cube = UsdGeom.Xformable(cube.GetPrim())
    xform_cube.ClearXformOpOrder()
    xform_cube.AddTranslateOp().Set(Gf.Vec3d(*pos))
    xform_cube.AddScaleOp().Set(Gf.Vec3f(0.04, 0.04, 0.04)) # 4cm cube block
    
    # Enable physics and collision APIs
    UsdPhysics.RigidBodyAPI.Apply(cube.GetPrim())
    UsdPhysics.CollisionAPI.Apply(cube.GetPrim())

# 9. Save stage to file using Export
import os
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "industrial_mobile_manipulator_scene.usd")
print(f"Saving USD scene to: {output_path}")
stage.GetRootLayer().Export(output_path)

print("USD Stage assembly complete!")
simulation_app.close()
