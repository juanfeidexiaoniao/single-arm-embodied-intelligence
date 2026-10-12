#include <rclcpp/rclcpp.hpp>
#include <moveit/move_group_interface/move_group_interface.h>
#include <moveit/planning_scene_interface/planning_scene_interface.h>
#include <moveit_msgs/msg/display_trajectory.hpp>

#include <tf2/LinearMath/Quaternion.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>

#include <cmath>
#include <vector>

double degreesToRadians(double degrees) {
    return degrees * M_PI / 180.0;
}

bool pick_and_place(
    rclcpp::Node::SharedPtr node,
    const geometry_msgs::msg::Pose& first_pose,
    const geometry_msgs::msg::Pose& second_pose)
{
    moveit::planning_interface::MoveGroupInterface move_group_arm(node, "arm");
    moveit::planning_interface::MoveGroupInterface move_group_gripper(node, "gripper");

    // 设置规划参数
    move_group_arm.setMaxVelocityScalingFactor(0.3);
    move_group_arm.setMaxAccelerationScalingFactor(0.2);
    move_group_arm.setPlanningTime(10.0);
    move_group_arm.setNumPlanningAttempts(5);

    auto move_to_pose = [&](const geometry_msgs::msg::Pose& pose, const std::string& desc) -> bool {
        move_group_arm.setPoseTarget(pose);
        moveit::planning_interface::MoveGroupInterface::Plan plan;
        bool success = (move_group_arm.plan(plan) == moveit::core::MoveItErrorCode::SUCCESS);
        if (success) {
            move_group_arm.execute(plan);
            RCLCPP_INFO(node->get_logger(), "Moved to %s", desc.c_str());
        } else {
            RCLCPP_ERROR(node->get_logger(), "Failed to plan to %s", desc.c_str());
        }
        return success;
    };

    auto control_gripper = [&](const std::string& target) -> bool {
        move_group_gripper.setNamedTarget(target);
        moveit::planning_interface::MoveGroupInterface::Plan plan;
        bool success = (move_group_gripper.plan(plan) == moveit::core::MoveItErrorCode::SUCCESS);
        if (success) {
            move_group_gripper.execute(plan);
            RCLCPP_INFO(node->get_logger(), "Gripper %s successfully", target.c_str());
        } else {
            RCLCPP_ERROR(node->get_logger(), "Failed to %s gripper", target.c_str());
        }
        return success;
    };

    // 1. 移动到第一个位姿
    if (!move_to_pose(first_pose, "first target pose")) return false;

    // 2. 打开夹爪
    if (!control_gripper("open")) return false;

    // 3. 移动到第二个位姿
    if (!move_to_pose(second_pose, "second target pose")) return false;

    // 4. 移动夹爪关节 (示例 joint7)
    std::string joint_name = "joint7";
    double target_angle_rad = degreesToRadians(-35.0);
    move_group_gripper.setJointValueTarget(joint_name, target_angle_rad);
    moveit::planning_interface::MoveGroupInterface::Plan joint_plan;
    if (move_group_gripper.plan(joint_plan) == moveit::core::MoveItErrorCode::SUCCESS) {
        move_group_gripper.execute(joint_plan);
        RCLCPP_INFO(node->get_logger(), "Joint moved successfully");
    } else {
        RCLCPP_ERROR(node->get_logger(), "Failed to move joint");
        return false;
    }

    // 6. 移动关节1-6到固定角度
    {
        std::vector<double> arm_joint_values = {
            degreesToRadians(18.0),
            degreesToRadians(35.0),
            degreesToRadians(13.0),
            degreesToRadians(-83.0),
            degreesToRadians(4.0),
            degreesToRadians(-10.0)
        };
        move_group_arm.setJointValueTarget(arm_joint_values);
        moveit::planning_interface::MoveGroupInterface::Plan arm_joint_plan;
        if (move_group_arm.plan(arm_joint_plan) == moveit::core::MoveItErrorCode::SUCCESS) {
            move_group_arm.execute(arm_joint_plan);
            RCLCPP_INFO(node->get_logger(), "Arm joints 1-6 moved successfully");
        } else {
            RCLCPP_ERROR(node->get_logger(), "Failed to move arm joints 1-6");
            return false;
        }
    }

    // 5. 移动关节1-6到固定角度
    {
        std::vector<double> arm_joint_values = {
            degreesToRadians(44.0),
            degreesToRadians(-5.0),
            degreesToRadians(24.0),
            degreesToRadians(-47.0),
            degreesToRadians(2.0),
            degreesToRadians(-27.0)
        };
        move_group_arm.setJointValueTarget(arm_joint_values);
        moveit::planning_interface::MoveGroupInterface::Plan arm_joint_plan;
        if (move_group_arm.plan(arm_joint_plan) == moveit::core::MoveItErrorCode::SUCCESS) {
            move_group_arm.execute(arm_joint_plan);
            RCLCPP_INFO(node->get_logger(), "Arm joints 1-6 moved successfully");
        } else {
            RCLCPP_ERROR(node->get_logger(), "Failed to move arm joints 1-6");
            return false;
        }
    }

    // 5.5 打开joint7
    {
        double open_angle_rad = degreesToRadians(-100.0);
        move_group_gripper.setJointValueTarget("joint7", open_angle_rad);
        moveit::planning_interface::MoveGroupInterface::Plan open_plan;
        if (move_group_gripper.plan(open_plan) == moveit::core::MoveItErrorCode::SUCCESS) {
            move_group_gripper.execute(open_plan);
            RCLCPP_INFO(node->get_logger(), "Joint7 opened successfully");
        } else {
            RCLCPP_ERROR(node->get_logger(), "Failed to open joint7");
        }
        // rclcpp::sleep_for(std::chrono::seconds(2));
    }

    // // 6. 移动到第三、第四固定位姿
    // geometry_msgs::msg::Pose third_pose;
    // third_pose.orientation.x = -0.3135;
    // third_pose.orientation.y = -0.0564;
    // third_pose.orientation.z = -0.0836;
    // third_pose.orientation.w = -0.9442;
    // third_pose.position.x = 0.0321;
    // third_pose.position.y = -0.2243;
    // third_pose.position.z = 0.2039;
    // if (!move_to_pose(third_pose, "third target pose")) return false;

    // geometry_msgs::msg::Pose fourth_pose;
    // fourth_pose.orientation.x = -0.2373;
    // fourth_pose.orientation.y = -0.5291;
    // fourth_pose.orientation.z = 0.1236;
    // fourth_pose.orientation.w = -0.8053;
    // fourth_pose.position.x = -0.2177;
    // fourth_pose.position.y = -0.2095;
    // fourth_pose.position.z = 0.1547;
    // if (!move_to_pose(fourth_pose, "fourth target pose")) return false;

    // if (!control_gripper("open")) return false;

    // 6. 关闭夹爪
    if (!control_gripper("close")) return false;

    return true; // 不再回到起点
}

