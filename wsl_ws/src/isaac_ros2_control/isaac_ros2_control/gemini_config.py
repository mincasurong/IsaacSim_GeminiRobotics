"""Load Gemini Robotics API configuration from private/.env or environment variables."""
import os
from pathlib import Path


def load_env(env_path=None):
    """Parse key=value pairs from a .env file."""
    if env_path is None:
        current_file = Path(__file__).resolve()
        candidates = [
            Path.home() / ".gemini_robotics" / ".env",
            Path("/mnt/d/git/IsaacSim_GeminiRobotics/private/.env"),
            Path("/mnt/d/git/IsaacSim_Gemini/private/.env"),
        ]
        
        # Traverse upwards to find private/.env
        for parent in current_file.parents:
            env_candidate = parent / "private" / ".env"
            if env_candidate.exists():
                candidates.insert(0, env_candidate)
                break
                
        for c in candidates:
            if c and c.exists():
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
    return config.get('GEMINI_API_KEY') or config.get('LLM_API_KEY', os.environ.get('GEMINI_API_KEY', ''))


def get_model_name(env_path=None):
    """Get the Gemini Robotics model name."""
    config = load_env(env_path)
    return config.get('ROBOTICS_MODEL', 'gemini-robotics-er-2-preview')


def get_planner_model(env_path=None):
    """Get the planner model name for lightweight planning tasks."""
    config = load_env(env_path)
    return config.get('PLANNER_MODEL', 'gemini-3.7-flash')
