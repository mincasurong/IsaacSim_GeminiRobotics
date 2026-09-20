"""Load Gemini Robotics API configuration from private/.env or environment variables."""
import os
from pathlib import Path


def _safe_parent(path: Path, n: int):
    """Return path.parents[n], or None if n is out of range."""
    parents = path.parents
    return parents[n] if n < len(parents) else None


def load_env(env_path=None):
    """Parse key=value pairs from a .env file.

    Search order:
    1. Explicit env_path argument.
    2. Automatic candidates relative to this file's resolved location,
       guarded against IndexError when the path hierarchy is shallower
       than expected (e.g. running from colcon build/ or install/).
    3. ~/.gemini_robotics/.env
    4. Hard-coded Windows-mount paths common in this project.
    """
    if env_path is None:
        current_file = Path(__file__).resolve()
        # Build candidates safely — skip any that require more parent levels
        # than actually exist in the resolved path.
        raw_candidates = [
            # src layout:  wsl_ws/src/isaac_ros2_control/isaac_ros2_control/gemini_config.py
            #              parents[4] = wsl_ws/
            (_safe_parent(current_file, 4), "private/.env"),
            # build layout: catkin_ws/build/isaac_ros2_control/isaac_ros2_control/gemini_config.py
            #               parents[3] = catkin_ws/
            (_safe_parent(current_file, 3), "private/.env"),
            # install layout: catkin_ws/install/isaac_ros2_control/lib/isaac_ros2_control/gemini_config.py
            #                 parents[4] = catkin_ws/
            (_safe_parent(current_file, 4), "private/.env"),
            # install (site-packages) layout:
            # catkin_ws/install/.../site-packages/isaac_ros2_control/gemini_config.py
            # parents[5] = catkin_ws/
            (_safe_parent(current_file, 5), "private/.env"),
            (_safe_parent(current_file, 6), "private/.env"),
        ]
        candidates = []
        for base, suffix in raw_candidates:
            if base is not None:
                candidates.append(base / suffix)

        # Fallback: walk up from the file until we find private/.env
        p = current_file.parent
        for _ in range(10):
            candidate = p / "private" / ".env"
            if candidate not in candidates:
                candidates.append(candidate)
            if p == p.parent:
                break
            p = p.parent

        # Well-known absolute paths
        candidates += [
            Path.home() / ".gemini_robotics" / ".env",
            Path("/mnt/d/git/IsaacSim_GeminiRobotics/private/.env"),
            Path("/mnt/d/git/IsaacSim_Gemini/private/.env"),
        ]

        for c in candidates:
            if c.exists():
                env_path = c
                break

    config = {}
    if env_path and Path(env_path).exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, _, value = line.partition('=')
                config[key.strip()] = value.strip()

    return config


def get_api_key(env_path=None):
    """Retrieve the Gemini API key from .env file or environment."""
    config = load_env(env_path)
    return config.get('LLM_API_KEY', os.environ.get('GEMINI_API_KEY', ''))


def get_model_name(env_path=None):
    """Get the Gemini Robotics model name."""
    config = load_env(env_path)
    return config.get('ROBOTICS_MODEL', 'gemini-robotics-er-2-preview')


def get_planner_model(env_path=None):
    """Get the planner model name for lightweight planning tasks."""
    config = load_env(env_path)
    return config.get('PLANNER_MODEL', 'gemini-3.7-flash')
