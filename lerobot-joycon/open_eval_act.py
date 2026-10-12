"""
开环评估脚本 —— 使用 ACT (Action Chunking Transformer) 策略

基于 open_eval.py 原型改写，不使用 LingbotVLA，而是直接使用 LeRobot 内置的
ACTPolicy 和本地数据集/预训练模型。

用法示例:
    python open_eval_act.py \
        --model_path outputs/train/pick_orange/checkpoints/last/pretrained_model \
        --data_path pick_orange \
        --traj_ids 0 1 2 \
        --save_plot_path ./open_loop_eval/

功能:
    1. 按 chunk 方式做开环评估：每 chunk_size 步输入一次观测，获取整段预测动作，
       与对应区间的 ground truth 动作计算 MSE/MAE。
    2. 为每个 trajectory 生成可视化图表，对比 GT action / Pred action / State joints。
"""

import logging
import os
from pathlib import Path
import argparse

import numpy as np
from matplotlib import pyplot as plt
import torch

from lerobot.common.policies.act.modeling_act import ACTPolicy
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset, LeRobotDatasetMetadata


# ---------------------------------------------------------------------------
# 可视化
# ---------------------------------------------------------------------------

def plot_trajectory_results(
    state_joints_across_time: np.ndarray,
    gt_action_across_time: np.ndarray,
    pred_action_across_time: np.ndarray,
    traj_id: int,
    action_names: list[str] | None = None,
    action_horizon: int = 100,
    save_plot_path: str = "traj.png",
) -> None:
    """
    绘制并保存单条 trajectory 的 GT / 预测 / 状态对比图。

    参数:
        state_joints_across_time: (T, D) 状态关节序列
        gt_action_across_time:    (T, D) ground truth 动作序列
        pred_action_across_time:  (T, D) 预测动作序列
        traj_id:                   trajectory 编号
        action_names:              每个动作维度的名称列表（可选）
        action_horizon:            每隔多少步标记一个推理点
        save_plot_path:            图表保存路径
    """
    actual_steps = len(gt_action_across_time)
    action_dim = gt_action_across_time.shape[1]

    # 限定最多绘制 7 个维度（7-DOF 机械臂）
    indices_to_plot = list(range(min(action_dim, 7)))

    if len(indices_to_plot) == 0:
        logging.warning("没有可绘制的动作维度")
        return

    num_plots = len(indices_to_plot)
    fig, axes = plt.subplots(nrows=num_plots, ncols=1, figsize=(10, 3 * num_plots))

    if num_plots == 1:
        axes = [axes]

    fig.suptitle(
        f"Trajectory {traj_id} — Open-Loop Evaluation (ACT)",
        fontsize=16,
        color="blue",
    )

    if action_names is None:
        action_names = [f"joint_{i}" for i in range(action_dim)]

    for plot_idx, action_idx in enumerate(indices_to_plot):
        ax = axes[plot_idx]

        # 仅在状态维度与动作维度相同时绘制状态曲线
        if state_joints_across_time.shape[1] == action_dim:
            ax.plot(
                state_joints_across_time[:, action_idx],
                label="state joints",
                alpha=0.5,
                linewidth=1.5,
            )

        ax.plot(gt_action_across_time[:, action_idx], label="GT action", linewidth=1.5)
        ax.plot(pred_action_across_time[:, action_idx], label="Pred action", linewidth=1.5)

        # 每隔 action_horizon 步画一个推理标记点
        for j in range(0, actual_steps, action_horizon):
            if j == 0:
                ax.plot(
                    j, gt_action_across_time[j, action_idx],
                    "ro", markersize=4, label="inference point"
                )
            else:
                ax.plot(
                    j, gt_action_across_time[j, action_idx],
                    "ro", markersize=4,
                )

        name = action_names[action_idx] if action_idx < len(action_names) else f"dim_{action_idx}"
        ax.set_title(f"{name} (dim {action_idx})")
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)

    plt.tight_layout()

    Path(save_plot_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(save_plot_path, dpi=150)
    plt.close(fig)
    logging.info(f"图表已保存至: {save_plot_path}")


# ---------------------------------------------------------------------------
# 单条 trajectory 评估
# ---------------------------------------------------------------------------

def evaluate_single_trajectory(
    policy: ACTPolicy,
    dataset: LeRobotDataset,
    traj_id: int,
    chunk_size: int = 100,
    save_plot_path: str | None = None,
    max_infer_steps: int = 50,
    device: str = "cuda",
) -> tuple[float, float]:
    """
    对单条 trajectory 进行开环评估。

    每隔 chunk_size 步，输入当前观测到策略，获取 (chunk_size, action_dim) 预测动作，
    与对应区间的 GT 动作对比。

    参数:
        policy:          已加载的 ACTPolicy（eval 模式）
        dataset:         已加载的 LeRobotDataset
        traj_id:         trajectory 编号
        chunk_size:      每次推理的动作块大小
        save_plot_path:  图表保存路径（为 None 则不保存）
        max_infer_steps: 每条 trajectory 最多推理次数
        device:          推理设备

    返回:
        (mse, mae) 元组
    """
    # ---------- 获取 trajectory 的起止索引 ----------
    episodes = dataset.meta.episodes
    if isinstance(episodes, list):
        # v2.0 格式：episodes 是 list[dict]
        ep = episodes[traj_id]
        # 计算累计帧偏移
        start_id = sum(episodes[i]["length"] for i in range(traj_id))
        end_id = start_id + ep["length"]
    elif isinstance(episodes, dict) and "dataset_from_index" in episodes:
        start_id = episodes["dataset_from_index"][traj_id].item()
        end_id = episodes["dataset_to_index"][traj_id].item()
    else:
        # 尝试当作 dict of tensors 处理
        start_id = episodes["from"][traj_id].item()
        end_id = episodes["to"][traj_id].item()

    logging.info(
        f"Trajectory {traj_id}: frames [{start_id}, {end_id}), "
        f"length={end_id - start_id}, chunk_size={chunk_size}"
    )

    gt_action_across_time = []
    state_joints_across_time = []
    pred_action_across_time = []

    count = 0
    for data_id in range(start_id, end_id, chunk_size):
        # 确保不会越界读不到足够的动作数据
        if data_id + chunk_size > end_id:
            break

        # ---- 从数据集中取一帧 ----
        item = dataset[data_id]

        # ---- 构造策略输入 batch ----
        state = item["observation.state"]  # numpy (state_dim,)
        if isinstance(state, torch.Tensor):
            state = state.numpy()

        state_tensor = torch.from_numpy(state).float().unsqueeze(0).to(device)  # (1, state_dim)

        batch = {"observation.state": state_tensor}

        # 图像：dataset 返回 (C, H, W) float [0,1] 或需要转换
        for img_key in policy.expected_image_keys:
            img = item[img_key]
            if isinstance(img, torch.Tensor):
                img = img.numpy()
            # 确保 float32 且值在 [0,1]
            if img.dtype == np.uint8:
                img = img.astype(np.float32) / 255.0
            else:
                img = img.astype(np.float32)

            # 确保是 (C, H, W) 格式
            if img.ndim == 3 and img.shape[-1] == 3:
                # (H, W, C) -> (C, H, W)
                img = np.transpose(img, (2, 0, 1))

            img_tensor = torch.from_numpy(img).float().unsqueeze(0).to(device)
            batch[img_key] = img_tensor

        # ---- 获取 GT 动作 ----
        gt_actions = item["action"]  # numpy (chunk_size, action_dim)
        if isinstance(gt_actions, torch.Tensor):
            gt_actions = gt_actions.numpy()
        gt_actions = gt_actions.astype(np.float32)

        # 确保是 2D
        if gt_actions.ndim == 1:
            gt_actions = gt_actions.reshape(1, -1)

        # ---- 策略推理 ----
        policy.eval()
        with torch.inference_mode():
            # 归一化输入
            batch_norm = policy.normalize_inputs(batch)
            batch_norm = dict(batch_norm)
            # 将多张图像堆叠为 (B, n_cameras, C, H, W)
            if len(policy.expected_image_keys) > 0:
                batch_norm["observation.images"] = torch.stack(
                    [batch_norm[k] for k in policy.expected_image_keys], dim=-4
                )
            # 调用底层模型获取完整动作块
            actions, _ = policy.model(batch_norm)  # (1, chunk_size, action_dim)
            # 只取当前 episode 所需步数
            n_steps = min(policy.config.n_action_steps, gt_actions.shape[0])
            actions = actions[:, :n_steps, :]
            # 反归一化
            actions = policy.unnormalize_outputs({"action": actions})["action"]

        pred_actions = actions[0].cpu().numpy()  # (n_steps, action_dim)
        gt_actions = gt_actions[:n_steps]         # 对齐长度

        # ---- 保存结果 ----
        state_joints = state  # (state_dim,)
        gt_action_across_time.append(gt_actions)
        state_joints_across_time.append(np.tile(state_joints, (n_steps, 1)))
        pred_action_across_time.append(pred_actions)

        count += 1
        if count >= max_infer_steps:
            logging.info(f"达到最大推理次数 {max_infer_steps}，停止")
            break

    # ---------- 拼接 ----------
    if len(gt_action_across_time) == 0:
        logging.warning(f"Trajectory {traj_id} 没有有效数据")
        return float("nan"), float("nan")

    gt_action_across_time = np.concatenate(gt_action_across_time, axis=0)
    state_joints_across_time = np.concatenate(state_joints_across_time, axis=0)
    pred_action_across_time = np.concatenate(pred_action_across_time, axis=0)

    # 最终对齐
    min_len = min(len(gt_action_across_time), len(pred_action_across_time))
    gt_action_across_time = gt_action_across_time[:min_len]
    state_joints_across_time = state_joints_across_time[:min_len]
    pred_action_across_time = pred_action_across_time[:min_len]

    # ---------- 计算指标 ----------
    mse = float(np.mean((gt_action_across_time - pred_action_across_time) ** 2))
    mae = float(np.mean(np.abs(gt_action_across_time - pred_action_across_time)))

    logging.info(f"Traj {traj_id}: MSE={mse:.6f}, MAE={mae:.6f}, steps={min_len}")

    # ---------- 获取动作名称 ----------
    action_names = dataset.meta.features.get("action", {}).get("names", None)

    # ---------- 可视化 ----------
    if save_plot_path is not None:
        plot_trajectory_results(
            state_joints_across_time=state_joints_across_time,
            gt_action_across_time=gt_action_across_time,
            pred_action_across_time=pred_action_across_time,
            traj_id=traj_id,
            action_names=action_names,
            action_horizon=chunk_size,
            save_plot_path=save_plot_path,
        )

    return mse, mae


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main(
    model_path: str,
    data_path: str,
    traj_ids: list[int],
    chunk_size: int = 100,
    max_infer_steps: int = 50,
    save_plot_dir: str = "./open_loop_eval/",
    device: str = "cuda",
) -> None:
    """
    遍历所有指定的 trajectory，汇总开环评估结果。

    参数:
        model_path:      预训练模型目录路径
        data_path:       数据集根目录路径
        traj_ids:        要评估的 trajectory ID 列表
        chunk_size:      动作块大小
        max_infer_steps: 每条 trajectory 最大推理次数
        save_plot_dir:   图表保存目录
        device:          推理设备
    """
    # ---- 设备 ----
    if device == "cuda" and not torch.cuda.is_available():
        logging.warning("CUDA 不可用，回退到 CPU")
        device = "cpu"
    device_obj = torch.device(device)

    # ---- 加载策略 ----
    logging.info(f"加载模型: {model_path}")
    policy = ACTPolicy.from_pretrained(model_path)
    policy.eval()
    policy.to(device_obj)
    logging.info(f"策略已加载，设备: {device_obj}")

    # ---- 加载数据集 ----
    data_root = Path(data_path)
    if not data_root.is_absolute():
        data_root = Path.cwd() / data_root

    # root 直接指向数据集目录本身（例如 pick_orange/）
    repo_id = data_root.name
    root = str(data_root)

    logging.info(f"加载数据集: repo_id={repo_id}, root={root}")

    # 元数据
    dataset_meta = LeRobotDatasetMetadata(repo_id, root=root, local_files_only=True)
    fps = dataset_meta.fps

    # delta_timestamps: 为 action 指定未来 chunk_size 步的时间偏移
    delta_timestamps = {
        "action": [i / fps for i in range(chunk_size)],
    }

    dataset = LeRobotDataset(
        repo_id,
        root=root,
        delta_timestamps=delta_timestamps,
        local_files_only=True,
    )
    logging.info(f"数据集加载完成，共 {len(dataset)} 帧")

    # ---- 验证 trajectory IDs ----
    total_episodes = dataset_meta.total_episodes
    valid_ids = []
    for tid in traj_ids:
        if 0 <= tid < total_episodes:
            valid_ids.append(tid)
        else:
            logging.warning(f"Trajectory ID {tid} 超出范围 [0, {total_episodes})，跳过")
    traj_ids = valid_ids

    if not traj_ids:
        logging.error("没有有效的 trajectory ID")
        return

    # ---- 评估 ----
    os.makedirs(save_plot_dir, exist_ok=True)

    all_mse = []
    all_mae = []

    for traj_id in traj_ids:
        logging.info(f"=== 评估 Trajectory {traj_id} ===")
        save_path = os.path.join(save_plot_dir, f"traj_{traj_id:03d}.png")
        mse, mae = evaluate_single_trajectory(
            policy=policy,
            dataset=dataset,
            traj_id=traj_id,
            chunk_size=chunk_size,
            save_plot_path=save_path,
            max_infer_steps=max_infer_steps,
            device=device,
        )
        if not np.isnan(mse):
            all_mse.append(mse)
            all_mae.append(mae)
            print(f"  Traj {traj_id}: MSE={mse:.6f}, MAE={mae:.6f}")
        else:
            print(f"  Traj {traj_id}: 无有效数据，跳过")

    # ---- 汇总 ----
    print("\n" + "=" * 60)
    if all_mse:
        avg_mse = np.mean(all_mse)
        avg_mae = np.mean(all_mae)
        std_mse = np.std(all_mse)
        std_mae = np.std(all_mae)
        print(f"评估 {len(all_mse)}/{len(traj_ids)} 条 trajectory 完成")
        print(f"Average MSE: {avg_mse:.6f} ± {std_mse:.6f}")
        print(f"Average MAE: {avg_mae:.6f} ± {std_mae:.6f}")
    else:
        print("没有成功评估任何 trajectory")
    print(f"图表保存在: {save_plot_dir}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ACT 开环评估 —— 按 chunk 评估预训练策略并可视化"
    )

    parser.add_argument(
        "--model_path", type=str,
        default="outputs/train/pick_orange/checkpoints/last/pretrained_model",
        help="预训练模型目录路径",
    )
    parser.add_argument(
        "--data_path", type=str,
        default="pick_orange",
        help="数据集根目录路径",
    )
    parser.add_argument(
        "--traj_ids", type=int, nargs="+",
        default=[0],
        help="要评估的 trajectory ID 列表，例如: --traj_ids 0 1 2",
    )
    parser.add_argument(
        "--chunk_size", type=int, default=50,
        help="动作块大小（每次推理预测多少步，配合推理频率使用）",
    )
    parser.add_argument(
        "--max_infer_steps", type=int, default=50,
        help="每条 trajectory 的最大推理次数",
    )
    parser.add_argument(
        "--save_plot_dir", type=str, default="./open_loop_eval/",
        help="图表保存目录",
    )
    parser.add_argument(
        "--device", type=str, default="cuda",
        choices=["cuda", "cpu"],
        help="推理设备",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    main(
        model_path=args.model_path,
        data_path=args.data_path,
        traj_ids=args.traj_ids,
        chunk_size=args.chunk_size,
        max_infer_steps=args.max_infer_steps,
        save_plot_dir=args.save_plot_dir,
        device=args.device,
    )
