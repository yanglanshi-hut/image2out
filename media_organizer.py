#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import hashlib
import shutil
import argparse
from datetime import datetime
from PIL import Image
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("media_organizer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def calculate_file_hash(file_path):
    """
    计算文件的哈希值，用于文件去重
    """
    try:
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
        return file_hash
    except Exception as e:
        logger.error(f"计算文件哈希失败: {file_path}, 错误: {e}")
        return None

def calculate_image_hash(image_path):
    """
    计算图片的哈希值，用于图片去重
    支持两种模式：快速模式(文件哈希)和精确模式(图片内容哈希)
    """
    try:
        # 文件哈希 - 更快但不能检测内容相同但编码/格式不同的图片
        with open(image_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()
            
        # 内容哈希 - 打开图片并调整大小以创建感知哈希
        # 这可以检测到即使调整大小或格式不同但内容相同的图片
        try:
            img = Image.open(image_path)
            # 转换为小缩略图并转为灰度
            img = img.resize((8, 8), Image.Resampling.LANCZOS).convert('L')
            # 计算像素平均值
            pixels = list(img.getdata())
            avg_pixel = sum(pixels) / len(pixels)
            # 基于平均值生成位序列
            bits = ''.join(['1' if pixel >= avg_pixel else '0' for pixel in pixels])
            # 将位序列转换为十六进制字符串
            content_hash = hex(int(bits, 2))[2:].zfill(16)
            
            return file_hash, content_hash
        except Exception as e:
            logger.warning(f"无法计算图片内容哈希，仅使用文件哈希: {image_path}, 错误: {e}")
            return file_hash, None
            
    except Exception as e:
        logger.error(f"计算图片哈希失败: {image_path}, 错误: {e}")
        return None, None

def get_file_type(file_path):
    """
    判断文件类型：图片、视频、压缩文件或其他
    """
    _, ext = os.path.splitext(file_path.lower())
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.heif'}
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.mpg', '.mpeg'}
    archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2', '.xz', '.tar.gz', '.tar.bz2', '.tar.xz'}
    
    if ext in image_extensions:
        return 'image'
    elif ext in video_extensions:
        return 'video'
    elif ext in archive_extensions:
        return 'archive'
    else:
        return 'other'

def is_image_file(file_path):
    """判断文件是否为图片文件"""
    if get_file_type(file_path) != 'image':
        return False
    
    # 额外验证：尝试打开文件确认是否为有效图片
    try:
        with Image.open(file_path) as img:
            img.verify()  # 验证图片是否损坏
        return True
    except Exception:
        # 如果无法打开或验证失败，说明不是有效图片文件
        return False

def should_skip_directory(dir_path):
    """判断是否应该跳过该目录"""
    skip_dirs = {'@eaDir', '.DS_Store', 'Thumbs.db', '@Recycle', '#recycle', '.thumbnail', 'mp4', 'zip'}
    dir_name = os.path.basename(dir_path)
    return dir_name in skip_dirs or dir_name.startswith('.')

def get_target_directory(target_dir, file_type):
    """
    根据文件类型获取目标目录
    """
    if file_type == 'video':
        return os.path.join(target_dir, 'mp4')
    elif file_type == 'archive':
        return os.path.join(target_dir, 'zip')
    else:
        return target_dir

def ensure_directory_exists(dir_path):
    """
    确保目录存在，如果不存在则创建
    """
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        logger.info(f"创建目录: {dir_path}")

def process_media_files(source_dir, target_dir, use_content_hash=True):
    """
    处理媒体文件：找出所有文件，按类型分类存储，去重，并保留最大的文件
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        logger.info(f"创建目标目录: {target_dir}")

    # 收集所有文件信息，按类型分组
    all_files = {
        'image': {},  # filename -> [{'path': str, 'size': int, 'hash': str, 'content_hash': str}]
        'video': {},
        'archive': {},
        'other': {}
    }
    
    # 扫描目标目录（包括子目录）
    logger.info(f"正在扫描目标目录: {target_dir}")
    target_counts = {'image': 0, 'video': 0, 'archive': 0, 'other': 0}
    
    for root, dirs, files in os.walk(target_dir):
        # 跳过系统目录
        dirs[:] = [d for d in dirs if not should_skip_directory(os.path.join(root, d))]
        
        for filename in files:
            file_path = os.path.join(root, filename)
            file_type = get_file_type(file_path)
            
            # 验证图片文件
            if file_type == 'image' and not is_image_file(file_path):
                continue
                
            target_counts[file_type] += 1
            file_size = os.path.getsize(file_path)
            
            if file_type == 'image':
                file_hash, content_hash = calculate_image_hash(file_path)
            else:
                file_hash = calculate_file_hash(file_path)
                content_hash = None
            
            base_filename = os.path.basename(filename)
            if base_filename not in all_files[file_type]:
                all_files[file_type][base_filename] = []
            
            all_files[file_type][base_filename].append({
                'path': file_path,
                'size': file_size,
                'hash': file_hash,
                'content_hash': content_hash,
                'is_target': True,
                'file_type': file_type
            })
    
    logger.info(f"目标目录中找到: 图片 {target_counts['image']} 张, 视频 {target_counts['video']} 个, 压缩文件 {target_counts['archive']} 个, 其他 {target_counts['other']} 个")

    # 扫描源目录
    logger.info(f"正在扫描源目录: {source_dir}")
    source_counts = {'image': 0, 'video': 0, 'archive': 0, 'other': 0}
    processed_files = 0
    total_files = 0
    
    # 先统计总文件数以便显示进度
    logger.info("正在统计源目录中的文件数量...")
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if not should_skip_directory(os.path.join(root, d))]
        for filename in files:
            file_type = get_file_type(os.path.join(root, filename))
            if file_type in ['image', 'video', 'archive']:
                total_files += 1
    
    logger.info(f"源目录中共有 {total_files} 个可处理的文件")
    
    # 扫描源目录
    for root, dirs, files in os.walk(source_dir):
        # 跳过系统目录
        dirs[:] = [d for d in dirs if not should_skip_directory(os.path.join(root, d))]
        
        for filename in files:
            file_path = os.path.join(root, filename)
            file_type = get_file_type(file_path)
            
            # 只处理图片、视频和压缩文件
            if file_type in ['image', 'video', 'archive']:
                processed_files += 1
                
                # 显示进度
                if processed_files % 100 == 0 or processed_files == total_files:
                    logger.info(f"正在处理: {processed_files}/{total_files} ({processed_files/total_files*100:.1f}%)")
                
                # 验证图片文件
                if file_type == 'image' and not is_image_file(file_path):
                    logger.debug(f"跳过非有效图片文件: {file_path}")
                    continue
                    
                source_counts[file_type] += 1
                
                if file_type == 'image':
                    file_hash, content_hash = calculate_image_hash(file_path)
                else:
                    file_hash = calculate_file_hash(file_path)
                    content_hash = None
                    
                if file_hash is None:  # 如果计算哈希失败，跳过该文件
                    logger.warning(f"跳过无法处理的文件: {file_path}")
                    continue
                        
                file_size = os.path.getsize(file_path)
                
                base_filename = os.path.basename(filename)
                if base_filename not in all_files[file_type]:
                    all_files[file_type][base_filename] = []
                
                all_files[file_type][base_filename].append({
                    'path': file_path,
                    'size': file_size,
                    'hash': file_hash,
                    'content_hash': content_hash,
                    'is_target': False,
                    'file_type': file_type
                })
    
    logger.info(f"源目录中找到: 图片 {source_counts['image']} 张, 视频 {source_counts['video']} 个, 压缩文件 {source_counts['archive']} 个")
    
    # 处理每种文件类型
    total_copied = 0
    total_skipped = 0
    total_replaced = 0
    total_deleted = 0
    
    for file_type in ['image', 'video', 'archive']:
        if not all_files[file_type]:
            continue
            
        logger.info(f"\n开始处理 {file_type} 文件...")
        
        # 确保目标目录存在
        type_target_dir = get_target_directory(target_dir, file_type)
        ensure_directory_exists(type_target_dir)
        
        # 按哈希值分组处理重复项
        hash_groups = {}  # hash -> [file_info, ...]
        
        # 将所有文件按哈希值分组
        for filename, file_list in all_files[file_type].items():
            for file_info in file_list:
                # 使用文件哈希作为主要去重依据
                primary_hash = file_info['hash']
                if primary_hash:
                    if primary_hash not in hash_groups:
                        hash_groups[primary_hash] = []
                    hash_groups[primary_hash].append(file_info)
                
                # 如果是图片且启用内容哈希且与文件哈希不同，也加入分组
                if (file_type == 'image' and use_content_hash and 
                    file_info['content_hash'] and file_info['content_hash'] != primary_hash):
                    content_hash = file_info['content_hash']
                    if content_hash not in hash_groups:
                        hash_groups[content_hash] = []
                    hash_groups[content_hash].append(file_info)
        
        # 处理每个哈希组
        copied_count = 0
        skipped_count = 0
        replaced_count = 0
        deleted_count = 0
        processed_files_set = set()  # 避免重复处理同一个文件
        
        for hash_value, file_list in hash_groups.items():
            # 去除重复的文件引用（同一文件可能被文件哈希和内容哈希都引用）
            unique_files = []
            seen_paths = set()
            for file_info in file_list:
                if file_info['path'] not in seen_paths:
                    unique_files.append(file_info)
                    seen_paths.add(file_info['path'])
            
            if len(unique_files) <= 1:
                # 没有重复文件
                if len(unique_files) == 1:
                    file_info = unique_files[0]
                    if not file_info['is_target'] and file_info['path'] not in processed_files_set:
                        # 源目录中的唯一文件，复制到目标目录
                        target_path = os.path.join(type_target_dir, os.path.basename(file_info['path']))
                        
                        # 处理文件名冲突
                        counter = 1
                        while os.path.exists(target_path):
                            name, ext = os.path.splitext(os.path.basename(file_info['path']))
                            target_path = os.path.join(type_target_dir, f"{name}_{counter}{ext}")
                            counter += 1
                        
                        try:
                            shutil.copy2(file_info['path'], target_path)
                            logger.info(f"复制唯一文件: {file_info['path']} -> {target_path}")
                            copied_count += 1
                            processed_files_set.add(file_info['path'])
                        except Exception as e:
                            logger.error(f"复制文件失败: {file_info['path']}, 错误: {e}")
            else:
                # 有重复文件，选择最大的
                largest_file = max(unique_files, key=lambda x: x['size'])
                
                # 检查最大文件是否已经在目标目录中
                target_files = [f for f in unique_files if f['is_target']]
                source_files = [f for f in unique_files if not f['is_target']]
                
                if largest_file['is_target']:
                    # 最大文件已在目标目录中
                    # 删除目标目录中其他较小的重复文件
                    for file_info in target_files:
                        if file_info != largest_file and file_info['path'] not in processed_files_set:
                            try:
                                os.remove(file_info['path'])
                                logger.info(f"删除较小的重复文件: {file_info['path']} ({file_info['size']} bytes)")
                                deleted_count += 1
                                processed_files_set.add(file_info['path'])
                            except Exception as e:
                                logger.error(f"删除文件失败: {file_info['path']}, 错误: {e}")
                    
                    # 跳过源目录中的重复文件
                    for file_info in source_files:
                        if file_info['path'] not in processed_files_set:
                            logger.debug(f"跳过重复文件: {file_info['path']} ({file_info['size']} bytes)")
                            skipped_count += 1
                            processed_files_set.add(file_info['path'])
                else:
                    # 最大文件在源目录中，需要复制并替换
                    # 删除目标目录中的所有重复文件
                    for file_info in target_files:
                        if file_info['path'] not in processed_files_set:
                            try:
                                os.remove(file_info['path'])
                                logger.info(f"删除较小的重复文件: {file_info['path']} ({file_info['size']} bytes)")
                                deleted_count += 1
                                processed_files_set.add(file_info['path'])
                            except Exception as e:
                                logger.error(f"删除文件失败: {file_info['path']}, 错误: {e}")
                    
                    # 复制最大的文件
                    if largest_file['path'] not in processed_files_set:
                        target_path = os.path.join(type_target_dir, os.path.basename(largest_file['path']))
                        
                        # 处理文件名冲突
                        counter = 1
                        while os.path.exists(target_path):
                            name, ext = os.path.splitext(os.path.basename(largest_file['path']))
                            target_path = os.path.join(type_target_dir, f"{name}_{counter}{ext}")
                            counter += 1
                        
                        try:
                            shutil.copy2(largest_file['path'], target_path)
                            logger.info(f"复制最大文件: {largest_file['path']} ({largest_file['size']} bytes) -> {target_path}")
                            replaced_count += 1
                            processed_files_set.add(largest_file['path'])
                        except Exception as e:
                            logger.error(f"复制文件失败: {largest_file['path']}, 错误: {e}")
                    
                    # 跳过源目录中其他较小的重复文件
                    for file_info in source_files:
                        if file_info != largest_file and file_info['path'] not in processed_files_set:
                            logger.debug(f"跳过较小的重复文件: {file_info['path']} ({file_info['size']} bytes)")
                            skipped_count += 1
                            processed_files_set.add(file_info['path'])
        
        logger.info(f"{file_type} 处理完成! 源目录: {source_counts[file_type]} 个, 复制: {copied_count}, 替换: {replaced_count}, 跳过: {skipped_count}, 删除重复: {deleted_count}")
        
        total_copied += copied_count
        total_skipped += skipped_count
        total_replaced += replaced_count
        total_deleted += deleted_count
    
    return total_copied + total_replaced, total_skipped, total_deleted

def main():
    parser = argparse.ArgumentParser(description='媒体文件去重和整理工具（支持图片、视频、压缩文件）')
    parser.add_argument('--source', '-s', required=True, nargs='+', help='源文件目录（可指定多个）')
    parser.add_argument('--target', '-t', required=True, nargs='+', help='目标文件目录（可指定多个）')
    parser.add_argument('--fast', action='store_true', help='使用快速模式（仅文件哈希，不检测图片内容相似性）')
    
    args = parser.parse_args()
    
    logger.info("=== 媒体文件去重和整理工具启动 ===")
    logger.info(f"源目录: {', '.join(args.source)}")
    logger.info(f"目标目录: {', '.join(args.target)}")
    logger.info(f"模式: {'快速模式' if args.fast else '精确模式(包含图片内容比较)'}")
    logger.info("文件分类规则:")
    logger.info("- 图片文件: 保存在主目录")
    logger.info("- 视频文件: 保存在 mp4/ 子目录")
    logger.info("- 压缩文件: 保存在 zip/ 子目录")
    
    # 检查所有源目录是否存在
    for source_dir in args.source:
        if not os.path.exists(source_dir):
            logger.error(f"源目录不存在: {source_dir}")
            return 1
    
    # 如果有多个目标目录，确保数量匹配或只有一个目标目录
    if len(args.target) > 1 and len(args.target) != len(args.source):
        logger.error("如果指定多个目标目录，数量必须与源目录匹配，或者只指定一个目标目录")
        return 1
    
    # 处理多个源目录和目标目录的组合
    total_copied = 0
    total_skipped = 0
    total_deleted = 0
    
    for i, source_dir in enumerate(args.source):
        # 确定对应的目标目录
        if len(args.target) == 1:
            target_dir = args.target[0]
        else:
            target_dir = args.target[i]
        
        logger.info(f"\n处理第 {i+1}/{len(args.source)} 个任务: {source_dir} -> {target_dir}")
        copied, skipped, deleted = process_media_files(source_dir, target_dir, not args.fast)
        total_copied += copied
        total_skipped += skipped
        total_deleted += deleted
    
    logger.info("=== 媒体文件去重和整理工具完成 ===")
    logger.info(f"总计处理了 {total_copied} 个文件")
    logger.info(f"总计跳过了 {total_skipped} 个重复文件")
    logger.info(f"总计删除了 {total_deleted} 个重复文件")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
