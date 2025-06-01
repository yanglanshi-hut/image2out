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
    if ext not in image_extensions:
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
            file_path = os.path.join(root, filename)
            if is_image_file(file_path):
                target_count += 1
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
    processed_files = 0
    total_files = 0
    
    # 先统计总文件数以便显示进度
    logger.info("正在统计源目录中的文件数量...")
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if not should_skip_directory(os.path.join(root, d))]
        for filename in files:
            _, ext = os.path.splitext(filename.lower())
            if ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.heif'}:
                total_files += 1
    
    logger.info(f"源目录中共有 {total_files} 个可能的图片文件")
    
    # 扫描源目录
    for root, dirs, files in os.walk(source_dir):
        # 跳过系统目录
        dirs[:] = [d for d in dirs if not should_skip_directory(os.path.join(root, d))]
        
        for filename in files:
            file_path = os.path.join(root, filename)
            _, ext = os.path.splitext(filename.lower())
            
            # 只处理可能的图片文件扩展名
            if ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp', '.heic', '.heif'}:
                processed_files += 1
                
                # 显示进度
                if processed_files % 100 == 0 or processed_files == total_files:
                    logger.info(f"正在处理: {processed_files}/{total_files} ({processed_files/total_files*100:.1f}%)")
                
                # 验证是否为有效图片
                if is_image_file(file_path):
                    source_count += 1
                    file_hash, content_hash = calculate_image_hash(file_path)
                    if file_hash is None:  # 如果计算哈希失败，跳过该文件
                        logger.warning(f"跳过无法处理的文件: {file_path}")
                        continue
                        
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
                else:
                    logger.debug(f"跳过非有效图片文件: {file_path}")
        logger.info(f"源目录中找到 {source_count} 张图片")
    
    # 按哈希值分组处理重复项（真正的去重）
    hash_groups = {}  # hash -> [file_info, ...]
    
    # 将所有图片按哈希值分组
    for filename, file_list in all_images.items():
        for file_info in file_list:
            # 使用文件哈希作为主要去重依据
            primary_hash = file_info['hash']
            if primary_hash:
                if primary_hash not in hash_groups:
                    hash_groups[primary_hash] = []
                hash_groups[primary_hash].append(file_info)
            
            # 如果启用内容哈希且与文件哈希不同，也加入分组
            if use_content_hash and file_info['content_hash'] and file_info['content_hash'] != primary_hash:
                content_hash = file_info['content_hash']
                if content_hash not in hash_groups:
                    hash_groups[content_hash] = []
                hash_groups[content_hash].append(file_info)
    
    # 处理每个哈希组
    copied_count = 0
    skipped_count = 0
    replaced_count = 0
    processed_files = set()  # 避免重复处理同一个文件
    
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
                if not file_info['is_target'] and file_info['path'] not in processed_files:
                    # 源目录中的唯一文件，复制到目标目录
                    target_path = os.path.join(target_dir, os.path.basename(file_info['path']))
                    
                    # 处理文件名冲突
                    original_target_path = target_path
                    counter = 1
                    while os.path.exists(target_path):
                        name, ext = os.path.splitext(os.path.basename(file_info['path']))
                        target_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
                        counter += 1
                    
                    try:
                        shutil.copy2(file_info['path'], target_path)
                        logger.info(f"复制唯一文件: {file_info['path']} -> {target_path}")
                        copied_count += 1
                        processed_files.add(file_info['path'])
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
                    if file_info != largest_file and file_info['path'] not in processed_files:
                        try:
                            os.remove(file_info['path'])
                            logger.info(f"删除较小的重复文件: {file_info['path']} ({file_info['size']} bytes)")
                            processed_files.add(file_info['path'])
                        except Exception as e:
                            logger.error(f"删除文件失败: {file_info['path']}, 错误: {e}")
                
                # 跳过源目录中的重复文件
                for file_info in source_files:
                    if file_info['path'] not in processed_files:
                        logger.debug(f"跳过重复文件: {file_info['path']} ({file_info['size']} bytes)")
                        skipped_count += 1
                        processed_files.add(file_info['path'])
            else:
                # 最大文件在源目录中，需要复制并替换
                # 删除目标目录中的所有重复文件
                for file_info in target_files:
                    if file_info['path'] not in processed_files:
                        try:
                            os.remove(file_info['path'])
                            logger.info(f"删除较小的重复文件: {file_info['path']} ({file_info['size']} bytes)")
                            processed_files.add(file_info['path'])
                        except Exception as e:
                            logger.error(f"删除文件失败: {file_info['path']}, 错误: {e}")
                
                # 复制最大的文件
                if largest_file['path'] not in processed_files:
                    target_path = os.path.join(target_dir, os.path.basename(largest_file['path']))
                    
                    # 处理文件名冲突
                    counter = 1
                    while os.path.exists(target_path):
                        name, ext = os.path.splitext(os.path.basename(largest_file['path']))
                        target_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
                        counter += 1
                    
                    try:
                        shutil.copy2(largest_file['path'], target_path)
                        logger.info(f"复制最大文件: {largest_file['path']} ({largest_file['size']} bytes) -> {target_path}")
                        replaced_count += 1
                        processed_files.add(largest_file['path'])
                    except Exception as e:
                        logger.error(f"复制文件失败: {largest_file['path']}, 错误: {e}")
                
                # 跳过源目录中其他较小的重复文件
                for file_info in source_files:
                    if file_info != largest_file and file_info['path'] not in processed_files:
                        logger.debug(f"跳过较小的重复文件: {file_info['path']} ({file_info['size']} bytes)")
                        skipped_count += 1
                        processed_files.add(file_info['path'])
    
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