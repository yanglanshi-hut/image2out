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

def process_images(source_dir, target_dir, use_content_hash=True):
    """
    处理图片：找出所有图片，去重，并移动到目标目录
    保留文件名，如果重复则保留文件大小最大的那张
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        logger.info(f"创建目标目录: {target_dir}")

    # 用字典来跟踪已有图片，存储哈希值到文件路径和大小的映射
    existing_files = {}  # hash -> (file_path, file_size, is_in_target)
    
    # 首先加载目标目录中已有的图片哈希值
    logger.info(f"正在加载目标目录中的现有图片: {target_dir}")
    target_image_count = 0
    for root, _, files in os.walk(target_dir):
        for filename in files:
            if is_image_file(filename):
                target_image_count += 1
                file_path = os.path.join(root, filename)
                file_hash, content_hash = calculate_image_hash(file_path)
                file_size = os.path.getsize(file_path)
                
                if file_hash:
                    existing_files[file_hash] = (file_path, file_size, True)
                if use_content_hash and content_hash:
                    existing_files[content_hash] = (file_path, file_size, True)
    
    logger.info(f"目标目录中已有 {target_image_count} 张图片")
    
    # 收集源目录中的所有图片信息
    source_images = []
    logger.info(f"正在扫描源目录: {source_dir}")
    for root, _, files in os.walk(source_dir):
        for filename in files:
            if is_image_file(filename):
                source_path = os.path.join(root, filename)
                file_hash, content_hash = calculate_image_hash(source_path)
                file_size = os.path.getsize(source_path)
                
                source_images.append({
                    'path': source_path,
                    'filename': filename,
                    'file_hash': file_hash,
                    'content_hash': content_hash,
                    'size': file_size
                })
    
    total_images = len(source_images)
    logger.info(f"源目录中找到 {total_images} 张图片")
    
    # 处理源目录中的图片
    copied_images = 0
    skipped_images = 0
    replaced_images = 0
    
    logger.info(f"开始处理源目录图片...")
    for i, img_info in enumerate(source_images, 1):
        source_path = img_info['path']
        filename = img_info['filename']
        file_hash = img_info['file_hash']
        content_hash = img_info['content_hash']
        file_size = img_info['size']
        
        # 检查是否为重复图片
        duplicate_hash = None
        if file_hash and file_hash in existing_files:
            duplicate_hash = file_hash
        elif use_content_hash and content_hash and content_hash in existing_files:
            duplicate_hash = content_hash
        
        if duplicate_hash:
            existing_path, existing_size, is_in_target = existing_files[duplicate_hash]
            
            # 如果当前文件更大，则替换
            if file_size > existing_size:
                if is_in_target:
                    # 删除目标目录中的旧文件
                    try:
                        os.remove(existing_path)
                        logger.info(f"删除较小的重复文件: {existing_path} ({existing_size} bytes)")
                    except Exception as e:
                        logger.error(f"删除文件失败: {existing_path}, 错误: {e}")
                        continue
                
                # 复制新的更大文件
                target_path = os.path.join(target_dir, filename)
                # 如果目标文件名已存在，添加数字后缀
                counter = 1
                while os.path.exists(target_path):
                    name, ext = os.path.splitext(filename)
                    target_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
                    counter += 1
                
                try:
                    shutil.copy2(source_path, target_path)
                    logger.info(f"替换为更大文件: {source_path} ({file_size} bytes) -> {target_path}")
                    
                    # 更新记录
                    existing_files[duplicate_hash] = (target_path, file_size, True)
                    replaced_images += 1
                except Exception as e:
                    logger.error(f"复制文件时出错: {source_path}, 错误: {e}")
            else:
                skipped_images += 1
                logger.debug(f"跳过较小的重复文件: {source_path} ({file_size} bytes)")
        else:
            # 非重复图片，直接复制
            target_path = os.path.join(target_dir, filename)
            # 如果目标文件名已存在，添加数字后缀
            counter = 1
            while os.path.exists(target_path):
                name, ext = os.path.splitext(filename)
                target_path = os.path.join(target_dir, f"{name}_{counter}{ext}")
                counter += 1
            
            try:
                shutil.copy2(source_path, target_path)
                logger.debug(f"已复制: {source_path} -> {target_path}")
                
                # 更新记录
                if file_hash:
                    existing_files[file_hash] = (target_path, file_size, True)
                if content_hash:
                    existing_files[content_hash] = (target_path, file_size, True)
                
                copied_images += 1
            except Exception as e:
                logger.error(f"复制文件时出错: {source_path}, 错误: {e}")
        
        if i % 10 == 0 or i == total_images:
            logger.info(f"已处理: {i}/{total_images}, 新复制: {copied_images}, 替换: {replaced_images}, 跳过: {skipped_images}")
    
    logger.info(f"处理完成! 总共: {total_images}, 新复制: {copied_images}, 替换: {replaced_images}, 跳过: {skipped_images}")
    return copied_images + replaced_images, skipped_images

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