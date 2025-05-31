# 群晖图片去重整理工具

这是一个专为群晖NAS设计的图片去重和整理工具，可以将新图片添加到目标文件夹，同时避免重复。适合每月定期整理照片使用。

## 功能特点

- 自动检测并跳过重复照片
- 支持多种图片格式 (JPG, PNG, GIF, BMP, TIFF, WebP, HEIC等)
- 两种去重模式：
  - 快速模式：仅基于文件哈希比较，速度快
  - 精确模式：同时比较图片内容，可以检测到内容相同但格式不同的图片
- 生成详细日志，方便跟踪处理过程
- 可配置源目录和目标目录
- 支持通过群晖任务计划定期执行

## 安装要求

1. Python 3.6+
2. Pillow库（用于图像处理）

## 安装步骤

1. 在群晖上启用SSH服务
2. 通过SSH连接到群晖
3. 将这些脚本文件复制到群晖上的目录，例如：`/volume1/homes/admin/scripts/image_deduplicator/`
4. 安装所需依赖：

```bash
# 进入脚本目录
cd /volume1/homes/admin/scripts/image_deduplicator/

# 安装依赖
pip3 install pillow
```

5. 确保脚本具有执行权限：

```bash
chmod +x image_deduplicator.py
chmod +x run_deduplication.py
```

## 配置说明

编辑`config.json`文件设置源目录和目标目录：

```json
{
    "source_directory": "/volume1/photo/new_photos",
    "target_directory": "/volume1/photo/all_photos",
    "use_content_hash": true
}
```

- `source_directory`: 包含新照片的目录
- `target_directory`: 保存所有不重复照片的目录
- `use_content_hash`: 是否使用内容哈希进行更精确的去重

## 使用方法

### 手动运行

```bash
# 使用配置文件中的设置运行
python3 run_deduplication.py

# 或者直接指定参数运行
python3 image_deduplicator.py --source /volume1/photo/new_photos --target /volume1/photo/all_photos
```

### 使用快速模式（仅文件哈希）

```bash
python3 image_deduplicator.py --source /volume1/photo/new_photos --target /volume1/photo/all_photos --fast
```

### 设置群晖任务计划

1. 打开群晖控制面板
2. 进入"任务计划" > "新增" > "计划的任务" > "用户定义的脚本"
3. 设置任务名称，如"每月图片整理"
4. 设置用户为"admin"或其他有权限的用户
5. 设置计划：选择"每月"，并选择您希望执行的日期
6. 在"任务设置"选项卡的"运行命令"框中输入：

```bash
cd /volume1/homes/admin/scripts/image_deduplicator/ && python3 run_deduplication.py
```

7. 点击"确定"保存任务

## 日志文件

- `image_deduplicator.log`: 记录主程序执行的详细信息
- `auto_run.log`: 记录自动运行脚本的执行情况

## 注意事项

1. 第一次运行时，如果目标目录中已有大量图片，程序需要先计算所有已有图片的哈希值，可能会比较耗时
2. 内容哈希比较会消耗更多CPU资源，但能提供更精确的去重结果
3. 确保源目录和目标目录都有足够的读写权限 