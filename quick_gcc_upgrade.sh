#!/bin/bash

# CentOS 7 GCC快速升级脚本
# 快速升级GCC以支持pandas/numpy编译

echo "🚀 CentOS 7 GCC快速升级"
echo "=================================================="

# 检查root权限
if [[ $EUID -ne 0 ]]; then
   echo "❌ 需要root权限，请使用: sudo $0"
   exit 1
fi

echo "📋 当前GCC版本: $(gcc --version | head -n1)"
echo ""

# 快速安装GCC 9
echo "📦 安装GCC 9..."
yum install -y epel-release
yum install -y centos-release-scl
yum install -y devtoolset-9-gcc devtoolset-9-gcc-c++ devtoolset-9-binutils

echo ""
echo "✅ GCC 9安装完成!"
echo ""

# 创建快速激活脚本
cat > /usr/local/bin/activate-gcc9 << 'EOF'
#!/bin/bash
# 快速激活GCC 9环境

source /opt/rh/devtoolset-9/enable
export CC=/opt/rh/devtoolset-9/root/usr/bin/gcc
export CXX=/opt/rh/devtoolset-9/root/usr/bin/g++

echo "🚀 GCC 9环境已激活: $(gcc --version | head -n1)"
echo "现在可以编译安装pandas和numpy了"
echo ""
echo "使用方法:"
echo "1. 激活环境: source /usr/local/bin/activate-gcc9"
echo "2. 安装包: pip3 install pandas numpy"
echo "3. 或者运行: ./install_and_start_linux.sh"
EOF

chmod +x /usr/local/bin/activate-gcc9

echo "📋 使用方法:"
echo "1. 激活GCC 9环境: source /usr/local/bin/activate-gcc9"
echo "2. 然后运行项目安装脚本: ./install_and_start_linux.sh"
echo ""

echo "✅ GCC升级完成!"
