# 媒体文件去重整理工具

一个功能强大的媒体文件去重和整理工具，专为群晖NAS和其他存储系统设计。支持图片、视频和压缩文件的智能去重，自动分类保存，保留最佳版本。

[![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ 主要特性

### 🎯 智能去重
- **多重去重算法**: 支持文件哈希和图片内容哈希双重检测
- **保留最佳版本**: 自动选择文件大小最大的版本（通常质量更高）
- **跨格式检测**: 精确模式可检测内容相同但格式不同的图片

### 📁 文件类型支持
- **图片文件**: JPG, JPEG, PNG, GIF, BMP, TIFF, WebP, HEIC, HEIF
- **视频文件**: MP4, AVI, MOV, MKV, WMV, FLV, WebM, M4V, 3GP, MPG, MPEG
- **压缩文件**: ZIP, RAR, 7Z, TAR, GZ, BZ2, XZ及其组合格式

### 🏗️ 自动分类存储
- **图片文件**: 保存在主目录
- **视频文件**: 自动保存在 `mp4/` 子目录
- **压缩文件**: 自动保存在 `zip/` 子目录

### ⚡ 性能优化
- **内存优化**: 使用SQLite数据库避免大量文件占用内存
- **流式处理**: 分块读取文件，支持大文件处理
- **批量操作**: 批量处理减少I/O操作
- **智能跳过**: 自动跳过系统目录和缩略图

### 🛡️ 安全特性
- **文件保护**: 仅复制文件，从不删除源文件
- **冲突处理**: 智能处理文件名冲突
- **系统目录保护**: 自动跳过群晖系统目录（@eaDir等）

## 📋 版本对比

项目包含三个版本，适合不同的使用场景：

| 版本 | 文件名 | 特点 | 适用场景 |
|------|--------|------|----------|
| **基础版** | `media_organizer.py` | 功能完整，内存使用较高 | 小到中等规模文件处理 |
| **优化版** | `media_organizer_optimized.py` | 使用SQLite优化内存，处理大量文件 | 大规模文件处理，推荐使用 |
| **高性能版** | `media_organizer_ultra.py` | 极致性能优化，最快处理速度 | 超大规模文件处理 |

## 🚀 安装与配置

### 系统要求

- Python 3.6 或更高版本
- 足够的磁盘空间用于目标目录

### 安装依赖

```bash
# 安装Python依赖
pip install Pillow

# 或使用requirements.txt（如果存在）
pip install -r requirements.txt
```

### 群晖NAS配置

1. **启用SSH服务**
   - 控制面板 → 终端机和SNMP → 启用SSH服务

2. **安装Python包**
   ```bash
   # SSH连接到群晖后执行
   sudo pip3 install Pillow
   ```

3. **下载脚本**
   ```bash
   # 创建脚本目录
   mkdir -p /volume1/scripts
   cd /volume1/scripts
   
   # 下载脚本文件（以优化版为例）
   wget https://raw.githubusercontent.com/your-repo/media_organizer_optimized.py
   chmod +x media_organizer_optimized.py
   ```

## 📖 使用说明

### 基本用法

```bash
# 基本使用（推荐使用优化版）
python3 media_organizer_optimized.py --source /path/to/source --target /path/to/target

# 快速模式（仅使用文件哈希，速度更快）
python3 media_organizer_optimized.py --source /path/to/source --target /path/to/target --fast

# 多个源目录处理
python3 media_organizer_optimized.py --source /path/src1 /path/src2 /path/src3 --target /path/to/target

# 一对一目录处理
python3 media_organizer_optimized.py --source /path/src1 /path/src2 --target /path/tgt1 /path/tgt2
```

### 参数说明

| 参数 | 简写 | 说明 | 示例 |
|------|------|------|------|
| `--source` | `-s` | 源目录路径（支持多个） | `--source /photos/raw /photos/import` |
| `--target` | `-t` | 目标目录路径（支持多个） | `--target /photos/organized` |
| `--fast` | | 启用快速模式（仅文件哈希） | `--fast` |
| `--db` | | 数据库文件路径（优化版） | `--db /tmp/media.db` |

### 工作模式

#### 🔄 精确模式（默认）
- 计算文件哈希 + 图片内容哈希
- 可检测格式转换后的重复图片
- 处理速度较慢，但检测更准确

#### ⚡ 快速模式
- 仅计算文件哈希
- 处理速度快，适合大批量处理
- 无法检测格式转换后的重复图片

### 目录结构示例

**处理前:**
```
/photos/
├── import/           # 源目录
│   ├── IMG_001.jpg
│   ├── video.mp4
│   └── backup.zip
└── organized/        # 目标目录（将被整理）
```

**处理后:**
```
/photos/organized/
├── IMG_001.jpg      # 图片文件（主目录）
├── mp4/             # 视频文件子目录
│   └── video.mp4
└── zip/             # 压缩文件子目录
    └── backup.zip
```

## 🔧 实际使用示例

### 示例1: 日常照片整理

```bash
# 将手机导入、相机卡和下载的图片整理到统一目录
python3 media_organizer_optimized.py \
  --source /volume1/photos/phone /volume1/photos/camera /volume1/photos/downloads \
  --target /volume1/photos/organized \
  --fast
```

### 示例2: 多设备备份整理

```bash
# 将不同设备的文件分别整理到对应目录
python3 media_organizer_optimized.py \
  --source /volume1/backup/device1 /volume1/backup/device2 \
  --target /volume1/organized/device1 /volume1/organized/device2
```

### 示例3: 群晖任务计划

在群晖控制面板中设置定时任务：

```bash
# 每周日凌晨2点执行照片整理
cd /volume1/scripts && python3 media_organizer_optimized.py \
  --source /volume1/photos/import \
  --target /volume1/photos/library \
  --fast \
  --db /tmp/media_$(date +%Y%m%d).db
```

## 📊 处理结果示例

```
=== 媒体文件去重和整理工具启动（优化版）===
源目录: /volume1/photos/import
目标目录: /volume1/photos/organized
模式: 快速模式

正在扫描目标目录: /volume1/photos/organized
目标目录扫描完成: 图片 1,234 张, 视频 56 个, 压缩文件 12 个

正在扫描源目录: /volume1/photos/import
源目录扫描完成: 图片 567 张, 视频 23 个, 压缩文件 8 个

开始处理 image 文件...
image 处理完成! 复制: 234, 替换: 12, 跳过: 321, 删除重复: 8

开始处理 video 文件...
video 处理完成! 复制: 15, 替换: 3, 跳过: 5, 删除重复: 2

开始处理 archive 文件...
archive 处理完成! 复制: 4, 替换: 1, 跳过: 3, 删除重复: 0

=== 媒体文件去重和整理工具完成（优化版）===
总计处理了 253 个文件
总计跳过了 329 个重复文件
总计删除了 10 个重复文件
```

## 📝 日志文件

程序运行时会生成详细的日志文件 `media_organizer.log`：

```
2025-06-02 14:30:15,123 - INFO - 正在扫描目标目录: /volume1/photos/organized
2025-06-02 14:30:16,456 - INFO - 复制唯一文件: /volume1/photos/import/IMG_001.jpg -> /volume1/photos/organized/IMG_001.jpg
2025-06-02 14:30:17,789 - INFO - 跳过重复文件: /volume1/photos/import/IMG_002.jpg (1234567 bytes)
2025-06-02 14:30:18,012 - INFO - 替换较小文件: /volume1/photos/import/IMG_003.jpg (2345678 bytes)
```

日志包含：
- 文件扫描进度
- 复制、跳过、替换操作记录
- 错误和警告信息
- 性能统计信息

## ⚠️ 注意事项

### 权限要求
- 对源目录的读取权限
- 对目标目录的读写权限
- 足够的磁盘空间

### 安全提醒
- **备份重要文件**: 首次运行前建议备份重要数据
- **测试运行**: 建议先在小规模数据上测试
- **源文件安全**: 程序不会删除源目录中的任何文件

### 性能考虑
- **首次运行**: 目标目录已有大量文件时，首次运行耗时较长
- **内存使用**: 优化版和高性能版显著减少内存占用
- **网络存储**: 网络存储设备处理速度可能较慢

### 系统兼容性
- **群晖系统**: 自动跳过 `@eaDir`、`.DS_Store` 等系统目录
- **文件名冲突**: 自动处理重名文件，添加数字后缀
- **路径限制**: 支持长文件名和特殊字符

## 🔍 故障排除

### 常见问题

**Q: 为什么显示的文件数量比实际文件多？**
A: 程序可能扫描到了系统缓存目录中的缩略图。新版本已自动跳过这些目录。

**Q: 程序会删除原始文件吗？**
A: 不会。程序只复制文件到目标目录，从不删除源目录中的文件。

**Q: 如何确保保留最高质量的图片？**
A: 程序自动选择文件大小最大的版本。如需更精确判断，建议手动检查。

**Q: 处理中断后如何继续？**
A: 重新运行程序即可，已处理的文件会被跳过。

### 错误处理

```bash
# 查看详细错误信息
tail -f media_organizer.log

# 检查磁盘空间
df -h

# 检查权限
ls -la /path/to/directory
```

## 📁 支持的文件格式

### 图片格式
- JPEG (.jpg, .jpeg)
- PNG (.png)  
- GIF (.gif)
- BMP (.bmp)
- TIFF (.tiff)
- WebP (.webp)
- HEIC (.heic)
- HEIF (.heif)

### 视频格式
- MP4 (.mp4)
- AVI (.avi)
- MOV (.mov)
- MKV (.mkv)
- WMV (.wmv)
- FLV (.flv)
- WebM (.webm)
- M4V (.m4v)
- 3GP (.3gp)
- MPG/MPEG (.mpg, .mpeg)

### 压缩格式
- ZIP (.zip)
- RAR (.rar)
- 7Z (.7z)
- TAR (.tar)
- GZIP (.gz, .tar.gz)
- BZIP2 (.bz2, .tar.bz2)
- XZ (.xz, .tar.xz)

## 🛠️ 开发与贡献

### 目录结构

```
image2out/
├── media_organizer.py              # 基础版本
├── media_organizer_optimized.py    # 优化版本（推荐）
├── media_organizer_ultra.py        # 高性能版本
├── image_deduplicator*.py          # 早期图片去重版本
└── README.md                       # 项目文档
```

### 技术特点

- **哈希算法**: MD5文件哈希 + 图片感知哈希
- **数据库**: SQLite存储文件信息（优化版）
- **图像处理**: PIL/Pillow库处理图片
- **内存管理**: 流式处理和批量操作

### 贡献指南

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- [Pillow](https://pillow.readthedocs.io/) - Python图像处理库
- [SQLite](https://www.sqlite.org/) - 轻量级数据库引擎
- 群晖社区的反馈和建议

---

**⭐ 如果这个项目对您有帮助，请给我们一个星标！**