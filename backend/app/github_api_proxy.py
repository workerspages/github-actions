"""
GitHub API 代理模块 - 简化版

通过 Monkey Patching 拦截原脚本的 SecretUpdater 类，
将对 GitHub API 的调用转发到内部 API。

原理：
1. 在脚本执行前导入此模块
2. 此模块会 patch requests 库的 put/get 方法
3. 当检测到对 api.github.com/repos/.../secrets/... 的 PUT 请求时
4. 解析请求参数，提取 secret 名称
5. 调用内部 API 更新任务独享 Secrets
"""

import os
import json
import functools

# 内部 API 配置
FLUX_TOKEN = os.environ.get('FLUX_TOKEN', '')
FLUX_API_URL = os.environ.get('FLUX_API_URL', 'http://127.0.0.1:8000')
FLUX_SCRIPT_ID = os.environ.get('FLUX_SCRIPT_ID', '')

# 存储待更新的 secret 值（在加密前拦截）
_pending_secrets = {}


def _patch_nacl():
    """Patch PyNaCl 库，在加密时捕获原始值"""
    try:
        from nacl.public import SealedBox
        
        _original_encrypt = SealedBox.encrypt
        
        @functools.wraps(_original_encrypt)
        def _patched_encrypt(self, plaintext):
            # 保存原始值
            if isinstance(plaintext, bytes):
                _pending_secrets['_last_value'] = plaintext.decode('utf-8')
            else:
                _pending_secrets['_last_value'] = str(plaintext)
            # 返回一个假的加密值（不会真正使用）
            return b'FLUX_PROXY_PLACEHOLDER'
        
        SealedBox.encrypt = _patched_encrypt
    except ImportError:
        pass


def _patch_requests():
    """Patch requests 库，拦截 GitHub API 调用"""
    try:
        import requests as req_module
    except ImportError:
        return
    
    _original_put = req_module.put
    _original_get = req_module.get
    
    @functools.wraps(_original_put)
    def _patched_put(url, **kwargs):
        # 拦截 GitHub Secrets API PUT 请求
        if 'api.github.com' in url and '/actions/secrets/' in url:
            # 提取 secret 名称
            parts = url.split('/actions/secrets/')
            if len(parts) == 2:
                secret_name = parts[1].split('?')[0].split('/')[0]
                secret_value = _pending_secrets.get('_last_value', '')
                
                if secret_value and FLUX_SCRIPT_ID:
                    print(f"[API Proxy] 拦截 PUT secrets/{secret_name}")
                    try:
                        # 调用内部 API 更新任务独享 Secrets
                        resp = _original_put(
                            f"{FLUX_API_URL}/api/scripts/{FLUX_SCRIPT_ID}/secrets/{secret_name}",
                            json={"value": secret_value},
                            headers={"Authorization": f"Bearer {FLUX_TOKEN}"},
                            timeout=30
                        )
                        
                        # 返回模拟的成功响应
                        class MockResponse:
                            status_code = 204 if resp.status_code == 200 else resp.status_code
                            text = ''
                            def json(self): return {}
                            def raise_for_status(self): 
                                if self.status_code >= 400:
                                    raise Exception(f"API error: {self.status_code}")
                        
                        if resp.status_code == 200:
                            print(f"[API Proxy] 成功更新 {secret_name}")
                        return MockResponse()
                    except Exception as e:
                        print(f"[API Proxy] 更新失败: {e}")
        
        return _original_put(url, **kwargs)
    
    @functools.wraps(_original_get)
    def _patched_get(url, **kwargs):
        # 拦截 GitHub Secrets 公钥请求
        if 'api.github.com' in url and '/actions/secrets/public-key' in url:
            print("[API Proxy] 拦截 GET public-key")
            
            class MockResponse:
                status_code = 200
                text = ''
                def json(self):
                    # 返回假公钥（将触发加密流程，我们在加密时捕获原始值）
                    return {
                        'key_id': 'flux_internal',
                        'key': 'MDEwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA='
                    }
                def raise_for_status(self): pass
            
            return MockResponse()
        
        return _original_get(url, **kwargs)
    
    req_module.put = _patched_put
    req_module.get = _patched_get
    print("[API Proxy] GitHub API 代理已启用")


def init_proxy():
    """初始化代理"""
    if FLUX_TOKEN and FLUX_SCRIPT_ID:
        _patch_nacl()
        _patch_requests()
        # 注入假的 REPO_TOKEN 和 GITHUB_REPOSITORY（让原脚本认为配置正确）
        if not os.environ.get('REPO_TOKEN'):
            os.environ['REPO_TOKEN'] = 'flux_proxy_token'
        if not os.environ.get('GITHUB_REPOSITORY'):
            os.environ['GITHUB_REPOSITORY'] = 'flux/internal'


# 自动初始化
init_proxy()
