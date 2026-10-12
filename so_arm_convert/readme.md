# Record ROSBAG

To record ROSBAG, run the following command:

```bash
cd ~/kuavo-il-opensource/so_arm_convert
chmod +x collect_data/record.py
./collect_data/record.py
```
You can change theduration of the recording by modifying the `duration` parameter in the `record.py` file.
Remember to press `Ctrl+C` to stop the recording, Or the rosbag will continue to record until the time reaches the limit,and that will make the rosbag lack of yaml file


# Convert ROSBAG to Lerobot Dataset

To convert ROSBAG to Lerobot Dataset, run the following command:

```bash
cd ~/kuavo-il-opensource

export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6

python3 so_arm_convert/cvt_rosbag2lerobot.py   --raw_dir ~/kuavo-il-opensource/so_arm_convert/rosbags   --task_name pick_place   --repo_id lerobot/7dof_arm   --root so_arm_convert//lerobot_data
```



# Visualize Dataset

To visualize the dataset, run the following command:

```bash
python lerobot/lerobot/scripts/visualize_dataset.py --repo-id lerobot/7dof_arm --root so_arm_convert/lerobot_data  --episode 0 --local-files-only 1
```