"""Load Gemini Robotics API configuration from private/.env or environment variables."""
import os
from pathlib import Path


def load_env(env_path=None):
    """Parse key=value pairs from a .env file."""
    if env_path is None:
        candidates = [
            Path("/mnt/d/git/IsaacSim_Gemini/private/.env"),
            Path.home() / "catkin_ws" / "private" / ".env",
            Path.home() / ".gemini_robotics" / ".env",
        ]
        # Safely scan parent directories dynamically without static index assumption
        cur = Path(__file__).resolve()
        for p in cur.parents:
            c = p / "private" / ".env"
            if c not in candidates:
                candidates.append(c)

        for c in candidates:
            try:
                if c.exists():
                    env_path = c
                    break
            except Exception:
                pass

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
    return config.get('PLANNER_MODEL', 'gemini-3.5-flash-lite')


def get_monitoring_model(env_path=None):
    """Get the model name for monitoring and log summarization tasks."""
    config = load_env(env_path)
    return config.get('MONITORING_MODEL', os.environ.get('MONITORING_MODEL', 'gemini-3.5-flash-lite'))


def get_execution_mode(env_path=None):
    """Get execution mode: 'visual_flow' (deterministic task blocks) or 'vla' (Gemini autonomous)."""
    config = load_env(env_path)
    return config.get('EXECUTION_MODE', os.environ.get('EXECUTION_MODE', 'visual_flow')).lower().strip()
