# isaac_ros2_control package
import sys
from pathlib import Path

for _cand in (
    Path(__file__).resolve().parents[4] / "private" / "research" / "ros2_nodes",
    Path.home() / "catkin_ws" / "private" / "research" / "ros2_nodes",
    Path("/mnt/d/git/IsaacSim_Gemini/private/research/ros2_nodes"),
):
    try:
        if _cand.is_dir():
            _p = str(_cand)
            if _p not in __path__:
                __path__.append(_p)
            if _p not in sys.path:
                sys.path.insert(0, _p)
    except Exception:
        pass

