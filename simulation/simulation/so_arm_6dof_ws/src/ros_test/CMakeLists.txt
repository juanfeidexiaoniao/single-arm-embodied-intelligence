cmake_minimum_required(VERSION 3.8)
project(ros_test)
 
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()
 
# 查找依赖项
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(moveit_ros_planning_interface REQUIRED)
 
# 添加可执行文件
add_executable(ros_test_node  src/test.cpp)
ament_target_dependencies(ros_test_node  rclcpp moveit_ros_planning_interface)
 
# 安装可执行文件
install(TARGETS
  ros_test_node 
  DESTINATION lib/${PROJECT_NAME}
)
 
ament_package()
