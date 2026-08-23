# SPDX-License-Identifier: Apache-2.0

import sys
import numpy as np
from PIL import Image
import yaml
from isaacsim import SimulationApp

# Start SimulationApp headlessly
simulation_app = SimulationApp({"headless": True})

import omni.usd
import omni.physx
import isaacsim.core.experimental.utils.app as app_utils

SCENE_USD_PATH = "D:/git/isaacsim/src/isaacsim/source/standalone_examples/api/isaacsim.ros2.bridge/industrial_mobile_manipulator_scene.usd"

print("Enabling occupancy map extension...")
app_utils.enable_extension("isaacsim.asset.gen.omap")
simulation_app.update()
simulation_app.update()

# Now import _omap AFTER the extension has been enabled
from isaacsim.asset.gen.omap.bindings import _omap

# Load the scene
print(f"Loading scene: {SCENE_USD_PATH}")
omni.usd.get_context().open_stage(SCENE_USD_PATH, None)
print("Waiting for stage loading...")
for _ in range(100):
    simulation_app.update()

# Start play to initialize PhysX
print("Starting play and waiting for PhysX warmup...")
app_utils.play()
for _ in range(100):
    simulation_app.update()

# Set up the generator
physx = omni.physx.get_physx_interface()
stage_id = omni.usd.get_context().get_stage_id()
generator = _omap.Generator(physx, stage_id)

CELL_SIZE = 0.05 # 5cm resolution
# Call update_settings using positional arguments
generator.update_settings(CELL_SIZE, 0.1, 1.8, 0.5)

# Define grid bounds: 10m x 10m centered around (0,0)
# Use a free point (1.0, -1.0, 0.0) as origin so flood-fill works correctly
generator.set_transform((1.0, -1.0, 0.0), (-6.0, -4.0, 0.0), (4.0, 6.0, 0.0))

print("Generating 2D occupancy map...")
generator.generate2d()
buffer = generator.get_buffer()

dims = generator.get_dimensions()
print(f"Map dimensions: {dims}")
width, height = dims[0], dims[1]

# Convert buffer to numpy array
map_data = np.array(buffer, dtype=np.uint8).reshape((height, width))

# In _omap: 0 = free, 127 = unknown, 255 = occupied (or similar).
# Let's write it to standard ROS grayscale:
# 254 = free (white), 0 = occupied (black), 205 = unknown (grey).
unique_vals = np.unique(map_data)
print(f"Unique values in buffer: {unique_vals}")

ros_map = np.full_like(map_data, 205) # Unknown
ros_map[map_data == 0] = 254
ros_map[(map_data == 1) | (map_data == 255)] = 0

# Save image
img_path = "D:/git/isaacsim/src/isaacsim/source/standalone_examples/api/isaacsim.ros2.bridge/map.png"
Image.fromarray(ros_map, 'L').save(img_path)
print(f"Saved map image to: {img_path}")

# Save YAML config
yaml_path = "D:/git/isaacsim/src/isaacsim/source/standalone_examples/api/isaacsim.ros2.bridge/map.yaml"
yaml_data = {
    "image": "map.png",
    "resolution": CELL_SIZE,
    "origin": [-5.0, -5.0, 0.0], # bottom-left corner in world space
    "negate": 0,
    "occupied_thresh": 0.65,
    "free_thresh": 0.196,
}

with open(yaml_path, "w") as f:
    yaml.dump(yaml_data, f, default_flow_style=False)
print(f"Saved map metadata to: {yaml_path}")

# Also copy them to the WSL workspace so ROS 2 can use them!
wsl_map_dir = "D:/git/isaacsim/src/isaacsim/wsl_ws/src/isaac_ros2_control/resource"
import os
import shutil
os.makedirs(wsl_map_dir, exist_ok=True)
shutil.copy(img_path, os.path.join(wsl_map_dir, "map.png"))
shutil.copy(yaml_path, os.path.join(wsl_map_dir, "map.yaml"))
print(f"Copied map files to WSL resource directory: {wsl_map_dir}")

app_utils.stop()
simulation_app.close()
