#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import hashlib
import shutil
import argparse
import sqlite3
import gc
import threading
import time
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

class MediaOrganizer:
    def __init__(self, db_path="media_organizer.db"):
        self.db_path = db_path
        self.init_database()
        self.processed_count = 0
        self.start_time = None
        
    def init_database(self):
        """初始化SQLite数据库来存储文件信息，减少内存使用"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        
        # 优化SQLite设置
        cursor.execute('PRAGMA journal_mode = WAL')
        cursor.execute('PRAGMA synchronous = NORMAL')
        cursor.execute('PRAGMA cache_size = 10000')
        cursor.execute('PRAGMA temp_store = MEMORY')
        
        # 创建文件信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE,
                filename TEXT,
                file_type TEXT,
                size INTEGER,
                file_hash TEXT,
                content_hash TEXT,
                is_target BOOLEAN,
                processed BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # 创建索引以提高查询性能
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON files(file_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_hash ON files(content_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_filename ON files(filename)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_type ON files(file_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_processed ON files(processed)')
        
        self.conn.commit()
        
    def close_database(self):
        """关闭数据库连接"""
        if hasattr(self, 'conn'):
            self.conn.close()
            
    def clear_database(self):
        """清空数据库表"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM files')
        self.conn.commit()
        
    def calculate_file_hash(self, file_path, chunk_size=65536):
        """
        计算文件的MD5哈希值，使用更大的块大小提高性能
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

    def calculate_image_hash_fast(self, image_path):
        """
        快速计算图片的感知哈希值，优化性能
        """
        try:
            # 文件哈希
            file_hash = self.calculate_file_hash(image_path)
            if file_hash is None:
                return None, None
                
            # 内容哈希 - 使用最快的算法
            content_hash = None
            try:
                with Image.open(image_path) as img:
                    # 使用最快的重采样方法和最小尺寸
                    img = img.convert('L').resize((8, 8), Image.Resampling.NEAREST)
                    pixels = list(img.getdata())
                    avg_pixel = sum(pixels) >> 6  # 除以64的快速方法
                    
                    # 使用位操作快速生成哈希
                    bits = 0
                    for i, pixel in enumerate(pixels):
                        if pixel >= avg_pixel:
                            bits |= (1 << i)
                    content_hash = f"{bits:016x}"
            except Exception:
                pass
                
            return file_hash, content_hash
            
        except Exception as e:
            logger.error(f"计算图片哈希失败: {image_path}, 错误: {e}")
            return None, None

    def get_file_type(self, file_path):
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

    def is_image_file_fast(self, file_path):
        """快速判断文件是否为图片文件，减少IO操作"""
        if self.get_file_type(file_path) != 'image':
            return False
        
        # 跳过额外验证以提高速度，仅依赖扩展名
        return True

    def should_skip_directory(self, dir_path):
        """判断是否应该跳过该目录"""
        skip_dirs = {'@eaDir', '.DS_Store', 'Thumbs.db', '@Recycle', '#recycle', '.thumbnail', 'mp4', 'zip'}
        dir_name = os.path.basename(dir_path)
        return dir_name in skip_dirs or dir_name.startswith('.')

    def get_target_directory(self, target_dir, file_type):
        """
        根据文件类型获取目标目录
        """
        if file_type == 'video':
            return os.path.join(target_dir, 'mp4')
        elif file_type == 'archive':
            return os.path.join(target_dir, 'zip')
        else:
            return target_dir

    def ensure_directory_exists(self, dir_path):
        """
        确保目录存在，如果不存在则创建
        """
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            logger.info(f"创建目录: {dir_path}")

    def show_progress(self, processed, total, start_time=None):
        """显示进度信息"""
        percentage = processed / total * 100
        if start_time:
            elapsed = time.time() - start_time
            if processed > 0:
                estimated_total = elapsed * total / processed
                remaining = estimated_total - elapsed
                logger.info(f"正在处理: {processed}/{total} ({percentage:.1f}%) - "
                          f"已用时: {elapsed/60:.1f}分钟, 预计剩余: {remaining/60:.1f}分钟")
            else:
                logger.info(f"正在处理: {processed}/{total} ({percentage:.1f}%)")
        else:
            logger.info(f"正在处理: {processed}/{total} ({percentage:.1f}%)")

    def scan_directory(self, directory, is_target=False, use_content_hash=True):
        """
        扫描目录并将文件信息存储到数据库
        """
        logger.info(f"正在扫描{'目标' if is_target else '源'}目录: {directory}")
        
        # 统计文件数量
        file_count = 0
        file_list = []
        
        logger.info("正在统计文件数量...")
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if not self.should_skip_directory(os.path.join(root, d))]
            for filename in files:
                file_path = os.path.join(root, filename)
                file_type = self.get_file_type(file_path)
                if file_type in ['image', 'video', 'archive']:
                    file_list.append((file_path, file_type))
                    file_count += 1
        
        logger.info(f"{'目标' if is_target else '源'}目录中共有 {file_count} 个可处理的文件")
        
        if file_count == 0:
            return
        
        processed_count = 0
        cursor = self.conn.cursor()
        start_time = time.time()
        
        # 批量处理文件
        batch_size = 1000
        batch_data = []
        
        for file_path, file_type in file_list:
            # 验证图片文件
            if file_type == 'image' and not self.is_image_file_fast(file_path):
                continue
            
            processed_count += 1
            
            # 显示进度
            if processed_count % 500 == 0 or processed_count == file_count:
                self.show_progress(processed_count, file_count, start_time)
                gc.collect()
            
            try:
                file_size = os.path.getsize(file_path)
                
                # 计算哈希值
                if file_type == 'image' and use_content_hash:
                    file_hash, content_hash = self.calculate_image_hash_fast(file_path)
                else:
                    file_hash = self.calculate_file_hash(file_path)
                    content_hash = None
                
                if file_hash is None:
                    logger.warning(f"跳过无法处理的文件: {file_path}")
                    continue
                
                # 添加到批处理列表
                batch_data.append((
                    file_path, os.path.basename(file_path), file_type, 
                    file_size, file_hash, content_hash, is_target
                ))
                
                # 批量插入数据库
                if len(batch_data) >= batch_size:
                    cursor.executemany('''
                        INSERT OR IGNORE INTO files 
                        (path, filename, file_type, size, file_hash, content_hash, is_target)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', batch_data)
                    self.conn.commit()
                    batch_data = []
                    
            except Exception as e:
                logger.error(f"处理文件失败: {file_path}, 错误: {e}")
                continue
        
        # 处理剩余的批处理数据
        if batch_data:
            cursor.executemany('''
                INSERT OR IGNORE INTO files 
                (path, filename, file_type, size, file_hash, content_hash, is_target)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', batch_data)
            self.conn.commit()
        
        # 统计结果
        cursor.execute('''
            SELECT file_type, COUNT(*) FROM files 
            WHERE is_target = ? 
            GROUP BY file_type
        ''', (is_target,))
        
        results = cursor.fetchall()
        type_counts = {file_type: count for file_type, count in results}
        
        logger.info(f"{'目标' if is_target else '源'}目录扫描完成: "
                   f"图片 {type_counts.get('image', 0)} 张, "
                   f"视频 {type_counts.get('video', 0)} 个, "
                   f"压缩文件 {type_counts.get('archive', 0)} 个")

    def process_duplicates(self, target_dir):
        """
        处理重复文件，批量处理以减少内存使用
        """
        cursor = self.conn.cursor()
        
        total_copied = 0
        total_skipped = 0
        total_replaced = 0
        total_deleted = 0
        
        # 按文件类型处理
        for file_type in ['image', 'video', 'archive']:
            logger.info(f"\n开始处理 {file_type} 文件...")
            
            type_target_dir = self.get_target_directory(target_dir, file_type)
            self.ensure_directory_exists(type_target_dir)
            
            copied_count = 0
            skipped_count = 0
            replaced_count = 0
            deleted_count = 0
            
            # 获取所有文件哈希值（分批处理）
            cursor.execute('''
                SELECT DISTINCT file_hash FROM files 
                WHERE file_type = ? AND file_hash IS NOT NULL
            ''', (file_type,))
            
            hash_values = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"处理 {len(hash_values)} 个不同的{file_type}文件哈希组...")
            
            start_time = time.time()
            for i, hash_value in enumerate(hash_values):
                if i % 500 == 0 and i > 0:
                    self.show_progress(i, len(hash_values), start_time)
                    gc.collect()
                
                # 获取具有相同哈希值的所有文件
                cursor.execute('''
                    SELECT path, size, is_target, processed FROM files 
                    WHERE file_hash = ? AND file_type = ?
                    ORDER BY size DESC, is_target DESC
                ''', (hash_value, file_type))
                
                duplicate_files = cursor.fetchall()
                
                if len(duplicate_files) <= 1:
                    # 没有重复文件
                    if len(duplicate_files) == 1:
                        path, size, is_target, processed = duplicate_files[0]
                        if not is_target and not processed:
                            # 源目录中的唯一文件，复制到目标目录
                            target_path = os.path.join(type_target_dir, os.path.basename(path))
                            
                            # 处理文件名冲突
                            counter = 1
                            while os.path.exists(target_path):
                                name, ext = os.path.splitext(os.path.basename(path))
                                target_path = os.path.join(type_target_dir, f"{name}_{counter}{ext}")
                                counter += 1
                            
                            try:
                                shutil.copy2(path, target_path)
                                copied_count += 1
                                cursor.execute('UPDATE files SET processed = TRUE WHERE path = ?', (path,))
                            except Exception as e:
                                logger.error(f"复制文件失败: {path}, 错误: {e}")
                else:
                    # 有重复文件，选择最大的
                    largest_file = duplicate_files[0]
                    largest_path, largest_size, largest_is_target, largest_processed = largest_file
                    
                    if largest_is_target:
                        # 最大文件已在目标目录中
                        for path, size, is_target, processed in duplicate_files[1:]:
                            if is_target and not processed:
                                try:
                                    os.remove(path)
                                    deleted_count += 1
                                    cursor.execute('UPDATE files SET processed = TRUE WHERE path = ?', (path,))
                                except Exception as e:
                                    logger.error(f"删除文件失败: {path}, 错误: {e}")
                        
                        # 跳过源目录中的重复文件
                        for path, size, is_target, processed in duplicate_files:
                            if not is_target and not processed:
                                skipped_count += 1
                                cursor.execute('UPDATE files SET processed = TRUE WHERE path = ?', (path,))
                        
                        cursor.execute('UPDATE files SET processed = TRUE WHERE path = ?', (largest_path,))
                        
                    else:
                        # 最大文件在源目录中，需要复制并替换
                        for path, size, is_target, processed in duplicate_files:
                            if is_target and not processed:
                                try:
                                    os.remove(path)
                                    deleted_count += 1
                                    cursor.execute('UPDATE files SET processed = TRUE WHERE path = ?', (path,))
                                except Exception as e:
                                    logger.error(f"删除文件失败: {path}, 错误: {e}")
                        
                        # 复制最大的文件
                        if not largest_processed:
                            target_path = os.path.join(type_target_dir, os.path.basename(largest_path))
                            
                            counter = 1
                            while os.path.exists(target_path):
                                name, ext = os.path.splitext(os.path.basename(largest_path))
                                target_path = os.path.join(type_target_dir, f"{name}_{counter}{ext}")
                                counter += 1
                            
                            try:
                                shutil.copy2(largest_path, target_path)
                                replaced_count += 1
                                cursor.execute('UPDATE files SET processed = TRUE WHERE path = ?', (largest_path,))
                            except Exception as e:
                                logger.error(f"复制文件失败: {largest_path}, 错误: {e}")
                        
                        # 跳过源目录中其他较小的重复文件
                        for path, size, is_target, processed in duplicate_files[1:]:
                            if not is_target and not processed:
                                skipped_count += 1
                                cursor.execute('UPDATE files SET processed = TRUE WHERE path = ?', (path,))
                
                # 定期提交数据库更改
                if i % 100 == 0:
                    self.conn.commit()
            
            # 最终提交
            self.conn.commit()
            
            logger.info(f"{file_type} 处理完成! 复制: {copied_count}, 替换: {replaced_count}, 跳过: {skipped_count}, 删除重复: {deleted_count}")
            
            total_copied += copied_count
            total_skipped += skipped_count
            total_replaced += replaced_count
            total_deleted += deleted_count
        
        return total_copied + total_replaced, total_skipped, total_deleted

    def process_media_files(self, source_dir, target_dir, use_content_hash=True):
        """
        处理媒体文件：找出所有文件，按类型分类存储，去重，并保留最大的文件
        """
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            logger.info(f"创建目标目录: {target_dir}")

        # 清空数据库
        self.clear_database()
        
        # 扫描目标目录
        self.scan_directory(target_dir, is_target=True, use_content_hash=use_content_hash)
        
        # 扫描源目录
        self.scan_directory(source_dir, is_target=False, use_content_hash=use_content_hash)
        
        # 处理重复文件
        return self.process_duplicates(target_dir)

def main():
    parser = argparse.ArgumentParser(description='媒体文件去重和整理工具（支持图片、视频、压缩文件）- 高性能优化版')
    parser.add_argument('--source', '-s', required=True, nargs='+', help='源文件目录（可指定多个）')
    parser.add_argument('--target', '-t', required=True, nargs='+', help='目标文件目录（可指定多个）')
    parser.add_argument('--fast', action='store_true', help='使用快速模式（仅文件哈希，不检测图片内容相似性）')
    parser.add_argument('--db', default='media_organizer.db', help='数据库文件路径（默认：media_organizer.db）')
    
    args = parser.parse_args()
    
    # 创建媒体整理器实例
    organizer = MediaOrganizer(args.db)
    
    try:
        logger.info("=== 媒体文件去重和整理工具启动（高性能优化版）===")
        logger.info(f"源目录: {', '.join(args.source)}")
        logger.info(f"目标目录: {', '.join(args.target)}")
        logger.info(f"模式: {'快速模式' if args.fast else '精确模式(包含图片内容比较)'}")
        logger.info(f"数据库文件: {args.db}")
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
        
        start_time = time.time()
        
        for i, source_dir in enumerate(args.source):
            # 确定对应的目标目录
            if len(args.target) == 1:
                target_dir = args.target[0]
            else:
                target_dir = args.target[i]
            
            logger.info(f"\n处理第 {i+1}/{len(args.source)} 个任务: {source_dir} -> {target_dir}")
            copied, skipped, deleted = organizer.process_media_files(source_dir, target_dir, not args.fast)
            total_copied += copied
            total_skipped += skipped
            total_deleted += deleted
        
        total_time = time.time() - start_time
        
        logger.info("=== 媒体文件去重和整理工具完成（高性能优化版）===")
        logger.info(f"总计处理了 {total_copied} 个文件")
        logger.info(f"总计跳过了 {total_skipped} 个重复文件")
        logger.info(f"总计删除了 {total_deleted} 个重复文件")
        logger.info(f"总用时: {total_time/60:.1f} 分钟")
        
    finally:
        # 关闭数据库连接
        organizer.close_database()
        
        # 可选：删除临时数据库文件
        if os.path.exists(args.db):
            try:
                os.remove(args.db)
                logger.info(f"已删除临时数据库文件: {args.db}")
            except Exception as e:
                logger.warning(f"无法删除临时数据库文件 {args.db}: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
