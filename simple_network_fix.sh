#!/bin/bash

# 简单的网络修复脚本
# 快速解决CentOS 7 yum仓库连接问题

echo "🔧 快速修复CentOS 7网络问题"
echo "=================================================="

# 检查root权限
if [[ $EUID -ne 0 ]]; then
   echo "❌ 需要root权限，请使用: sudo $0"
   exit 1
fi

echo "📋 当前问题: 无法连接CentOS官方仓库"
echo "解决方案: 使用国内镜像源"
echo ""

# 备份原有配置
echo "🔒 备份原有yum配置..."
cp -r /etc/yum.repos.d /etc/yum.repos.d.backup.$(date +%Y%m%d_%H%M%S)

# 清理有问题的仓库
echo "🧹 清理有问题的仓库..."
rm -f /etc/yum.repos.d/CentOS-SCLo-scl*.repo
rm -f /etc/yum.repos.d/CentOS-SCLo-scl-rh*.repo

# 创建阿里云镜像源配置
echo "📡 配置阿里云镜像源..."
cat > /etc/yum.repos.d/CentOS-Base-Aliyun.repo << 'EOF'
[base]
name=CentOS-7 - Base - mirrors.aliyun.com
baseurl=http://mirrors.aliyun.com/centos/7/os/x86_64/
gpgcheck=1
gpgkey=http://mirrors.aliyun.com/centos/RPM-GPG-KEY-CentOS-7

[updates]
name=CentOS-7 - Updates - mirrors.aliyun.com
baseurl=http://mirrors.aliyun.com/centos/7/updates/x86_64/
gpgcheck=1
gpgkey=http://mirrors.aliyun.com/centos/RPM-GPG-KEY-CentOS-7

[extras]
name=CentOS-7 - Extras - mirrors.aliyun.com
baseurl=http://mirrors.aliyun.com/centos/7/extras/x86_64/
gpgcheck=1
gpgkey=http://mirrors.aliyun.com/centos/RPM-GPG-KEY-CentOS-7
EOF

# 创建EPEL仓库配置
echo "📦 配置EPEL仓库..."
cat > /etc/yum.repos.d/epel-aliyun.repo << 'EOF'
[epel]
name=Extra Packages for Enterprise Linux 7 - $basearch
baseurl=http://mirrors.aliyun.com/epel/7/$basearch
failovermethod=priority
enabled=1
gpgcheck=0
EOF

# 创建SCL仓库配置
echo "🔧 配置SCL仓库..."
cat > /etc/yum.repos.d/CentOS-SCLo-scl-aliyun.repo << 'EOF'
[centos-sclo-rh]
name=CentOS-7 - SCLo rh
baseurl=http://mirrors.aliyun.com/centos/7/sclo/x86_64/rh/
gpgcheck=1
enabled=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-SIG-SCLo

[centos-sclo-sclo]
name=CentOS-7 - SCLo sclo
baseurl=http://mirrors.aliyun.com/centos/7/sclo/x86_64/sclo/
gpgcheck=1
enabled=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-CentOS-SIG-SCLo
EOF

echo ""
echo "🧪 测试仓库连接..."
echo "=================================================="

# 清理缓存
yum clean all

# 测试仓库
echo "测试基础仓库..."
if yum repolist | grep -q "base"; then
    echo "✅ 基础仓库连接成功"
else
    echo "❌ 基础仓库连接失败"
fi

echo "测试EPEL仓库..."
if yum repolist | grep -q "epel"; then
    echo "✅ EPEL仓库连接成功"
else
    echo "❌ EPEL仓库连接失败"
fi

echo "测试SCL仓库..."
if yum repolist | grep -q "centos-sclo-rh"; then
    echo "✅ SCL仓库连接成功"
else
    echo "❌ SCL仓库连接失败"
fi

echo ""
echo "🎯 现在可以尝试安装GCC了:"
echo "1. 运行: yum install -y devtoolset-7-gcc devtoolset-7-gcc-c++ devtoolset-7-binutils"
echo "2. 或者运行: ./quick_gcc_upgrade.sh"
echo "3. 或者直接安装项目依赖: pip3 install -r requirements-centos7.txt"
echo ""

echo "✅ 网络问题修复完成!"
echo "=================================================="
