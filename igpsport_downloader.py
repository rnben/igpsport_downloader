#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iGPSport 骑行数据下载器
用于批量下载iGPSport平台上的骑行数据FIT文件
"""

import requests
import os
import json
import time
from typing import List, Dict, Optional
from urllib.parse import urlparse

class IGPSportDownloader:
    def __init__(self, headers: Dict[str, str] = None):
        """
        初始化下载器
        
        Args:
            headers: 请求头，包含鉴权信息
        """
        self.session = requests.Session()
        self.base_url = "https://prod.zh.igpsport.com/service/web-gateway/web-analyze/activity"
        self.headers = headers or {}
        self.download_dir = "downloads"
        
        # 设置默认请求头
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }
        
        # 合并用户提供的headers
        for key, value in default_headers.items():
            if key not in self.headers:
                self.headers[key] = value
        
        self.session.headers.update(self.headers)
        
        # 创建下载目录
        os.makedirs(self.download_dir, exist_ok=True)
    
    def get_activities(self, page_no: int = 1, page_size: int = 20, req_type: int = 0, sort: int = 1) -> Dict:
        """
        获取活动列表
        
        Args:
            page_no: 页码，从1开始
            page_size: 每页数量
            req_type: 请求类型，0表示全部
            sort: 排序方式，1表示按时间倒序
            
        Returns:
            API响应的JSON数据
        """
        url = f"{self.base_url}/queryMyActivity"
        params = {
            'pageNo': page_no,
            'pageSize': page_size,
            'reqType': req_type,
            'sort': sort
        }
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"获取活动列表失败: {e}")
            return None
    
    def get_all_activities(self) -> List[Dict]:
        """
        获取所有活动
        
        Returns:
            所有活动的列表
        """
        all_activities = []
        page_no = 1
        
        print("正在获取活动列表...")
        
        while True:
            print(f"正在获取第 {page_no} 页...")
            
            data = self.get_activities(page_no=page_no)
            
            if not data or data.get('code') != 0:
                print(f"获取第 {page_no} 页失败: {data.get('message', '未知错误') if data else '网络错误'}")
                break
            
            activities = data.get('data', {}).get('rows', [])
            if not activities:
                print("没有更多活动了")
                break
            
            all_activities.extend(activities)
            
            # 检查是否还有下一页
            pagination = data.get('data', {})
            current_page = pagination.get('pageNo', 1)
            total_page = pagination.get('totalPage', 1)
            
            print(f"第 {page_no} 页获取成功，本页 {len(activities)} 个活动")
            
            if current_page >= total_page:
                print("已获取所有活动")
                break
            
            page_no += 1
            time.sleep(0.5)  # 避免请求过快
        
        print(f"总共获取到 {len(all_activities)} 个活动")
        return all_activities
    
    def get_download_url(self, ride_id: int) -> Optional[str]:
        """
        获取FIT文件的下载链接
        
        Args:
            ride_id: 活动ID
            
        Returns:
            下载链接URL，失败返回None
        """
        url = f"{self.base_url}/getDownloadUrl/{ride_id}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                return data.get('data')
            else:
                print(f"获取下载链接失败 (rideId: {ride_id}): {data.get('message', '未知错误')}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"获取下载链接失败 (rideId: {ride_id}): {e}")
            return None
    
    def download_file(self, url: str, filename: str) -> bool:
        """
        下载文件
        
        Args:
            url: 下载链接
            filename: 保存的文件名
            
        Returns:
            下载是否成功
        """
        filepath = os.path.join(self.download_dir, filename)
        
        # 如果文件已存在，跳过下载
        if os.path.exists(filepath):
            print(f"文件已存在，跳过下载: {filename}")
            return True
        
        try:
            print(f"正在下载: {filename}")
            response = self.session.get(url, timeout=60, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 显示下载进度
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\r下载进度: {progress:.1f}% ({downloaded}/{total_size} bytes)", end='', flush=True)
            
            print(f"\n下载完成: {filename}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"下载失败 {filename}: {e}")
            # 删除部分下载的文件
            if os.path.exists(filepath):
                os.remove(filepath)
            return False
    
    def download_all_activities(self, limit: Optional[int] = None, activity_type_filter: Optional[str] = None):
        """
        下载所有活动的FIT文件
        
        Args:
            limit: 限制下载数量，None表示全部下载
            activity_type_filter: 活动类型过滤，None表示全部
        """
        activities = self.get_all_activities()
        
        if not activities:
            print("没有找到活动")
            return
        
        # 应用过滤器
        if activity_type_filter:
            filtered_activities = [a for a in activities if activity_type_filter.lower() in a.get('title', '').lower()]
            print(f"按标题过滤后剩余 {len(filtered_activities)} 个活动")
            activities = filtered_activities
        
        # 应用数量限制
        if limit:
            activities = activities[:limit]
            print(f"限制下载数量为 {len(activities)} 个")
        
        success_count = 0
        failed_count = 0
        
        for i, activity in enumerate(activities, 1):
            ride_id = activity.get('rideId')
            title = activity.get('title', f'活动_{ride_id}')
            start_time = activity.get('startTime', '').replace('.', '-').replace(' ', '_')
            
            print(f"\n[{i}/{len(activities)}] 处理活动: {title} (rideId: {ride_id})")
            
            # 获取下载链接
            download_url = self.get_download_url(ride_id)
            if not download_url:
                failed_count += 1
                continue
            
            # 生成文件名
            parsed_url = urlparse(download_url)
            original_filename = os.path.basename(parsed_url.path)
            if not original_filename or '.' not in original_filename:
                original_filename = f"{ride_id}.fit"
            
            # 使用更描述性的文件名
            filename = f"{start_time}_{title}_{ride_id}_{original_filename}"
            # 清理文件名中的非法字符
            filename = ''.join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            
            # 下载文件
            if self.download_file(download_url, filename):
                success_count += 1
            else:
                failed_count += 1
            
            # 避免请求过快
            time.sleep(0.5)
        
        print(f"\n下载完成! 成功: {success_count}, 失败: {failed_count}")
        print(f"文件保存在: {os.path.abspath(self.download_dir)}")


def main():
    """
    主函数 - 用户配置区域
    """
    print("=== iGPSport 骑行数据下载器 ===")
    
    # ========================================
    # 用户配置区域 - 请在这里填写你的请求头
    # ========================================
    
    # 从浏览器开发者工具中复制完整的请求头
    # 包括但不限于: Cookie, Authorization, User-Agent 等
    user_headers = {
        # 在这里粘贴你的浏览器请求头
        # 示例:
        # 'Cookie': 'your_cookie_here',
        # 'Authorization': 'Bearer your_token_here',
        # 'User-Agent': 'your_user_agent_here',
    }
    
    # 检查用户是否配置了headers
    if not any(user_headers.values()):
        print("⚠️  警告: 你还没有配置请求头!")
        print("请在脚本中的 user_headers 字典中填写你的浏览器请求头")
        print("通常包括: Cookie, Authorization 等字段")
        
        # 询问用户是否继续
        choice = input("\n是否继续运行? (y/N): ").strip().lower()
        if choice != 'y':
            print("脚本已退出")
            return
    
    # ========================================
    # 下载配置
    # ========================================
    
    # 限制下载数量，None表示下载全部
    download_limit = None  # 例如: 10 表示只下载前10个活动
    
    # 活动标题过滤，None表示不过滤
    # 例如: '骑行' 只下载标题包含'骑行'的活动
    title_filter = None
    
    # ========================================
    # 开始执行
    # ========================================
    
    try:
        # 创建下载器实例
        downloader = IGPSportDownloader(headers=user_headers)
        
        # 开始下载
        downloader.download_all_activities(
            limit=download_limit,
            activity_type_filter=title_filter
        )
        
    except KeyboardInterrupt:
        print("\n\n用户中断下载")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
