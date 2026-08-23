# Contributing to IsaacSim_GeminiRobotics

Thank you for your interest in contributing! 🎉 We welcome contributions from robotics engineers, AI researchers, simulation developers, and hobbyists of all experience levels.

---

## Code of Conduct

Please ensure all interactions remain respectful, constructive, and collaborative. We are committed to providing a welcoming and inclusive environment for everyone.

---

## How to Report Bugs

Found a bug? Please [open a GitHub Issue](https://github.com/mincasurong/IsaacSim_GeminiRobotics/issues) and include:

- **Environment**: OS version, Isaac Sim version, ROS 2 distro, GPU model, NVIDIA driver version
- **Steps to reproduce**: Clear, numbered steps
- **Expected behavior**: What should have happened
- **Actual behavior**: What actually happened (include logs, tracebacks, screenshots)

---

## How to Suggest Features

We love new ideas! Please check existing issues first, then open a new issue with the prefix `[Feature Request]`.

---

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/mincasurong/IsaacSim_GeminiRobotics.git
   cd IsaacSim_GeminiRobotics
   ```

2. **Set up WSL2 & ROS 2**:
   ```bash
   # Inside WSL2 Ubuntu 24.04
   cd /mnt/d/git/IsaacSim_GeminiRobotics/wsl_ws
   chmod +x setup_all.sh
   ./setup_all.sh
   ```

3. **Configure API key**:
   ```bash
   cp .env.example private/.env
   # Edit private/.env with your GEMINI_API_KEY
   ```

4. **Build ROS 2 workspace**:
   ```bash
   # Inside WSL2
   cd ~/catkin_ws
   colcon build --symlink-install
   source install/setup.bash
   ```

5. **Set up Web Dashboard**:
   ```bash
   cd gemini_web_gui
   npm install
   ```

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for detailed instructions.

---

## Code Style

- **Python**: Follow [PEP 8](https://peps.python.org/pep-0008/). Use type annotations where possible.
- **TypeScript / React**: Follow the existing project style. Use functional components with hooks.
- **ROS 2**: Follow standard ROS 2 naming conventions for packages, nodes, and topics.

---

## Testing & Verification

Before opening a pull request, please verify:

```bash
# ROS 2 workspace builds cleanly
cd ~/catkin_ws && colcon build --symlink-install

# Web dashboard builds without errors
cd gemini_web_gui && npm run build
```

---

## Pull Request Process

1. **Fork** the repository
2. **Create a branch**: `git checkout -b feature/my-new-feature`
3. **Commit** with clear messages: `git commit -m "feat: add parallel task scheduling"`
4. **Push** to your fork: `git push origin feature/my-new-feature`
5. **Open a Pull Request** against `main`
6. Fill out the PR description and reference any related issues

---

## Questions?

Feel free to open a [Discussion](https://github.com/mincasurong/IsaacSim_GeminiRobotics/discussions) or reach out via Issues. We're happy to help!
