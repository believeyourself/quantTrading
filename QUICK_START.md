# 快速启动指南

## 问题解决：浏览器能访问API，但是代码不能

### 问题原因
您的系统有两个独立的服务：
- **API服务** (FastAPI) - 运行在端口8000
- **Web界面** (Dash) - 运行在端口8050

浏览器能访问API是因为可以直接访问 `http://localhost:8000`，但Web界面需要通过代码调用API服务。

### 解决方案

#### 1. 安装依赖
```bash
pip install -r requirements.txt
```

#### 2. 启动API服务（必需）
```bash
python start_api.py
```
或者双击 `start_api.bat`

#### 3. 测试API服务
```bash
python test_api.py
```

#### 4. 启动Web界面（可选）
```bash
python start_web.py
```
或者双击 `start_web.bat`

### 访问地址
- **API服务**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **Web界面**: http://localhost:8050

### 常见问题

#### Q: 启动API服务时提示端口被占用
A: 检查是否有其他程序占用了8000端口，或者修改 `config/settings.py` 中的 `API_PORT`

#### Q: Web界面无法加载数据
A: 确保API服务已经启动并且可以正常访问

#### Q: 提示缺少模块
A: 运行 `pip install -r requirements.txt` 安装所有依赖

### 验证步骤
1. 启动API服务
2. 在浏览器访问 http://localhost:8000/health
3. 应该看到 `{"status": "healthy", "timestamp": "..."}`
4. 启动Web界面
5. 访问 http://localhost:8050 查看完整功能 