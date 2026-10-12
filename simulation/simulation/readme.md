
-----

# Isaac Sim 4.5.0 & ROS2 Humble 机械臂控制教程

## 📺 参考资源

  * **YouTube:** [观看视频](https://www.youtube.com/watch?v=Ym5jav5scfA)
  * **Bilibili:** [观看视频](https://www.google.com/search?q=https://www.bilibili.com/video/BV1MzhuziEPk/)

-----

## 1\. 快速启动仿真环境

如果你已经拥有配置好的环境，可以使用以下命令快速启动：

### 1.1 开启 Isaac Sim

1.  进入仿真环境目录并启动：
    ```bash
    ./isaac-sim.sh
    ```
2.  点击左上角 **File -\> Open**，选择对应的 `.usd` 文件加载场景。

### 1.2 启动 ROS2 控制节点

在新的终端中运行：

```bash
cd /home/user/so_arm_6dof_ws
colcon build
source install/setup.bash
ros2 run so_arm100_moveit_controller so_arm100_moveit_control
```

-----

## 2\. ROS2 & MoveIt 配置过程

### 2.1 环境准备与依赖安装

首先，刷新 ROS2 环境并创建工作空间：

```bash
source /opt/ros/humble/setup.bash

mkdir -p ~/so-arm_moveit_isaacsim_ws/src
cd ~/so-arm_moveit_isaacsim_ws/src

# 安装必要的 ROS2 依赖
sudo apt update
sudo apt install \
   ros-humble-moveit \
   ros-humble-ros2-controllers \
   ros-humble-ros2-control \
   ros-humble-gripper-controllers \
   ros-humble-topic-based-ros2-control
```

### 2.2 创建功能包

创建配置和描述文件存放目录，并将你的 **URDF 文件** 准备好：

```bash
mkdir -p so_arm_moveit_config
mkdir -p so_arm_description
```

### 2.3 使用 MoveIt Setup Assistant

1.  **初步编译：**
    ```bash
    cd ~/so-arm_moveit_isaacsim_ws
    colcon build
    source ~/so-arm_moveit_isaacsim_ws/install/setup.bash
    ```
2.  **启动助手：**
    ```bash
    ros2 launch moveit_setup_assistant setup_assistant.launch.py
    ```
3.  **配置要点：** 划分 Link 与 Joint、设置末端执行器、选择运动学解算器等。

### 2.4 关键错误修复

配置完成后，需手动修改以下文件中的错误：

  * **`joint_limits.yaml`**：将所有整数值（如 `1`）改为浮点数（如 `1.0`）。
  * **`moveit_control.yaml`**：添加以下内容：
    ```yaml
    action_ns: follow_joint_trajectory
    default: true
    ```

最后重新执行 `colcon build`。

-----

## 3\. Isaac Sim 设置与联调

### 3.1 导入机械臂

1.  **导入 URDF**：点击 **File -\> Import** 选择机械臂 URDF。
2.  **修正 Articulation Root**：
      * 删除 Root Joint 下默认的 `Articulation root`。
      * 选中 `base` 链接，手动添加 `Articulation root` 将其设为底座。

### 3.2 配置 ROS2 OmniGraph

1.  选择 **Tools -\> ROS 2 OmniGraphs -\> Joint States**。
2.  添加 `/isaac_joint_states` (发布者) 与 `/isaac_joint_command` (订阅者)。
      * *注：若没有此选项，可在 `Create -> Graphs -> Action Graph` 中手动创建。*

### 3.3 修改控制插件 (Xacro)

修改 `src/so_arm_config/config/so_arm.ros2_control.xacro`，将硬件接口替换为基于话题的通信方式：

```xml
<ros2_control name="${name}" type="system">
    <hardware>
        <plugin>topic_based_ros2_control/TopicBasedSystem</plugin>
        <param name="joint_states_topic">/isaac_joint_states</param>
        <param name="joint_commands_topic">/isaac_joint_command</param>
    </hardware>
</ros2_control>
```

-----

## 4\. 场景搭建与高级功能

  * **资产导入**：可以使用 Isaac Sim 现成资产，注意物体间物理配合的合理性。
  * **话题发布 (OmniGraph)**：关于Isaac Sim图编程OmniGraph可参考[中文教程](https://developer.aliyun.com/article/1592535)和[各种节点定义](https://docs.omniverse.nvidia.com/extensions/latest/ext_omnigraph/node-library/node-library.html)以及[官方教程](https://docs.isaacsim.omniverse.nvidia.com/latest/omnigraph/omnigraph_tutorial.html)
      * 可发布 **待抓取物位置信息**。
      
      * 可发布 **相机 RGB 与深度 (Depth) 图像**。
      * 可设置 **场景开始与重置开关**。这里需要提醒，omnigraph里面的nodes只有start和stop两种，并没有重置到timeine起点的restart功能，这里可以自己编辑并导入自定义node
      

完成上述步骤后，即可通过 `ros2 launch so_arm_moveit_config demo.launch.py` 在 RViz 中控制 Isaac Sim 里的机械臂运行。
