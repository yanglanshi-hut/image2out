# 群晖图片去重整理工具

这是一个专为群晖NAS设计的图片去重和整理工具，可以将新图片添加到目标文件夹，同时智能去重并保留最佳版本。适合定期整理照片使用。

## 功能特点

- 智能检测重复照片，自动保留文件大小最大的版本
- 支持多种图片格式 (JPG, PNG, GIF, BMP, TIFF, WebP, HEIC等)
- 自动跳过群晖系统目录（@eaDir等），避免处理缩略图
- 保留原始文件名，不进行重命名
- 两种去重模式：
  - 快速模式：仅基于文件哈希比较，速度快
  - 精确模式：同时比较图片内容，可以检测到内容相同但格式不同的图片
- 生成详细日志，方便跟踪处理过程
- 智能文件替换：如果源目录中的图片比目标目录中的同名图片更大，会自动替换

## 安装要求

1. Python 3.6+
2. Pillow库（用于图像处理）

## 安装步骤

1. 在群晖上启用SSH服务
2. 通过SSH连接到群晖
3. 将脚本文件复制到群晖上的目录，例如：`/volume1/photo/scripts/`
4. 安装所需依赖：

```bash
# 安装依赖
sudo pip3 install pillow
```

5. 确保脚本具有执行权限：

```bash
chmod +x image_deduplicator.py
```

## 使用方法

### 基本用法

```bash
# 基本使用方法（单个源目录到单个目标目录）
python3 image_deduplicator.py --source /volume1/photo/test --target /volume1/photo/images

# 多个源目录到同一个目标目录
python3 image_deduplicator.py --source /volume1/photo/test1 /volume1/photo/test2 /volume1/photo/test3 --target /volume1/photo/images

# 多个源目录到对应的多个目标目录（一对一关系）
python3 image_deduplicator.py --source /volume1/photo/test1 /volume1/photo/test2 --target /volume1/photo/images1 /volume1/photo/images2

# 使用快速模式（仅文件哈希比较，速度更快）
python3 image_deduplicator.py --source /volume1/photo/test --target /volume1/photo/images --fast
```

### 参数说明

- `--source` / `-s`: 源图片目录路径（可指定多个，用空格分隔）
- `--target` / `-t`: 目标图片目录路径（可指定多个，用空格分隔。如果指定多个，数量必须与源目录匹配，或者只指定一个目标目录）
- `--fast`: 可选，启用快速模式（仅使用文件哈希，不进行内容比较）

### 工作原理

1. **扫描阶段**: 程序会先扫描目标目录中已有的图片，然后扫描源目录
2. **去重逻辑**: 
   - 如果源目录中的图片与目标目录中的图片同名且更大，会替换目标目录中的图片
   - 如果源目录中的图片是全新的（目标目录中没有同名文件），会直接复制
   - 如果源目录中的图片比目标目录中的同名图片小，会跳过
3. **文件保护**: 自动跳过群晖系统目录（如`@eaDir`），避免处理缩略图文件

### 设置群晖任务计划

1. 打开群晖控制面板
2. 进入"任务计划" > "新增" > "计划的任务" > "用户定义的脚本"
3. 设置任务名称，如"定期图片整理"
4. 设置用户为"admin"或其他有权限的用户
5. 设置计划：选择您希望的执行频率（每天、每周、每月等）
6. 在"任务设置"选项卡的"运行命令"框中输入：

```bash
# 单个源目录的示例
cd /volume1/photo/scripts/ && python3 image_deduplicator.py --source /volume1/photo/test --target /volume1/photo/images --fast

# 多个源目录的示例
cd /volume1/photo/scripts/ && python3 image_deduplicator.py --source /volume1/photo/test1 /volume1/photo/test2 /volume1/photo/test3 --target /volume1/photo/images --fast
```

7. 点击"确定"保存任务

## 日志文件

程序运行时会生成详细的日志文件：

- `image_deduplicator.log`: 记录程序执行的详细信息，包括：
  - 扫描到的图片数量
  - 复制、替换、跳过的文件统计
  - 错误信息和警告
  - 文件操作的详细记录

## 使用示例

