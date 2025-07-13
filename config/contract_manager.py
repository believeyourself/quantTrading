#!/usr/bin/env python3
"""
合约配置管理器（仅币安，基于binance_interface工具类）
"""
import os
import json
from datetime import datetime
from typing import Dict, List
from utils.binance_funding import BinanceFunding

class ContractManager:
    """合约配置管理器（只支持币安1小时结算合约）"""
    def __init__(self, config_file: str = "config/funding_contracts.json"):
        self.config_file = config_file
        self.contracts = {}
        self.last_updated = None
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        self.funding = BinanceFunding()
        self.load_config()

    def load_config(self) -> bool:
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.contracts = json.load(f)
            self.last_updated = datetime.fromtimestamp(os.path.getmtime(self.config_file))
            print(f"✅ 加载合约配置成功，共 {len(self.contracts)} 个合约")
            return True
        else:
            print("⚠️ 合约配置文件不存在，将创建默认配置")
            return False

    def save_config(self) -> bool:
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.contracts, f, ensure_ascii=False, indent=2)
            print(f"✅ 保存合约配置成功")
            return True
        except Exception as e:
            print(f"❌ 保存合约配置失败: {e}")
            return False

    def scan_1h_funding_contracts(self) -> Dict[str, Dict]:
        """调用工具类扫描币安1小时结算周期合约"""
        print("🔍 开始扫描币安1小时结算周期的永续合约...")
        contracts = self.funding.scan_1h_funding_contracts(contract_type="UM")
        print(f"✅ 扫描完成，共 {len(contracts)} 个合约")
        return contracts

    def update_contracts(self) -> bool:
        try:
            print("🔄 开始更新合约配置...")
            contracts = self.scan_1h_funding_contracts()
            self.contracts = contracts
            self.last_updated = datetime.now()
            return self.save_config()
        except Exception as e:
            print(f"❌ 更新合约配置失败: {e}")
            return False

    def get_contracts(self) -> Dict[str, Dict]:
        return self.contracts

    def get_contract_symbols(self) -> List[str]:
        return list(self.contracts.keys())

    def is_config_valid(self) -> bool:
        return len(self.contracts) > 0 and self.last_updated is not None

    def get_config_info(self) -> Dict:
        return {
            'total_contracts': len(self.contracts),
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'is_valid': self.is_config_valid()
        }

if __name__ == "__main__":
    cm = ContractManager()
    cm.update_contracts()
    print(cm.get_config_info()) 