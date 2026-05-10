# 恋爱至上主义区域 (Love Supremacy Zone) - 角色基类
"""
角色基类 - 所有蒸馏角色的模板
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import json
import os


@dataclass
class CharacterConfig:
    """角色配置"""
    id: str                          # 角色ID，如 "chayewoon"
    name: str                        # 显示名称，如 "车如云"
    source: str                      # 来源作品，如 "恋爱播放列表"
    
    # 角色设定
    personality: str = ""            # 性格描述
    background: str = ""             # 背景故事
    speaking_style: str = ""         # 说话风格
    catchphrases: List[str] = field(default_factory=list)  # 口头禅
    
    # 对话配置
    system_prompt: str = ""          # AI 系统提示词（如果提供则使用这个）
    user_nickname: str = "完成者"    # 对用户的称呼

    # 世界观配置
    world_layer: str = "stage"       # 剧本区/留白区/共鸣层
    emotion_defaults: dict = None    # {"affection": 0, "happiness": 50, "awakening": 0}
    awakening_conditions: dict = None  # 觉醒条件
    is_novel_character: bool = False   # 是否为小说原作角色
    world_role: str = ""               # 在世界观中的角色定位

    # 视觉配置
    avatar_url: Optional[str] = None # 头像URL
    theme_color: str = "#660874"     # 主题色

    # 数据路径
    data_dir: str = ""               # 专属数据目录
    
    def get_data_path(self, filename: str) -> str:
        """获取数据文件路径"""
        return os.path.join(self.data_dir, filename)
    
    @classmethod
    def from_dict(cls, data: dict, id: str, data_dir: str = "") -> 'CharacterConfig':
        """从字典创建配置"""
        return cls(
            id=id,
            name=data.get('name', id),
            source=data.get('source', ''),
            personality=data.get('personality', ''),
            background=data.get('background', ''),
            speaking_style=data.get('speaking_style', ''),
            catchphrases=data.get('catchphrases', []),
            system_prompt=data.get('system_prompt', ''),
            user_nickname=data.get('user_nickname', '完成者'),
            world_layer=data.get('world_layer', 'stage'),
            emotion_defaults=data.get('emotion_defaults'),
            awakening_conditions=data.get('awakening_conditions'),
            is_novel_character=data.get('is_novel_character', False),
            world_role=data.get('world_role', ''),
            avatar_url=data.get('avatar_url'),
            theme_color=data.get('theme_color', '#660874'),
            data_dir=data_dir,
        )


class CharacterBase(ABC):
    """角色基类"""
    
    def __init__(self, config: CharacterConfig):
        self.config = config
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        if self.config.data_dir:
            os.makedirs(self.config.data_dir, exist_ok=True)
    
    @abstractmethod
    def get_system_prompt(self, context: Dict[str, Any] = None) -> str:
        """获取 AI 系统提示词"""
        pass
    
    @abstractmethod
    def format_response(self, text: str) -> str:
        """格式化回复文本"""
        pass
    
    @abstractmethod
    def get_random_selfie_caption(self) -> str:
        """获取随机自拍配文"""
        pass
    
    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "id": self.config.id,
            "name": self.config.name,
            "source": self.config.source,
            "theme_color": self.config.theme_color,
            "avatar_url": self.config.avatar_url,
            "user_nickname": self.config.user_nickname,
        }
