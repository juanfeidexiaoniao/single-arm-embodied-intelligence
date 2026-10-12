import os
os.system(r'python lerobot/scripts/control_robot.py record \
 --robot-path lerobot/configs/robot/6DOF_ARM.yaml \
 --fps 60 \
 --tags so100 tutorial eval \
 --warmup-time-s 2 \
--episode-time-s 100 \
--reset-time-s 5 \
--num-episodes 2 \
--push-to-hub 0 \
--local-files-only 1 \
--root 6dof_arm_data\
--repo-id ${HF_USER}/eval_6dof_arm \
--single-task experiment \
-p outputs/train/act_so100_test_2/checkpoints/last/pretrained_model ')