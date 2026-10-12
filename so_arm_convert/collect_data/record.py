#!/usr/bin/env python3
import time
import subprocess
import os
from pathlib import Path
import signal
import atexit
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Transform
from std_msgs.msg import Int32

# ================== 配置 ==================
WORKSPACE = str(Path.home() / "backup_simulation/simulation/so_arm_6dof_ws")
BAG_ROOT = Path("./rosbags")

TOPIC_LIST = [
    "/isaac_joint_states",
    "/isaac_joint_command",
    "/rgb1",
    "/rgb2",
    "/rgb3",
    "/orange1_pose",
    "/orange2_pose"
]

EPISODE_COUNT = 2
WAIT_BETWEEN = 3
ORANGE_X_LIMIT = 0.15
RESET_DELAY = 2.0  # 场景 stop->start 延迟

# =========================================

bag_proc = None
reset_node = None
stop_pub = None
start_pub = None

# ================= ROS2 节点 & 场景重置 =================
def create_reset_publishers():
    global reset_node, stop_pub, start_pub
    reset_node = rclpy.create_node('reset_node')
    stop_pub = reset_node.create_publisher(Int32, '/stop_sub', 10)
    start_pub = reset_node.create_publisher(Int32, '/start_sub', 10)

def reset_scene(delay=RESET_DELAY):
    # 发布 stop
    msg = Int32()
    msg.data = 0
    stop_pub.publish(msg)
    reset_node.get_logger().info("[RESET] Published stop message")
    time.sleep(delay)

    # 发布 start
    msg.data = 1
    start_pub.publish(msg)
    reset_node.get_logger().info("[RESET] Published start message")
    time.sleep(delay)

# ================= 工作空间构建 =================
def setup_workspace():
    print(f"[INFO] Building workspace: {WORKSPACE}")
    cmd = f"""
    cd {WORKSPACE}
    colcon build
    source install/setup.bash
    """
    subprocess.run(["bash", "-c", cmd], check=True)
    print("[✅] Workspace built & sourced")

# ================= ROS话题检查 =================
def check_topics():
    print("[INFO] Checking ROS topics...")
    try:
        active = subprocess.check_output(
            ["ros2", "topic", "list"], encoding="utf-8"
        ).splitlines()
        missing = [t for t in TOPIC_LIST if t not in active]
        if missing:
            print("[⚠️] Missing topics:")
            for t in missing: print(f"  - {t}")
            input("[⚠️] Press Enter to continue anyway…")
        else:
            print("[✅] All topics active")
    except Exception as e:
        print(f"[❌] Topic check failed: {e}")

# ================= 橙子位姿订阅 =================
class OrangePoseSubscriber(Node):
    def __init__(self, topic):
        super().__init__('orange_pose_subscriber')
        self.x = None
        self.topic = topic
        self.sub = self.create_subscription(
            Transform,
            topic,
            self.callback,
            10
        )

    def callback(self, msg):
        self.x = msg.translation.x
        self.get_logger().info(f"Received {self.topic}: {msg}")

def get_orange_x(topic, timeout_sec=3.0):
    subscriber = OrangePoseSubscriber(topic)
    start_time = subscriber.get_clock().now()

    while rclpy.ok() and subscriber.x is None and \
            (subscriber.get_clock().now() - start_time).nanoseconds / 1e9 < timeout_sec:
        rclpy.spin_once(subscriber, timeout_sec=0.1)

    x_value = subscriber.x
    subscriber.destroy_node()
    return x_value

def check_oranges_ok():
    x1 = get_orange_x("/orange1_pose")
    x2 = get_orange_x("/orange2_pose")

    print(f"[INFO] orange1.x={x1}, orange2.x={x2}")

    if x1 is None or x2 is None:
        print("[⚠️] Missing orange pose -> discard episode")
        return False

    if x1 < ORANGE_X_LIMIT or x2 < ORANGE_X_LIMIT:
        print("[❌] One of the oranges x < threshold -> discard\n")
        return False

    print("[✅] Both oranges valid -> keep bag\n")
    return True

# ================= 清理临时 bag =================
def clean_bag_temp(folder: Path):
    print(f"[CLEAN] Force deleting temp bag: {folder}")
    try:
        if folder.exists():
            for p in folder.rglob("*"):
                try: p.unlink()
                except: pass
            subprocess.run(["rm", "-rf", str(folder)], check=False)
        print("[CLEAN ✅] Removed permanently\n")
    except Exception as e:
        print(f"[CLEAN ⚠️] Cleanup error: {e}")

