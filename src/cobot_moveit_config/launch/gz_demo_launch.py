"""
Configure and launch nodes related to MoveIt2.
List of nodes to be launched:
 * ros_gz_sim (with default world)
 * ros_gz_bridge
 * move_group
 * robot_state_publisher
 * ros2_control_node
 * rviz2
 * controller_manager spawning the controllers

Like most launch-files created for ROS2 and Gazebo,
we use XACRO for the creation of the robot description
(conversion from XACRO to URDF is handled on demand).
"""

import yaml
import xacro
from os import path
from typing import List, IO

from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    DeclareLaunchArgument,
)
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch import LaunchDescription
from ament_index_python.packages import (
    get_package_share_directory,
)
from launch.substitutions import LaunchConfiguration
from launch_ros.substitutions import FindPackageShare
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description() -> LaunchDescription:
    """Creates the launch description for the Moveit2 / Gazebo example."""
    # declare all launch arguments
    declared_arguments = _generate_declared_arguments()

    world = LaunchConfiguration("world")
    rviz_config = LaunchConfiguration("rviz_config")
    use_sim_time = LaunchConfiguration("use_sim_time")
    log_level = LaunchConfiguration("log_level")
    gz_verbosity = LaunchConfiguration("gz_verbosity")

    # define package with configuration
    moveit_config_package = "cobot_moveit_config"

    # add external lauch-files
    launch_descriptions = [
        # include ROS Gazebo launch-file
        # (convenient way to start the gz sim node)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution(
                    [
                        FindPackageShare("ros_gz_sim"),
                        "launch",
                        "gz_sim.launch.py",
                    ]
                )
            ),
            launch_arguments=[("gz_args", [world, " -r -v ", gz_verbosity])],
        ),
    ]

    # get URDF model (from xacro)
    robot_description_as_string = _load_file(
        "cobot_model", path.join("urdf", "festo_cobot_model.urdf.xacro")
    )
    robot_description = {"robot_description": robot_description_as_string}

    # get SRDF model
    robot_description_semantic_srdf = _load_file(
        moveit_config_package, path.join("config", "festo_cobot_model.srdf")
    )
    robot_description_semantic = {
        "robot_description_semantic": robot_description_semantic_srdf
    }
    # get kinematics
    robot_description_kinematics_yaml = _load_file(
        moveit_config_package, path.join("config", "kinematics.yaml")
    )
    robot_description_kinematics = {
        "robot_description_kinematics": robot_description_kinematics_yaml
    }
    # get joint limits
    joint_limits = {
        "robot_description_planning": _load_file(
            moveit_config_package, path.join("config", "joint_limits.yaml")
        )
    }
    # define planning pipeline (loading defaults from OMPL yaml)
    planning_pipeline = {
        "planning_pipelines": ["ompl"],
        "default_planning_pipeline": "ompl",
    }
    planning_pipeline["ompl"] = _load_file(
        moveit_config_package, path.join("config", "ompl_planning_conf.yaml")
    )
    # deine params for planning scene
    planning_scene_monitor_parameters = {
        "publish_planning_scene": True,
        "publish_geometry_updates": True,
        "publish_state_updates": True,
        "publish_transforms_updates": True,
    }

    # load controller definition for the MoveIt controller manager
    moveit_controller_manager_yaml = _load_file(
        moveit_config_package, path.join("config", "moveit_controller_manager.yaml")
    )
    moveit_controller_manager = {
        "moveit_controller_manager": "moveit_simple_controller_manager/MoveItSimpleControllerManager",
        "moveit_simple_controller_manager": moveit_controller_manager_yaml,
    }

    # configure trajectory execution
    trajectory_execution = {
        "allow_trajectory_execution": True,
        "moveit_manage_controllers": False,
        "execution_duration_monitoring": False,
        "trajectory_execution.allowed_execution_duration_scaling": 1.5,
        "trajectory_execution.allowed_goal_duration_margin": 0.5,
        "trajectory_execution.allowed_start_tolerance": 0.01,
    }

    # define list of nodes to be launched
    nodes = [
        # ros_gz_sim_create
        Node(
            package="ros_gz_sim",
            executable="create",
            output="log",
            arguments=[
                "-string",
                robot_description_as_string,
                "--ros-args",
                "--log-level",
                log_level,
            ],
            parameters=[{"use_sim_time": use_sim_time}],
        ),
        # ros_gz_bridge (clock -> ROS 2)
        Node(
            package="ros_gz_bridge",
            executable="parameter_bridge",
            output="log",
            arguments=[
                "/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock",
                "--ros-args",
                "--log-level",
                log_level,
            ],
            parameters=[{"use_sim_time": use_sim_time}],
        ),
        # robot_state_publisher
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            output="log",
            arguments=["--ros-args", "--log-level", log_level],
            parameters=[
                robot_description,
                {
                    "publish_frequency": 100.0,
                    "frame_prefix": "",
                    "use_sim_time": use_sim_time,
                },
            ],
        ),
        # move_group
        Node(
            package="moveit_ros_move_group",
            executable="move_group",
            output="log",
            arguments=["--ros-args", "--log-level", log_level],
            parameters=[
                robot_description,
                robot_description_semantic,
                robot_description_kinematics,
                joint_limits,
                planning_pipeline,
                trajectory_execution,
                planning_scene_monitor_parameters,
                moveit_controller_manager,
                {"use_sim_time": use_sim_time},
            ],
        ),
        # rviz2
        Node(
            package="rviz2",
            executable="rviz2",
            output="log",
            arguments=[
                "--display-config",
                rviz_config,
                "--ros-args",
                "--log-level",
                log_level,
            ],
            parameters=[
                robot_description,
                robot_description_semantic,
                robot_description_kinematics,
                planning_pipeline,
                joint_limits,
                {"use_sim_time": use_sim_time},
            ],
        ),
    ]

    # add nodes for loading controllers
    for controller in moveit_controller_manager_yaml["controller_names"] + [
        "joint_state_broadcaster"
    ]:
        nodes.append(
            Node(
                package="controller_manager",
                executable="spawner",
                output="log",
                arguments=[controller, "--ros-args", "--log-level", log_level],
                parameters=[{"use_sim_time": use_sim_time}],
            ),
        )

    return LaunchDescription(declared_arguments + launch_descriptions + nodes)


