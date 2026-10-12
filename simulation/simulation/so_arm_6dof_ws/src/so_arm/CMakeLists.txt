
cmake_minimum_required(VERSION 3.10.2) 

project(so_arm)

find_package(ament_cmake REQUIRED)
find_package(urdf REQUIRED)

install(
  DIRECTORY config launch meshes urdf
  DESTINATION share/${PROJECT_NAME}
  OPTIONAL
)

ament_package()