# ================= 录制机械臂动作 & Bag =================
def run_motion_and_record(valid_idx: int, bag_root: Path):
    global bag_proc

    episode_folder = bag_root / f"episode{valid_idx}_tmp"
    episode_folder.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Recording into {episode_folder}")
    bag_proc = subprocess.Popen(
        ["ros2", "bag", "record", "-o", "data"] + TOPIC_LIST,
        cwd=episode_folder,
        preexec_fn=os.setsid
    )

    try:
        print("[INFO] Running robot motion...")
        cmd = f"source {WORKSPACE}/install/setup.bash && ros2 run so_arm100_moveit_controller so_arm100_moveit_control"
        subprocess.run(["bash", "-c", cmd], check=True)
        print("[✅] Motion finished, stopping bag...")
    except subprocess.CalledProcessError:
        print("[❌] Motion command failed")

    os.killpg(os.getpgid(bag_proc.pid), signal.SIGINT)
    bag_proc.wait()

    data_dir = episode_folder / "data"
    db3_list = list(data_dir.glob("*.db3"))

    if not db3_list:
        print("[❌] No db3 file!")
        clean_bag_temp(episode_folder)
        return False

    # 不再通过橙子位姿判断数据集是否有效，只判断是否成功输出 .db3 文件
    # if not check_oranges_ok():
    #     clean_bag_temp(episode_folder)
    #     return False

    db3_file = db3_list[0]
    new_db3_path = bag_root / f"episode{valid_idx}.db3"
    db3_file.rename(new_db3_path)

    yaml_file = list(data_dir.glob("*.yaml"))
    if yaml_file and valid_idx == 0:
        yaml_file[0].rename(bag_root / "metadata.yaml")

    clean_bag_temp(episode_folder)
    print(f"[✅] Saved episode {valid_idx} -> {new_db3_path}")
    return True

# ================= 清理 =================
def cleanup():
    global bag_proc
    print("\n[EXIT] Cleaning up...")
    if bag_proc:
        try:
            print("[EXIT] Killing ros2 bag process...")
            os.killpg(os.getpgid(bag_proc.pid), signal.SIGINT)
        except Exception:
            pass
    if reset_node:
        reset_node.destroy_node()
    print("[EXIT] Done.")

atexit.register(cleanup)

def sigint_handler(sig, frame):
    print("\n[CTRL+C detected] Stopping...")
    cleanup()
    rclpy.shutdown()
    exit(0)

signal.signal(signal.SIGINT, sigint_handler)

# ================= 获取下一个可用索引 =================
def get_next_index(bag_root: Path) -> int:
    """扫描 bag_root 下已有的 episode*.db3，返回下一个可用索引"""
    existing = list(bag_root.glob("episode*.db3"))
    if not existing:
        return 0
    max_idx = -1
    for f in existing:
        try:
            idx = int(f.stem.replace("episode", ""))
            if idx > max_idx:
                max_idx = idx
        except ValueError:
            continue
    return max_idx + 1

# ================= 主程序 =================
def main():
    rclpy.init()  # 只初始化一次 ROS2
    setup_workspace()
    check_topics()
    BAG_ROOT.mkdir(parents=True, exist_ok=True)

    # 初始化 stop/start 发布器
    create_reset_publishers()

    start_idx = get_next_index(BAG_ROOT)
    print(f"[INFO] Existing bags found, starting from episode {start_idx}")

    valid_count = 0
    attempts = 0

    while valid_count < EPISODE_COUNT:
        current_idx = start_idx + valid_count
        print(f"\n===== Attempt {attempts}, Valid {valid_count}/{EPISODE_COUNT} (saving as episode{current_idx}) =====")
        ok = run_motion_and_record(current_idx, BAG_ROOT)

        if ok:
            valid_count += 1

        attempts += 1
        if valid_count < EPISODE_COUNT:
            print(f"[INFO] Waiting {WAIT_BETWEEN}s before next...")

            # 自动重置场景
            reset_scene()

            time.sleep(WAIT_BETWEEN)

    print("\n🎉 Finished! Valid bags collected.")
    print(f"[INFO] Bags in folder:")
    for f in sorted(BAG_ROOT.iterdir()):
        print(f"  - {f.name}")

    cleanup()
    rclpy.shutdown()

if __name__ == "__main__":
    main()
