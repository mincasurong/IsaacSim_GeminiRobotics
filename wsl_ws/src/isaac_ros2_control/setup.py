from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'isaac_ros2_control'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*.launch.py'))),
        (os.path.join('share', package_name, 'resource'), glob(os.path.join('resource', '*'))),
        (os.path.join('lib', package_name), [
            'scripts/multi_robot_controller',
            'scripts/conveyor_dual_controller',
            'scripts/gemini_robotics_node',
            'scripts/conveyor_gemini_node',
            'scripts/experiment_runner',
            'scripts/analyze_experiments',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='isaac',
    maintainer_email='isaac@todo.todo',
    description='ROS 2 Multi-Robot Control & Motion Planner Package (Rule-based & Gemini-Robotics)',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'multi_robot_controller = isaac_ros2_control.multi_robot_controller:main',
            'conveyor_dual_controller = isaac_ros2_control.conveyor_dual_controller:main',
            'gemini_robotics_node = isaac_ros2_control.gemini_robotics_node:main',
            'conveyor_gemini_node = isaac_ros2_control.conveyor_gemini_node:main',
            'experiment_runner = isaac_ros2_control.experiment_runner:main',
            'analyze_experiments = isaac_ros2_control.analyze_experiments:main',
        ],
    },
)
