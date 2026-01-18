"""
GitHub API 代理模块

自动拦截对 api.github.com 的请求，转发到内部 API。
让原脚本无需修改即可在私有化环境中运行。

原理：
1. 在脚本执行前导入此模块
2. Patch PyNaCl 的 SealedBox.encrypt() 捕获原始值
3. Patch requests.get/put 拦截 GitHub API 调用
4. 将 Secret 更新请求转发到内部 API
"""

import os
import functools

# 内部 API 配置
FLUX_TOKEN = os.environ.get('FLUX_TOKEN', '')
FLUX_API_URL = os.environ.get('FLUX_API_URL', 'http://127.0.0.1:8000')
FLUX_SCRIPT_ID = os.environ.get('FLUX_SCRIPT_ID', '')

# 存储待更新的 secret 值（在加密前拦截）
_pending_secrets = {}
_proxy_initialized = False


def _patch_nacl():
    """Patch PyNaCl 库，在加密时捕获原始值"""
    try:
        from nacl.public import SealedBox
        
        _original_encrypt = SealedBox.encrypt
        
        @functools.wraps(_original_encrypt)
        def _patched_encrypt(self, plaintext):
            # 保存原始值（这是 Secret 的明文值）
            if isinstance(plaintext, bytes):
                _pending_secrets['_last_value'] = plaintext.decode('utf-8')
            else:
                _pending_secrets['_last_value'] = str(plaintext)
            print(f"[API Proxy] 捕获到 Secret 值")
            # 返回假的加密数据（不会真正发送到 GitHub）
            return b'FLUX_ENCRYPTED_PLACEHOLDER'
        
        SealedBox.encrypt = _patched_encrypt
        print("[API Proxy] PyNaCl SealedBox.encrypt 已拦截")
    except ImportError:
        print("[API Proxy] PyNaCl 未安装，跳过 patch")


def _patch_nacl_publickey():
    """Patch PublicKey 构造函数，接受任意公钥"""
    try:
        from nacl import public, encoding
        
        _original_init = public.PublicKey.__init__
        
        @functools.wraps(_original_init)
        def _patched_init(self, public_key, encoder=encoding.RawEncoder):
            # 使用一个有效的 32 字节假公钥
            fake_key = b'\x00' * 32
            try:
                _original_init(self, fake_key, encoding.RawEncoder)
            except:
                # 如果失败，忽略错误
                pass
        
        public.PublicKey.__init__ = _patched_init
        print("[API Proxy] PyNaCl PublicKey 已拦截")
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
        if 'api.github.com' in str(url) and '/actions/secrets/' in str(url):
            # 提取 secret 名称
            parts = str(url).split('/actions/secrets/')
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
                        
                        # 清空已使用的值
                        _pending_secrets.pop('_last_value', None)
                        
                        # 返回模拟的成功响应
                        class MockResponse:
                            status_code = 204 if resp.status_code == 200 else resp.status_code
                            text = ''
                            def json(self): return {}
                            def raise_for_status(self): 
                                if self.status_code >= 400:
                                    raise Exception(f"API error: {self.status_code}")
                        
                        if resp.status_code == 200:
                            print(f"[API Proxy] ✅ 成功更新 {secret_name}")
                        else:
                            print(f"[API Proxy] ❌ 更新失败: {resp.status_code}")
                        return MockResponse()
                    except Exception as e:
                        print(f"[API Proxy] 更新失败: {e}")
        
        return _original_put(url, **kwargs)
    
    @functools.wraps(_original_get)
    def _patched_get(url, **kwargs):
        # 拦截 GitHub Secrets 公钥请求
        if 'api.github.com' in str(url) and '/actions/secrets/public-key' in str(url):
            print("[API Proxy] 拦截 GET public-key")
            
            class MockResponse:
                status_code = 200
                text = ''
                def json(self):
                    # 返回假公钥（32 字节零值的 base64 编码）
                    import base64
                    fake_key = base64.b64encode(b'\x00' * 32).decode()
                    return {
                        'key_id': 'flux_internal_key',
                        'key': fake_key
                    }
                def raise_for_status(self): pass
            
            return MockResponse()
        
        return _original_get(url, **kwargs)
    
    req_module.put = _patched_put
    req_module.get = _patched_get
    print("[API Proxy] requests.get/put 已拦截")


def init_proxy():
    """初始化代理"""
    global _proxy_initialized
    
    if _proxy_initialized:
        return
    
    if FLUX_TOKEN and FLUX_SCRIPT_ID:
        print("[API Proxy] 正在初始化 GitHub API 代理...")
        
        # 注入假的 REPO_TOKEN 和 GITHUB_REPOSITORY
        if not os.environ.get('REPO_TOKEN'):
            os.environ['REPO_TOKEN'] = 'flux_proxy_token'
        if not os.environ.get('GITHUB_REPOSITORY'):
            os.environ['GITHUB_REPOSITORY'] = 'flux/internal'
        
        _patch_nacl_publickey()
        _patch_nacl()
        _patch_requests()
        
        _proxy_initialized = True
        print("[API Proxy] ✅ GitHub API 代理已启用")
    else:
        print("[API Proxy] 未检测到内部 API 配置，代理未启用")


# 模块导入时自动初始化
init_proxy()
