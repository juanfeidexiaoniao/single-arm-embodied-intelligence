import csv
csv_file = "jinengku.csv"  # 替换成你的文件路径

# 2. 创建空字典用于存储结果
result_dict = {}

# 3. 读取并生成字典
with open(csv_file, mode='r', encoding='utf-8') as file:
    # 读取每一行（不把第一行当作表头，直接读取）
    csv_reader = csv.reader(file)
    n = True
    
    for row in csv_reader:
        # 确保每行至少有两列，避免报错
        if len(row) >= 2:
            if n:
                key = row[0][1:]
                n = False
            else:
                key = row[0]       # 第一列 = 键
            value = row[1]     # 第二列 = 值
            result_dict[key] = value
del n
print(result_dict)