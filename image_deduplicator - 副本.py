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
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        logger.info(f"创建目标目录: {target_dir}")

    # 创建哈希集合来跟踪已有图片
    existing_file_hashes = set()
    existing_content_hashes = set() if use_content_hash else set()
    
    # 首先加载目标目录中已有的图片哈希值
    logger.info(f"正在加载目标目录中的现有图片: {target_dir}")
    for root, _, files in os.walk(target_dir):
        for filename in files:
            if is_image_file(filename):
                file_path = os.path.join(root, filename)
                file_hash, content_hash = calculate_image_hash(file_path)
                if file_hash:
                    existing_file_hashes.add(file_hash)
                if content_hash:
                    existing_content_hashes.add(content_hash)
    
    logger.info(f"目标目录中已有 {len(existing_file_hashes)} 张图片")
    
    # 处理源目录中的图片
    total_images = 0
    copied_images = 0
    skipped_images = 0
    
    logger.info(f"开始处理源目录: {source_dir}")
    for root, _, files in os.walk(source_dir):
        for filename in files:
            if is_image_file(filename):
                total_images += 1
                source_path = os.path.join(root, filename)
                file_hash, content_hash = calculate_image_hash(source_path)
                
                # 检查是否为重复图片
                is_duplicate = False
                if file_hash in existing_file_hashes:
                    is_duplicate = True
                elif use_content_hash and content_hash and content_hash in existing_content_hashes:
                    is_duplicate = True
                
                if is_duplicate:
                    skipped_images += 1
                    if total_images % 100 == 0:
                        logger.info(f"已处理: {total_images}, 已复制: {copied_images}, 已跳过: {skipped_images}")
                    continue
                
                # 生成唯一文件名
                file_extension = os.path.splitext(filename)[1]
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                new_filename = f"{timestamp}{file_extension}"
                target_path = os.path.join(target_dir, new_filename)
                
                # 复制文件
                try:
                    shutil.copy2(source_path, target_path)
                    logger.debug(f"已复制: {source_path} -> {target_path}")
                    
                    # 更新哈希集合
                    if file_hash:
                        existing_file_hashes.add(file_hash)
                    if content_hash:
                        existing_content_hashes.add(content_hash)
                    
                    copied_images += 1
                except Exception as e:
                    logger.error(f"复制文件时出错: {source_path}, 错误: {e}")
                
                if total_images % 100 == 0:
                    logger.info(f"已处理: {total_images}, 已复制: {copied_images}, 已跳过: {skipped_images}")
    
    logger.info(f"处理完成! 总共: {total_images}, 已复制: {copied_images}, 已跳过: {skipped_images}")
    return copied_images, skipped_images

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