def _load_file(package_name: str, file_path: str) -> IO[str]:
    """
    Reads a file and returns its contents.
    Differentiates between xacro, yaml and other files (xml)
    based on their suffix.

    Args:
        package_name (str): the name of the package
        file_path (str): the filepath of the file to be read

    Returns:
        Contents of file
    """

    # create absolute file path
    package_path = get_package_share_directory(package_name)
    absolute_file_path = path.join(package_path, file_path)
    # get file suffix
    file_type = path.splitext(file_path)[1]
    try:
        if file_type == ".xacro":
            # xacro requires processing
            return xacro.process_file(absolute_file_path).toprettyxml()
        # open file
        with open(absolute_file_path, "r") as file:
            if file_type == ".yaml":
                # yaml requires safe load
                return yaml.safe_load(file)
            else:
                # everything else will be returned directly
                return file.read()
    except OSError as e:
        print(
            "\n\nSomething went wrong reading the file "
            + absolute_file_path
            + "\n Error message: "
            + str(e)
            + "\n\n"
        )
        return None


def _generate_declared_arguments() -> List[DeclareLaunchArgument]:
    """
    Generate list of all launch arguments that are declared for this launch script.

    Returns:
        List of launch arguments
    """

    return [
        DeclareLaunchArgument(
            "world",
            default_value="default.sdf",
            description="Name or filepath of world to load.",
        ),
        DeclareLaunchArgument(
            "rviz_config",
            default_value=path.join(
                get_package_share_directory("cobot_moveit_config"),
                "rviz",
                "moveit.rviz",
            ),
            description="Path to configuration for RViz2.",
        ),
        DeclareLaunchArgument(
            "use_sim_time",
            default_value="true",
            description="If true, use simulated clock.",
        ),
        DeclareLaunchArgument(
            "log_level",
            default_value="warn",
            description="The level of logging that is applied to all ROS 2 nodes launched by this script.",
        ),
        DeclareLaunchArgument(
            "gz_verbosity",
            default_value="3",
            description="Verbosity level for Gazebo (0~4).",
        ),
    ]
