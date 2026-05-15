"""
缓存管理模块

解决内存缓存无过期问题，使用 TTLCache 实现自动过期。

缓存设计：
1. _token_storage: username → token（8小时，与 JWT 一致）
2. _user_info_storage: username → 用户信息（1小时，变化较少）
3. _current_user_cache: token → 用户 payload（8小时，与 token 生命周期一致）
"""

from cachetools import TTLCache
from typing import Optional, Dict, Any


class CacheManager:
    """
    缓存管理器
    
    使用 TTLCache 实现带过期时间的缓存：
    - token 缓存：8 小时（与 JWT 过期时间一致）
    - 用户信息缓存：1 小时（变化较少）
    - 当前用户缓存：8 小时（与 token 生命周期一致）
    """
    
    def __init__(
        self,
        token_ttl: int = 28800,      # 8 小时（秒）
        user_info_ttl: int = 3600,    # 1 小时（秒）
        max_size: int = 1000          # 最大缓存数量
    ):
        # Token 存储：username → token
        self._token_storage = TTLCache(maxsize=max_size, ttl=token_ttl)
        
        # 用户信息存储：username → user_info
        self._user_info_storage = TTLCache(maxsize=max_size, ttl=user_info_ttl)
        
        # 当前用户缓存：token → user_payload
        self._current_user_cache = TTLCache(maxsize=max_size, ttl=token_ttl)
    
    # ========== Token 存储 ==========
    
    def store_token(self, username: str, token: str) -> None:
        """存储用户 token"""
        self._token_storage[username] = token
    
    def get_token(self, username: str) -> Optional[str]:
        """获取用户 token"""
        return self._token_storage.get(username)
    
    def remove_token(self, username: str) -> None:
        """删除用户 token（登出时调用）"""
        self._token_storage.pop(username, None)
    
    # ========== 用户信息存储 ==========
    
    def store_user_info(self, username: str, user_info: Dict[str, Any]) -> None:
        """存储用户信息"""
        self._user_info_storage[username] = user_info
    
    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        return self._user_info_storage.get(username)
    
    def remove_user_info(self, username: str) -> None:
        """删除用户信息"""
        self._user_info_storage.pop(username, None)
    
    # ========== 当前用户缓存 ==========
    
    def store_current_user(self, token: str, user_payload: Dict[str, Any]) -> None:
        """缓存当前用户（用于快速认证）"""
        self._current_user_cache[token] = user_payload
    
    def get_current_user(self, token: str) -> Optional[Dict[str, Any]]:
        """获取缓存的当前用户"""
        return self._current_user_cache.get(token)
    
    def remove_current_user(self, token: str) -> None:
        """删除当前用户缓存"""
        self._current_user_cache.pop(token, None)
    
    # ========== 批量操作 ==========
    
    def clear_all(self) -> None:
        """清空所有缓存（测试用）"""
        self._token_storage.clear()
        self._user_info_storage.clear()
        self._current_user_cache.clear()
    
    def clear_user(self, username: str, token: str = None) -> None:
        """
        清除用户相关缓存（登出时调用）
        
        Args:
            username: 用户名
            token: 可选，如果有 token 也一并清除
        """
        self.remove_token(username)
        self.remove_user_info(username)
        if token:
            self.remove_current_user(token)
    
    # ========== 统计信息 ==========
    
    def get_stats(self) -> Dict[str, int]:
        """获取缓存统计信息"""
        return {
            "token_count": len(self._token_storage),
            "user_info_count": len(self._user_info_storage),
            "current_user_count": len(self._current_user_cache),
            "token_max_size": self._token_storage.maxsize,
            "user_info_max_size": self._user_info_storage.maxsize,
            "current_user_max_size": self._current_user_cache.maxsize,
        }


# 全局单例实例
cache_manager = CacheManager()


# 便捷函数（兼容旧代码）
def store_user_token(username: str, token: str, user_info: Dict = None) -> None:
    """存储用户 token 和信息"""
    cache_manager.store_token(username, token)
    if user_info:
        cache_manager.store_user_info(username, user_info)


def get_user_token(username: str) -> Optional[str]:
    """获取用户 token"""
    return cache_manager.get_token(username)


def get_user_info_cache(username: str) -> Optional[Dict]:
    """获取用户信息缓存"""
    return cache_manager.get_user_info(username)


# 导出
__all__ = [
    'CacheManager',
    'cache_manager',
    'store_user_token',
    'get_user_token',
    'get_user_info_cache',
]