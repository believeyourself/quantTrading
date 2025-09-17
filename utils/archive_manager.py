"""
合约历史数据归档管理器
负责管理合约入池出池时的数据归档，支持按会话区分每次入池出池的特征分析
"""

import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from utils.logger import get_logger

logger = get_logger(__name__)

class ContractArchiveManager:
    """合约历史数据归档管理器"""
    
    def __init__(self):
        self.archive_dir = "cache/archive"
        self.sessions_dir = os.path.join(self.archive_dir, "sessions")
        self.summary_dir = os.path.join(self.archive_dir, "summary")
        self.current_history_dir = "cache/monitor_history"
        
        # 确保目录存在
        os.makedirs(self.sessions_dir, exist_ok=True)
        os.makedirs(self.summary_dir, exist_ok=True)
        
        # 归档索引文件
        self.index_file = os.path.join(self.summary_dir, "archive_index.json")
        self.sessions_summary_file = os.path.join(self.summary_dir, "contract_sessions.json")
        
        # 加载归档索引
        self.archive_index = self._load_archive_index()
        self.sessions_summary = self._load_sessions_summary()
    
    def _load_archive_index(self) -> Dict:
        """加载归档索引"""
        if os.path.exists(self.index_file):
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载归档索引失败: {e}")
        return {
            "last_session_id": 0,
            "total_sessions": 0,
            "last_updated": datetime.now().isoformat()
        }
    
    def _load_sessions_summary(self) -> Dict:
        """加载会话摘要"""
        if os.path.exists(self.sessions_summary_file):
            try:
                with open(self.sessions_summary_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载会话摘要失败: {e}")
        return {}
    
    def _save_archive_index(self):
        """保存归档索引"""
        try:
            self.archive_index["last_updated"] = datetime.now().isoformat()
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.archive_index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存归档索引失败: {e}")
    
    def _save_sessions_summary(self):
        """保存会话摘要"""
        try:
            with open(self.sessions_summary_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions_summary, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存会话摘要失败: {e}")
    
    def _generate_session_id(self, symbol: str) -> str:
        """生成会话ID"""
        self.archive_index["last_session_id"] += 1
        session_id = f"{datetime.now().strftime('%Y-%m-%d')}_{symbol}_session_{self.archive_index['last_session_id']:03d}"
        return session_id
    
    def archive_contract_exit(self, symbol: str, exit_reason: str = "manual") -> Optional[str]:
        """
        合约出池时归档数据
        
        Args:
            symbol: 合约名称
            exit_reason: 出池原因
            
        Returns:
            归档的会话ID，如果归档失败返回None
        """
        try:
            # 检查是否有当前历史数据
            current_history_file = os.path.join(self.current_history_dir, f"{symbol}_history.json")
            if not os.path.exists(current_history_file):
                logger.warning(f"合约 {symbol} 没有历史数据文件，跳过归档")
                return None
            
            # 读取当前历史数据
            with open(current_history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            
            if not history_data.get('history'):
                logger.warning(f"合约 {symbol} 历史数据为空，跳过归档")
                return None
            
            # 生成会话ID
            session_id = self._generate_session_id(symbol)
            
            # 计算统计信息
            history_records = history_data['history']
            entry_time = history_records[-1]['timestamp']  # 最早的记录
            exit_time = history_records[0]['timestamp']    # 最新的记录
            
            # 计算资金费率统计
            funding_rates = [record.get('funding_rate', 0) for record in history_records]
            entry_funding_rate = funding_rates[-1]  # 入池时的资金费率
            exit_funding_rate = funding_rates[0]     # 出池时的资金费率
            max_funding_rate = max(funding_rates)
            min_funding_rate = min(funding_rates)
            avg_funding_rate = sum(funding_rates) / len(funding_rates)
            
            # 计算价格统计
            mark_prices = [record.get('mark_price', 0) for record in history_records]
            entry_price = mark_prices[-1]  # 入池时的价格
            exit_price = mark_prices[0]    # 出池时的价格
            max_price = max(mark_prices)
            min_price = min(mark_prices)
            
            # 计算持续时间
            try:
                entry_dt = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
                exit_dt = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))
                duration_minutes = int((exit_dt - entry_dt).total_seconds() / 60)
            except:
                duration_minutes = 0
            
            # 构建归档数据
            archive_data = {
                "session_id": session_id,
                "symbol": symbol,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "duration_minutes": duration_minutes,
                "entry_funding_rate": entry_funding_rate,
                "exit_funding_rate": exit_funding_rate,
                "max_funding_rate": max_funding_rate,
                "min_funding_rate": min_funding_rate,
                "avg_funding_rate": avg_funding_rate,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "max_price": max_price,
                "min_price": min_price,
                "total_records": len(history_records),
                "exit_reason": exit_reason,
                "created_time": datetime.now().isoformat(),
                "history": history_records
            }
            
            # 保存归档文件
            archive_filename = f"{session_id}.json"
            archive_filepath = os.path.join(self.sessions_dir, archive_filename)
            
            with open(archive_filepath, 'w', encoding='utf-8') as f:
                json.dump(archive_data, f, ensure_ascii=False, indent=2)
            
            # 更新会话摘要
            if symbol not in self.sessions_summary:
                self.sessions_summary[symbol] = []
            
            # 添加会话摘要（不包含完整历史数据）
            session_summary = {
                "session_id": session_id,
                "entry_time": entry_time,
                "exit_time": exit_time,
                "duration_minutes": duration_minutes,
                "entry_funding_rate": entry_funding_rate,
                "exit_funding_rate": exit_funding_rate,
                "max_funding_rate": max_funding_rate,
                "min_funding_rate": min_funding_rate,
                "avg_funding_rate": avg_funding_rate,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "max_price": max_price,
                "min_price": min_price,
                "total_records": len(history_records),
                "exit_reason": exit_reason,
                "created_time": datetime.now().isoformat()
            }
            
            self.sessions_summary[symbol].append(session_summary)
            
            # 更新归档索引
            self.archive_index["total_sessions"] += 1
            
            # 保存索引和摘要
            self._save_archive_index()
            self._save_sessions_summary()
            
            logger.info(f"✅ 合约 {symbol} 出池数据已归档，会话ID: {session_id}")
            logger.info(f"📊 归档统计: 持续时间 {duration_minutes}分钟，记录数 {len(history_records)}，资金费率范围 [{min_funding_rate:.4f}, {max_funding_rate:.4f}]")
            
            return session_id
            
        except Exception as e:
            logger.error(f"❌ 合约 {symbol} 出池归档失败: {e}")
            return None
    
    def archive_contract_entry(self, symbol: str, entry_reason: str = "auto") -> Optional[str]:
        """
        合约入池时记录入池信息
        
        Args:
            symbol: 合约名称
            entry_reason: 入池原因
            
        Returns:
            会话ID，如果记录失败返回None
        """
        try:
            # 生成会话ID
            session_id = self._generate_session_id(symbol)
            
            # 记录入池信息
            entry_data = {
                "session_id": session_id,
                "symbol": symbol,
                "entry_time": datetime.now().isoformat(),
                "entry_reason": entry_reason,
                "status": "active",
                "created_time": datetime.now().isoformat()
            }
            
            # 保存入池记录
            entry_filename = f"{session_id}_entry.json"
            entry_filepath = os.path.join(self.sessions_dir, entry_filename)
            
            with open(entry_filepath, 'w', encoding='utf-8') as f:
                json.dump(entry_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 合约 {symbol} 入池记录已保存，会话ID: {session_id}")
            
            return session_id
            
        except Exception as e:
            logger.error(f"❌ 合约 {symbol} 入池记录失败: {e}")
            return None
    
    def get_contract_sessions(self, symbol: str) -> List[Dict]:
        """获取指定合约的所有会话摘要"""
        return self.sessions_summary.get(symbol, [])
    
    def get_session_detail(self, session_id: str) -> Optional[Dict]:
        """获取指定会话的详细信息"""
        try:
            session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
            if os.path.exists(session_file):
                with open(session_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"获取会话 {session_id} 详情失败: {e}")
            return None
    
    def get_archive_statistics(self) -> Dict:
        """获取归档统计信息"""
        try:
            total_sessions = self.archive_index.get("total_sessions", 0)
            total_contracts = len(self.sessions_summary)
            
            # 计算各合约的会话数
            contract_session_counts = {}
            for symbol, sessions in self.sessions_summary.items():
                contract_session_counts[symbol] = len(sessions)
            
            # 计算平均会话持续时间
            all_durations = []
            for sessions in self.sessions_summary.values():
                for session in sessions:
                    if 'duration_minutes' in session:
                        all_durations.append(session['duration_minutes'])
            
            avg_duration = sum(all_durations) / len(all_durations) if all_durations else 0
            
            return {
                "total_sessions": total_sessions,
                "total_contracts": total_contracts,
                "contract_session_counts": contract_session_counts,
                "average_duration_minutes": avg_duration,
                "last_updated": self.archive_index.get("last_updated", ""),
                "archive_directory": self.archive_dir
            }
            
        except Exception as e:
            logger.error(f"获取归档统计失败: {e}")
            return {}
    
    def cleanup_old_archives(self, days_to_keep: int = 30):
        """清理旧的归档数据"""
        try:
            cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
            cleaned_count = 0
            
            for filename in os.listdir(self.sessions_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.sessions_dir, filename)
                    if os.path.getmtime(filepath) < cutoff_date:
                        os.remove(filepath)
                        cleaned_count += 1
            
            logger.info(f"✅ 清理了 {cleaned_count} 个超过 {days_to_keep} 天的归档文件")
            
        except Exception as e:
            logger.error(f"清理旧归档失败: {e}")


# 全局归档管理器实例
archive_manager = ContractArchiveManager()
