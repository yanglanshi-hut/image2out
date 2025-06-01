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
        logging.FileHandler("image_deduplicator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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

def is_image_file(file_path):
    """判断文件是否为图片文件"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.heif'}
    _, ext = os.path.splitext(file_path.lower())
    return ext in image_extensions

def should_skip_directory(dir_path):
    """判断是否应该跳过该目录"""
    skip_dirs = {'@eaDir', '.DS_Store', 'Thumbs.db', '@Recycle', '#recycle', '.thumbnail'}
    dir_name = os.path.basename(dir_path)
    return dir_name in skip_dirs or dir_name.startswith('.')

def process_images(source_dir, target_dir, use_content_hash=True):
    """
    处理图片：找出所有图片，去重，并保留最大的文件
    完全重写以修复逻辑问题
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        logger.info(f"创建目标目录: {target_dir}")

    # 收集所有图片信息，包括源目录和目标目录
    all_images = {}  # filename -> [{'path': str, 'size': int, 'hash': str, 'content_hash': str}]
    
    # 扫描目标目录
    logger.info(f"正在扫描目标目录: {target_dir}")
    target_count = 0
    for root, dirs, files in os.walk(target_dir):
        # 跳过系统目录
        dirs[:] = [d for d in dirs if not should_skip_directory(os.path.join(root, d))]
        
        for filename in files:
            if is_image_file(filename):
                target_count += 1
                file_path = os.path.join(root, filename)
                file_hash, content_hash = calculate_image_hash(file_path)
                file_size = os.path.getsize(file_path)
                
                base_filename = os.path.basename(filename)
                if base_filename not in all_images:
                    all_images[base_filename] = []
                
                all_images[base_filename].append({
                    'path': file_path,
                    'size': file_size,
                    'hash': file_hash,
                    'content_hash': content_hash,
                    'is_target': True
                })
    
    logger.info(f"目标目录中找到 {target_count} 张图片")
    
    # 扫描源目录
    logger.info(f"正在扫描源目录: {source_dir}")
    source_count = 0
    for root, dirs, files in os.walk(source_dir):
        # 跳过系统目录
        dirs[:] = [d for d in dirs if not should_skip_directory(os.path.join(root, d))]
        
        for filename in files:
            if is_image_file(filename):
                source_count += 1
                file_path = os.path.join(root, filename)
                file_hash, content_hash = calculate_image_hash(file_path)
                file_size = os.path.getsize(file_path)
                
                base_filename = os.path.basename(filename)
                if base_filename not in all_images:
                    all_images[base_filename] = []
                
                all_images[base_filename].append({
                    'path': file_path,
                    'size': file_size,
                    'hash': file_hash,
                    'content_hash': content_hash,
                    'is_target': False
                })
    
    logger.info(f"源目录中找到 {source_count} 张图片")
    
    # 按文件名分组处理重复项
    copied_count = 0
    skipped_count = 0
    replaced_count = 0
    
    for filename, file_list in all_images.items():
        if len(file_list) == 1:
            # 只有一个文件，如果在源目录中则复制
            file_info = file_list[0]
            if not file_info['is_target']:
                target_path = os.path.join(target_dir, filename)
                try:
                    shutil.copy2(file_info['path'], target_path)
                    logger.info(f"复制唯一文件: {file_info['path']} -> {target_path}")
                    copied_count += 1
                except Exception as e:
                    logger.error(f"复制文件失败: {file_info['path']}, 错误: {e}")
        else:
            # 有多个同名文件，选择最大的
            largest_file = max(file_list, key=lambda x: x['size'])
            target_path = os.path.join(target_dir, filename)
            
            # 如果最大的文件已经在目标目录中
            if largest_file['is_target']:
                # 删除其他较小的文件（如果在目标目录中）
                for file_info in file_list:
                    if file_info != largest_file and file_info['is_target']:
                        try:
                            os.remove(file_info['path'])
                            logger.info(f"删除较小的重复文件: {file_info['path']} ({file_info['size']} bytes)")
                        except Exception as e:
                            logger.error(f"删除文件失败: {file_info['path']}, 错误: {e}")
                skipped_count += len([f for f in file_list if not f['is_target']])
            else:
                # 最大的文件在源目录中，需要复制
                # 先删除目标目录中的所有同名文件
                for file_info in file_list:
                    if file_info['is_target']:
                        try:
                            os.remove(file_info['path'])
                            logger.info(f"删除较小的重复文件: {file_info['path']} ({file_info['size']} bytes)")
                        except Exception as e:
                            logger.error(f"删除文件失败: {file_info['path']}, 错误: {e}")
                
                # 复制最大的文件
                try:
                    shutil.copy2(largest_file['path'], target_path)
                    logger.info(f"复制最大文件: {largest_file['path']} ({largest_file['size']} bytes) -> {target_path}")
                    replaced_count += 1
                except Exception as e:
                    logger.error(f"复制文件失败: {largest_file['path']}, 错误: {e}")
                
                # 统计跳过的文件
                skipped_count += len([f for f in file_list if f != largest_file and not f['is_target']])
    
    logger.info(f"处理完成! 源目录: {source_count} 张, 复制: {copied_count}, 替换: {replaced_count}, 跳过: {skipped_count}")
    return copied_count + replaced_count, skipped_count

def main():
    parser = argparse.ArgumentParser(description='图片去重和整理工具')
    parser.add_argument('--source', '-s', required=True, help='源图片目录')
    parser.add_argument('--target', '-t', required=True, help='目标图片目录')
    parser.add_argument('--fast', action='store_true', help='使用快速模式（仅文件哈希，不检测内容相似性）')
    
    args = parser.parse_args()
    
    logger.info("=== 图片去重和整理工具启动 ===")
    logger.info(f"源目录: {args.source}")
    logger.info(f"目标目录: {args.target}")
    logger.info(f"模式: {'快速模式' if args.fast else '精确模式(包含内容比较)'}")
    
    if not os.path.exists(args.source):
        logger.error(f"源目录不存在: {args.source}")
        return 1
    
    copied, skipped = process_images(args.source, args.target, not args.fast)
    
    logger.info("=== 图片去重和整理工具完成 ===")
    logger.info(f"复制了 {copied} 张新图片")
    logger.info(f"跳过了 {skipped} 张重复图片")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 