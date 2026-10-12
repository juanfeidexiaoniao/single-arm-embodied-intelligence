  ---
  终端 1：启动 Isaac Sim + 运行位姿发布脚本

  cd /home/user/isaacsim
  ./python.sh

  Isaac Sim 启动后：
  1. 打开场景：File → Open → /home/user/simulation/scene1.usd
  2. 点击 Play（或按空格键）开始仿真
  3. 打开 Script Editor（Window → Script Editor）
  4. 打开文件 /home/user/simulation/scripts/write_poses_to_file.py
  5. 点击 Run 运行脚本（它会持续将橙子和盘子的世界坐标写入
  /tmp/orange_poses.json）

  ---
  终端 2：启动 MoveIt move_group

  cd /home/user/simulation/so_arm_6dof_ws
  source install/setup.bash
  ros2 launch so_arm_config demo.launch.py

  等待看到 MoveGroup move_group node is ready 或类似信息。

  ---
  终端 3：启动位姿中继脚本

  cd /home/user/simulation
  python3 scripts/read_poses_publish.py

  这个脚本读取 /tmp/orange_poses.json，以 10Hz 发布到 ROS2 话题：
  - /orange1_world_pose
  - /orange2_world_pose
  - /plate_world_pose

  ---
  终端 4：运行抓取控制器

  cd /home/user/simulation/so_arm_6dof_ws
  source install/setup.bash
  ros2 run so_arm100_moveit_controller so_arm100_moveit_control

  ---
  执行流程

  控制器启动后会：

  1. 预热 2 秒 — 等待 ROS2 订阅连接建立
  2. 等待位姿 10 秒 — 从终端 3 接收橙子和盘子的动态坐标
  3. 验证位姿有效性 — 若 sqrt(x² + y²) > 1cm 则使用动态位姿，否则回退到默认位置
  4. 回家 → go_home("start")
  5. orange1：approach → open → grasp（x偏移-4cm）→ close → lift → to drop →
  place → open → close → home
  6. orange2：同上流程
  7. 回家 → 完成







    第一步：启动 Isaac Sim 并加载场景

  cd /path/to/isaac-sim
  ./isaac-sim.sh

  启动后在 Isaac Sim 中点击 File → Open，选择：
  /home/user/backup simulatiom/simulation/scene1.usd

  点击 Play 按钮开始仿真。

  ▎ 场景中已包含：7-DOF 机械臂 (so-ARM100)、桌子、盘子、两个橙子 (Orange001)、3
  ▎ 个 RGB 相机。

  ---
  第二步：确保 OmniGraph ROS2 桥接已配置

  在 Isaac Sim 中，确认 Tools → ROS 2 OmniGraphs → Joint States 已激活，包含：
  - /isaac_joint_states（发布者 — 关节状态）
  - /isaac_joint_command（订阅者 — 关节指令）
  - 相机话题 /rgb1、/rgb2、/rgb3
  - 橙子位置话题 /orange1_pose、/orange2_pose

  ---
  第三步：构建 ROS2 工作空间并运行抓取

  打开新终端：

  cd "/home/user/backup_simulation/simulation/so_arm_6dof_ws"
  unset LD_LIBRARY_PATH
  source /opt/ros/humble/setup.bash
  colcon build
  source install/setup.bash
  ros2 run so_arm100_moveit_controller so_arm100_moveit_control

  这个 C++ 控制节点 (so_arm100_moveit_control.cpp) 已经包含了完整的逻辑：
  - 橙子1：移动到抓取位姿 → 张开夹爪 → 下降到橙子 → 闭合夹爪 → 抬起 →
  移动到盘子上方 → 张开夹爪释放
  - 橙子2：重复上述过程
  - 完成后回到起始位姿

  ---
  第四步（可选）：录制数据用于训练

  如果你想录制 ROSBAG 和转换为 LeRobot 数据集，使用 record.py：

  cd ~/so_arm_convert
  chmod +x collect_data/record.py
  ./collect_data/record.py

  这个脚本会：
  1. 自动构建工作空间
  2. 检查所有 ROS2 话题是否正常
  3. 运行机械臂抓取动作的同时录制 rosbag
  4. 验证橙子位置是否有效（x > -0.20）
  5. 完成 2 个有效 episode 后自动停止
  6. 在 episode 之间自动重置场景（通过 /stop_sub 和 /start_sub）

  录制完成后，rosbag 文件保存在 so_arm_convert/rosbags/ 下。

  ---
  第五步（可选）：转换 ROSBAG 为 LeRobot 数据集

  cd ~/so_arm_convert
  export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6
  python3 cvt_rosbag2lerobot.py \
      --raw_dir ~/so_arm_convert/rosbags \
      --task_name pick_place \
      --repo_id lerobot/7dof_arm \
      --root lerobot_data4