int main(int argc, char** argv)
{
    rclcpp::init(argc, argv);
    auto node = rclcpp::Node::make_shared("so_arm100_moveit_control");

    // 定义三组橙子的抓放位姿
    struct PosePair {
        geometry_msgs::msg::Pose pick_pose;
        geometry_msgs::msg::Pose place_pose;
    };

    std::vector<PosePair> orange_poses(1);

    //橙子1
    orange_poses[0].pick_pose.orientation.x = 0.40764;
    orange_poses[0].pick_pose.orientation.y = -0.06857;
    orange_poses[0].pick_pose.orientation.z = -0.22093;
    orange_poses[0].pick_pose.orientation.w = 0.88336;
    orange_poses[0].pick_pose.position.x = -0.06153;
    orange_poses[0].pick_pose.position.y = -0.08889;
    orange_poses[0].pick_pose.position.z = 0.21153;

    orange_poses[0].place_pose.orientation.x = 0.40764;
    orange_poses[0].place_pose.orientation.y = -0.06857;
    orange_poses[0].place_pose.orientation.z = -0.22093;
    orange_poses[0].place_pose.orientation.w = 0.88336;
    orange_poses[0].place_pose.position.x = -0.06153;
    orange_poses[0].place_pose.position.y = -0.08889;
    orange_poses[0].place_pose.position.z = 0.1100;

    // // 橙子3
    // orange_poses[0].pick_pose.orientation.x = -0.4238;
    // orange_poses[0].pick_pose.orientation.y = -0.5229;
    // orange_poses[0].pick_pose.orientation.z = -0.2682;
    // orange_poses[0].pick_pose.orientation.w = -0.6892;
    // orange_poses[0].pick_pose.position.x = -0.0548;
    // orange_poses[0].pick_pose.position.y = -0.1268;
    // orange_poses[0].pick_pose.position.z = 0.1841;

    // orange_poses[0].place_pose.orientation.x = -0.4667;
    // orange_poses[0].place_pose.orientation.y = -0.4851;
    // orange_poses[0].place_pose.orientation.z = -0.3259;
    // orange_poses[0].place_pose.orientation.w = -0.6638;
    // orange_poses[0].place_pose.position.x = -0.0563;
    // orange_poses[0].place_pose.position.y = -0.2035;
    // orange_poses[0].place_pose.position.z = 0.1133;

    // // 橙子2
    // orange_poses[0].pick_pose.orientation.x = -0.5539;
    // orange_poses[0].pick_pose.orientation.y = 0.0058;
    // orange_poses[0].pick_pose.orientation.z = 0.0896;
    // orange_poses[0].pick_pose.orientation.w = -0.8278;
    // orange_poses[0].pick_pose.position.x = -0.0613;
    // orange_poses[0].pick_pose.position.y = -0.1661;
    // orange_poses[0].pick_pose.position.z = 0.1880;

    // orange_poses[0].place_pose.orientation.x = -0.5806;
    // orange_poses[0].place_pose.orientation.y = 0.0013;
    // orange_poses[0].place_pose.orientation.z = 0.0784;
    // orange_poses[0].place_pose.orientation.w = -0.8104;
    // orange_poses[0].place_pose.position.x = -0.0206;
    // orange_poses[0].place_pose.position.y = -0.1467;
    // orange_poses[0].place_pose.position.z = 0.1153;

    // 循环抓放所有橙子
    for (size_t i = 0; i < orange_poses.size(); ++i) {
        if (!pick_and_place(node, orange_poses[i].pick_pose, orange_poses[i].place_pose)) {
            RCLCPP_ERROR(node->get_logger(), "Pick and place operation failed for orange %zu", i+1);
        }
    }

    // 所有橙子抓放完成后回到起点
    moveit::planning_interface::MoveGroupInterface move_group_arm(node, "arm");
    move_group_arm.setNamedTarget("start");
    moveit::planning_interface::MoveGroupInterface::Plan arm_plan;
    if (move_group_arm.plan(arm_plan) == moveit::core::MoveItErrorCode::SUCCESS) {
        move_group_arm.execute(arm_plan);
        RCLCPP_INFO(node->get_logger(), "Returned to start position after all operations");
    } else {
        RCLCPP_ERROR(node->get_logger(), "Failed to return to start position");
    }

    rclcpp::shutdown();
    return 0;
}
