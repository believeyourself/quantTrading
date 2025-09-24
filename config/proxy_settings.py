"""
代理配置设置
"""
import urllib3

# 禁用urllib3的SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 代理配置
PROXY_CONFIG = {
    # 是否启用代理
    'enabled': True,
    
    # 代理服务器地址和端口
    'host': '127.0.0.1',
    'port': 7890,  # 常见代理端口: 7890, 1080, 8080, 3128, 8888
    
    # 代理类型
    'type': 'http',  # http, https, socks5
    
    # 代理认证（如果需要）
    'username': None,
    'password': None,
}

def get_proxy_url():
    """获取代理URL"""
    if not PROXY_CONFIG['enabled']:
        return None
    
    proxy_type = PROXY_CONFIG['type']
    host = PROXY_CONFIG['host']
    port = PROXY_CONFIG['port']
    
    # 构建代理URL
    if PROXY_CONFIG['username'] and PROXY_CONFIG['password']:
        # 带认证的代理
        auth = f"{PROXY_CONFIG['username']}:{PROXY_CONFIG['password']}@"
        return f"{proxy_type}://{auth}{host}:{port}"
    else:
        # 无认证的代理
        return f"{proxy_type}://{host}:{port}"

def get_proxy_dict():
    """获取代理字典（用于requests和ccxt）"""
    if not PROXY_CONFIG['enabled']:
        return {}
    
    proxy_url = get_proxy_url()
    return {
        'http': proxy_url,
        'https': proxy_url,
    }

def get_ccxt_proxy_config():
    """获取CCXT专用的代理配置"""
    if not PROXY_CONFIG['enabled']:
        return {}
    
    return {
        'proxies': {
            'http': f"http://{PROXY_CONFIG['host']}:{PROXY_CONFIG['port']}",
            'https': f"http://{PROXY_CONFIG['host']}:{PROXY_CONFIG['port']}",
        },
        'timeout': 60000,  # 增加超时时间
        'enableRateLimit': True,
        'rateLimit': 2000,
    }

def test_proxy_connection():
    """测试代理连接"""
    import requests
    
    try:
        proxies = get_proxy_dict()
        if not proxies:
            print("代理未启用")
            return False
        
        response = requests.get(
            "https://api.binance.com/api/v3/ping", 
            proxies=proxies, 
            timeout=10,
            verify=False  # 禁用SSL验证
        )
        
        if response.status_code == 200:
            print(f"✅ 代理连接测试成功: {get_proxy_url()}")
            return True
        else:
            print(f"❌ 代理连接测试失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 代理连接测试失败: {e}")
        return False

# 常见的代理端口配置
COMMON_PROXY_PORTS = {
    'clash': 7890,
    'v2ray': 1080,
    'shadowsocks': 1080,
    'http_proxy': 8080,
    'squid': 3128,
    'custom': 8888,
}

def detect_proxy_port():
    """自动检测代理端口"""
    import requests
    
    for name, port in COMMON_PROXY_PORTS.items():
        try:
            test_config = PROXY_CONFIG.copy()
            test_config['port'] = port
            
            proxy_url = f"http://{test_config['host']}:{port}"
            proxies = {'http': proxy_url, 'https': proxy_url}
            
            response = requests.get(
                "https://api.binance.com/api/v3/ping", 
                proxies=proxies, 
                timeout=5,
                verify=False
            )
            
            if response.status_code == 200:
                print(f"✅ 检测到代理端口: {port} ({name})")
                return port
                
        except Exception:
            continue
    
    print("❌ 未检测到可用的代理端口")
    return None 