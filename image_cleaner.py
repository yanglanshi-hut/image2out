#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import hashlib
import argparse
import sqlite3
import gc
from datetime import datetime
from PIL import Image
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("image_cleaner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ImageCleaner:
    def __init__(self, db_path="image_cleaner.db"):
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """初始化SQLite数据库来存储图片信息"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        # 创建图片信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE,
                filename TEXT,
                size INTEGER,
                file_hash TEXT,
                content_hash TEXT,
                is_source BOOLEAN,
                deleted BOOLEAN DEFAULT FALSE,
                created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建索引以提高查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON images(file_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON images(content_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_filename ON images(filename)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_source ON images(is_source)')
        
        self.conn.commit()
        
    def close_database(self):
        """关闭数据库连接"""
        if hasattr(self, 'conn'):
            self.conn.close()
            
    def clear_database(self):
        """清空数据库表"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM images')
        self.conn.commit()
        
    def calculate_file_hash(self, file_path, chunk_size=8192):
        """
        计算文件的MD5哈希值，使用流式读取减少内存使用
        """
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败: {file_path}, 错误: {e}")
            return None

    def calculate_image_content_hash(self, image_path):
        """
        计算图片的内容哈希值（感知哈希）
        """
        try:
            with Image.open(image_path) as img:
                # 转换为小缩略图并转为灰度
                img = img.resize((8, 8), Image.Resampling.LANCZOS).convert('L')
                # 计算像素平均值
                pixels = list(img.getdata())
                avg_pixel = sum(pixels) / len(pixels)
                # 基于平均值生成位序列
                bits = ''.join(['1' if pixel >= avg_pixel else '0' for pixel in pixels])
                # 将位序列转换为十六进制字符串
                content_hash = hex(int(bits, 2))[2:].zfill(16)
                return content_hash
        except Exception as e:
            logger.debug(f"无法计算图片内容哈希: {image_path}, 错误: {e}")
            return None

    def calculate_image_hash(self, image_path, use_content_hash=True):
        """
        计算图片的哈希值（文件哈希 + 内容哈希）
        """
        try:
            # 文件哈希
            file_hash = self.calculate_file_hash(image_path)
            if file_hash is None:
                return None, None
                
            # 内容哈希
            content_hash = None
            if use_content_hash:
                content_hash = self.calculate_image_content_hash(image_path)
                
            return file_hash, content_hash
            
        except Exception as e:
            logger.error(f"计算图片哈希失败: {image_path}, 错误: {e}")
            return None, None

    def is_image_file(self, file_path):
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
            return False

    def should_skip_directory(self, dir_path):
        """判断是否应该跳过该目录"""
        skip_dirs = {'@eaDir', '.DS_Store', 'Thumbs.db', '@Recycle', '#recycle', '.thumbnail'}
        dir_name = os.path.basename(dir_path)
        return dir_name in skip_dirs or dir_name.startswith('.')

    def scan_source_directory(self, directory, use_content_hash=True):
        """
        扫描源目录并记录所有图片信息到数据库
        """
        logger.info(f"正在扫描源目录: {directory}")
        
        # 统计图片文件数量
        image_count = 0
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not self.should_skip_directory(os.path.join(root, d))]
            for filename in files:
                file_path = os.path.join(root, filename)
                if self.is_image_file(file_path):
                    image_count += 1
        
        logger.info(f"源目录中共有 {image_count} 张图片")
        
        processed_count = 0
        cursor = self.conn.cursor()
        
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not self.should_skip_directory(os.path.join(root, d))]
            
            for filename in files:
                file_path = os.path.join(root, filename)
                
                # 只处理图片文件
                if not self.is_image_file(file_path):
                    continue
                
                processed_count += 1
                
                # 显示进度
                if processed_count % 100 == 0 or processed_count == image_count:
                    logger.info(f"正在处理: {processed_count}/{image_count} ({processed_count/image_count*100:.1f}%)")
                    # 强制垃圾回收以释放内存
                    gc.collect()
                
                try:
                    file_size = os.path.getsize(file_path)
                    
                    # 计算哈希值
                    file_hash, content_hash = self.calculate_image_hash(file_path, use_content_hash)
                    
                    if file_hash is None:
                        logger.warning(f"跳过无法处理的文件: {file_path}")
                        continue
                    
                    # 存储到数据库
                    cursor.execute('''
                        INSERT OR IGNORE INTO images 
                        (path, filename, size, file_hash, content_hash, is_source)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (file_path, os.path.basename(filename), file_size, 
                          file_hash, content_hash, True))
                    
                    # 每100个文件提交一次，减少内存使用
                    if processed_count % 100 == 0:
                        self.conn.commit()
                        
                except Exception as e:
                    logger.error(f"处理文件失败: {file_path}, 错误: {e}")
                    continue
        
        # 最终提交
        self.conn.commit()
        
        logger.info(f"源目录扫描完成，共记录 {processed_count} 张图片")
        return processed_count

    def find_and_delete_from_target(self, target_directory, use_content_hash=True, dry_run=False):
        """
        在目标目录中寻找与源目录相同的图片并删除
        """
        logger.info(f"正在扫描目标目录寻找重复图片: {target_directory}")
        
        # 统计目标目录中的图片文件数量
        target_image_count = 0
        for root, dirs, files in os.walk(target_directory):
            dirs[:] = [d for d in dirs if not self.should_skip_directory(os.path.join(root, d))]
            for filename in files:
                file_path = os.path.join(root, filename)
                if self.is_image_file(file_path):
                    target_image_count += 1
        
        logger.info(f"目标目录中共有 {target_image_count} 张图片")
        
        processed_count = 0
        deleted_count = 0
        cursor = self.conn.cursor()
        
        for root, dirs, files in os.walk(target_directory):
            dirs[:] = [d for d in dirs if not self.should_skip_directory(os.path.join(root, d))]
            
            for filename in files:
                file_path = os.path.join(root, filename)
                
                # 只处理图片文件
                if not self.is_image_file(file_path):
                    continue
                
                processed_count += 1
                
                # 显示进度
                if processed_count % 100 == 0 or processed_count == target_image_count:
                    logger.info(f"正在检查: {processed_count}/{target_image_count} ({processed_count/target_image_count*100:.1f}%)")
                    gc.collect()
                
                try:
                    # 计算当前文件的哈希值
                    file_hash, content_hash = self.calculate_image_hash(file_path, use_content_hash)
                    
                    if file_hash is None:
                        logger.warning(f"跳过无法处理的文件: {file_path}")
                        continue
                    
                    # 检查是否在源目录的记录中存在
                    found_in_source = False
                    
                    # 首先按文件哈希查找
                    cursor.execute('''
                        SELECT COUNT(*) FROM images 
                        WHERE file_hash = ? AND is_source = TRUE
                    ''', (file_hash,))
                    
                    if cursor.fetchone()[0] > 0:
                        found_in_source = True
                        match_type = "文件哈希"
                    elif content_hash and use_content_hash:
                        # 如果文件哈希没找到，再按内容哈希查找
                        cursor.execute('''
                            SELECT COUNT(*) FROM images 
                            WHERE content_hash = ? AND is_source = TRUE AND content_hash IS NOT NULL
                        ''', (content_hash,))
                        
                        if cursor.fetchone()[0] > 0:
                            found_in_source = True
                            match_type = "内容哈希"
                    
                    if found_in_source:
                        if dry_run:
                            logger.info(f"[模拟] 将删除重复图片: {file_path} (匹配类型: {match_type})")
                        else:
                            try:
                                os.remove(file_path)
                                logger.info(f"删除重复图片: {file_path} (匹配类型: {match_type})")
                                deleted_count += 1
                                
                                # 记录删除操作到数据库
                                cursor.execute('''
                                    INSERT OR IGNORE INTO images 
                                    (path, filename, size, file_hash, content_hash, is_source, deleted)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                ''', (file_path, os.path.basename(filename), 
                                      os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                                      file_hash, content_hash, False, True))
                                
                            except Exception as e:
                                logger.error(f"删除文件失败: {file_path}, 错误: {e}")
                    
                    # 每100个文件提交一次数据库更改
                    if processed_count % 100 == 0:
                        self.conn.commit()
                        
                except Exception as e:
                    logger.error(f"处理文件失败: {file_path}, 错误: {e}")
                    continue
        
        # 最终提交
        self.conn.commit()
        
        action_text = "模拟删除" if dry_run else "删除"
        logger.info(f"目标目录处理完成，共{action_text}了 {deleted_count} 张重复图片")
        return deleted_count

    def generate_report(self):
        """生成处理报告"""
        cursor = self.conn.cursor()
        
        # 统计源目录图片数量
        cursor.execute('SELECT COUNT(*) FROM images WHERE is_source = TRUE')
        source_count = cursor.fetchone()[0]
        
        # 统计删除的图片数量
        cursor.execute('SELECT COUNT(*) FROM images WHERE deleted = TRUE')
        deleted_count = cursor.fetchone()[0]
        
        logger.info("\n=== 处理报告 ===")
        logger.info(f"源目录图片总数: {source_count}")
        logger.info(f"删除的重复图片数量: {deleted_count}")
        
        # 获取删除的文件列表
        cursor.execute('SELECT path FROM images WHERE deleted = TRUE ORDER BY path')
        deleted_files = cursor.fetchall()
        
        if deleted_files:
            logger.info("\n删除的文件列表:")
            for (file_path,) in deleted_files:
                logger.info(f"  - {file_path}")

def main():
    parser = argparse.ArgumentParser(description='图片清理工具 - 记录源目录图片，删除目标目录中的重复图片')
    parser.add_argument('--source', '-s', required=True, help='源目录路径（记录其中的图片）')
    parser.add_argument('--target', '-t', required=True, help='目标目录路径（删除其中的重复图片）')
    parser.add_argument('--fast', action='store_true', help='使用快速模式（仅文件哈希，不使用内容哈希）')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行，不实际删除文件')
    parser.add_argument('--db', default='image_cleaner.db', help='数据库文件路径（默认：image_cleaner.db）')
    parser.add_argument('--keep-db', action='store_true', help='保留数据库文件，不在完成后删除')
    
    args = parser.parse_args()
    
    # 检查目录是否存在
    if not os.path.exists(args.source):
        logger.error(f"源目录不存在: {args.source}")
        return 1
    
    if not os.path.exists(args.target):
        logger.error(f"目标目录不存在: {args.target}")
        return 1
    
    # 创建图片清理器实例
    cleaner = ImageCleaner(args.db)
    
    try:
        logger.info("=== 图片清理工具启动 ===")
        logger.info(f"源目录: {args.source}")
        logger.info(f"目标目录: {args.target}")
        logger.info(f"模式: {'快速模式（仅文件哈希）' if args.fast else '精确模式（文件哈希+内容哈希）'}")
        logger.info(f"运行模式: {'模拟运行' if args.dry_run else '实际删除'}")
        logger.info(f"数据库文件: {args.db}")
        
        # 清空数据库
        cleaner.clear_database()
        
        # 步骤1：扫描源目录，记录所有图片
        source_count = cleaner.scan_source_directory(args.source, not args.fast)
        
        if source_count == 0:
            logger.warning("源目录中没有找到图片文件")
            return 0
        
        # 步骤2：在目标目录中寻找并删除重复图片
        deleted_count = cleaner.find_and_delete_from_target(args.target, not args.fast, args.dry_run)
        
        # 生成报告
        cleaner.generate_report()
        
        logger.info("=== 图片清理工具完成 ===")
        action_text = "模拟删除" if args.dry_run else "删除"
        logger.info(f"总计{action_text}了 {deleted_count} 张重复图片")
        
    finally:
        # 关闭数据库连接
        cleaner.close_database()
        
        # 根据用户选择决定是否删除数据库文件
        if not args.keep_db and os.path.exists(args.db):
            try:
                os.remove(args.db)
                logger.info(f"已删除临时数据库文件: {args.db}")
            except Exception as e:
                logger.warning(f"无法删除临时数据库文件 {args.db}: {e}")
        elif args.keep_db and os.path.exists(args.db):
            logger.info(f"数据库文件已保留: {args.db}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
