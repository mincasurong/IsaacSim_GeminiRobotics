"""Backward compatibility wrapper aliasing FrankaDualController to MultiRobotController."""

from .multi_robot_controller import MultiRobotController, main

FrankaDualController = MultiRobotController

if __name__ == '__main__':
    main()