假设您有以下目录结构：
```
/volume1/photo/
├── test1/          # 源目录1，包含新下载的图片
├── test2/          # 源目录2，包含手机导入的图片
├── test3/          # 源目录3，包含相机导入的图片
├── images/         # 目标目录，保存整理后的图片
├── backup1/        # 备份目录1
└── backup2/        # 备份目录2
```

**示例1：多个源目录合并到一个目标目录**
```bash
python3 image_deduplicator.py --source /volume1/photo/test1 /volume1/photo/test2 /volume1/photo/test3 --target /volume1/photo/images --fast
```

**示例2：源目录与目标目录一对一处理**
```bash
python3 image_deduplicator.py --source /volume1/photo/test1 /volume1/photo/test2 --target /volume1/photo/backup1 /volume1/photo/backup2 --fast
```

预期输出：
```
2025-06-01 14:54:39,470 - INFO - === 图片去重和整理工具启动 ===
2025-06-01 14:54:39,470 - INFO - 源目录: /volume1/photo/test1, /volume1/photo/test2, /volume1/photo/test3
2025-06-01 14:54:39,470 - INFO - 目标目录: /volume1/photo/images
2025-06-01 14:54:39,470 - INFO - 模式: 快速模式

处理第 1/3 个任务: /volume1/photo/test1 -> /volume1/photo/images
2025-06-01 14:54:39,471 - INFO - 源目录中找到 15 张图片
2025-06-01 14:54:40,883 - INFO - 处理完成! 源目录: 15 张, 复制: 10, 替换: 0, 跳过: 5

处理第 2/3 个任务: /volume1/photo/test2 -> /volume1/photo/images
2025-06-01 14:54:41,471 - INFO - 源目录中找到 8 张图片
2025-06-01 14:54:42,883 - INFO - 处理完成! 源目录: 8 张, 复制: 3, 替换: 1, 跳过: 4

处理第 3/3 个任务: /volume1/photo/test3 -> /volume1/photo/images
2025-06-01 14:54:43,471 - INFO - 源目录中找到 12 张图片
2025-06-01 14:54:44,883 - INFO - 处理完成! 源目录: 12 张, 复制: 5, 替换: 2, 跳过: 5

2025-06-01 14:54:45,470 - INFO - === 图片去重和整理工具完成 ===
2025-06-01 14:54:45,470 - INFO - 总计复制了 18 张新图片
2025-06-01 14:54:45,470 - INFO - 总计跳过了 14 张重复图片
2025-06-01 14:54:45,470 - INFO - 总计删除了 3 张重复文件
```

## 注意事项

1. **权限要求**: 确保对源目录和目标目录都有足够的读写权限
2. **系统目录**: 程序会自动跳过群晖系统目录（如`@eaDir`、`.DS_Store`等），避免处理缩略图和系统文件
3. **文件名冲突**: 如果目标目录中已存在同名文件，程序会比较文件大小：
   - 源文件更大：替换目标文件
   - 源文件更小或相等：跳过源文件
4. **性能考虑**: 
   - 快速模式（`--fast`）：仅比较文件哈希，速度快，适合大批量处理
   - 精确模式（默认）：额外进行图片内容比较，能检测格式转换后的重复图片，但会消耗更多CPU
5. **首次运行**: 如果目标目录中已有大量图片，首次运行时程序需要计算所有已有图片的哈希值，耗时较长属正常现象
6. **备份建议**: 建议在首次运行前备份重要图片，以防意外情况

## 支持的图片格式

- JPEG (.jpg, .jpeg)
- PNG (.png)  
- GIF (.gif)
- BMP (.bmp)
- TIFF (.tiff)
- WebP (.webp)
- HEIC (.heic)
- HEIF (.heif)

## 常见问题

**Q: 为什么显示的图片数量比实际文件数多？**
A: 这通常是因为程序扫描到了系统缓存目录（如`@eaDir`）中的缩略图。更新后的版本已经自动跳过这些目录。

**Q: 程序会删除原始文件吗？**
A: 不会。程序只会从源目录复制文件到目标目录，不会删除源目录中的任何文件。

**Q: 如何确保保留最高质量的图片？**
A: 程序会自动选择文件大小最大的版本，通常文件越大质量越高。如需更精确的质量判断，建议手动检查。