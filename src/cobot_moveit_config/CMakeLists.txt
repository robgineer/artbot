cmake_minimum_required(VERSION 3.22)
project(cobot_moveit_config)

find_package(ament_cmake REQUIRED)

ament_package()

if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/launch")
  install(
    DIRECTORY launch config rviz
    DESTINATION share/${PROJECT_NAME}
  )
endif()

install(DIRECTORY config DESTINATION share/${PROJECT_NAME})
