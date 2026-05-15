"""
角色声音管理模块
v1.6.4.2 — 支持角色声音上传、存储、TTS 克隆

功能：
1. 接收用户上传的角色声音样本（音频文件）
2. 保存到 characters/{character_id}/voice/ 目录
3. 支持 Fish Speech / GPT-SoVITS 声音克隆
4. 生成 voice_config.json 配置
"""

import os
import json
import logging
import shutil
from typing import Dict, Optional, List
from pathlib import Path

from system.config import DATA_DIR

logger = logging.getLogger(__name__)

# 角色声音存储目录
VOICE_DIR = "voice"
VOICE_CONFIG_FILE = "voice_config.json"


class VoiceManager:
    """角色声音管理器"""

    def __init__(self, character_id: str):
        self.character_id = character_id
        self.char_dir = os.path.join(
            os.path.dirname(__file__), character_id
        )
        self.voice_dir = os.path.join(self.char_dir, VOICE_DIR)
        self.config_path = os.path.join(self.voice_dir, VOICE_CONFIG_FILE)
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保目录存在"""
        os.makedirs(self.voice_dir, exist_ok=True)

    def _load_config(self) -> Dict:
        """加载声音配置"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "character_id": self.character_id,
            "samples": [],
            "tts_config": {
                "backend": "auto",  # auto | fish | sovits | edge
                "fish_reference_id": "",
                "sovits_api_url": "",
            },
            "voice_traits": {
                "gender": "male",
                "age_group": "young",
                "tone": "soft",
                "description": "",
            }
        }

    def _save_config(self, config: Dict):
        """保存声音配置"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def list_samples(self) -> List[Dict]:
        """列出所有声音样本"""
        config = self._load_config()
        return config.get("samples", [])

    def save_voice_sample(self, source_path: str, label: str = "", 
                          description: str = "") -> Dict:
        """保存声音样本

        Args:
            source_path: 源音频文件路径
            label: 样本标签（如 "温柔" "生气" "日常"）
            description: 样本描述

        Returns:
            保存结果
        """
        try:
            # 生成文件名
            ext = os.path.splitext(source_path)[1] or ".mp3"
            sample_id = f"sample_{len(self.list_samples()) + 1}"
            filename = f"{sample_id}{ext}"
            dest_path = os.path.join(self.voice_dir, filename)

            # 复制文件
            shutil.copy2(source_path, dest_path)

            # 更新配置
            config = self._load_config()
            sample_info = {
                "id": sample_id,
                "filename": filename,
                "label": label or "默认",
                "description": description,
                "path": dest_path,
            }
            config["samples"].append(sample_info)
            self._save_config(config)

            logger.info(f"[Voice] 保存声音样本: {filename} ({label})")
            return {"success": True, "sample": sample_info}

        except Exception as e:
            logger.error(f"[Voice] 保存声音样本失败: {e}")
            return {"success": False, "error": str(e)}

    def delete_sample(self, sample_id: str) -> bool:
        """删除声音样本"""
        try:
            config = self._load_config()
            samples = config.get("samples", [])

            for i, sample in enumerate(samples):
                if sample["id"] == sample_id:
                    # 删除文件
                    path = sample.get("path")
                    if path and os.path.exists(path):
                        os.remove(path)

                    # 从配置移除
                    samples.pop(i)
                    self._save_config(config)
                    logger.info(f"[Voice] 删除声音样本: {sample_id}")
                    return True

            return False

        except Exception as e:
            logger.error(f"[Voice] 删除声音样本失败: {e}")
            return False

    def set_tts_config(self, backend: str = None, fish_reference_id: str = None,
                       sovits_api_url: str = None) -> Dict:
        """设置 TTS 配置

        Args:
            backend: TTS 后端 (auto|fish|sovits|edge)
            fish_reference_id: Fish Speech 克隆音色 ID
            sovits_api_url: GPT-SoVITS API URL
        """
        config = self._load_config()
        tts_config = config.get("tts_config", {})

        if backend:
            tts_config["backend"] = backend
        if fish_reference_id is not None:
            tts_config["fish_reference_id"] = fish_reference_id
        if sovits_api_url is not None:
            tts_config["sovits_api_url"] = sovits_api_url

        config["tts_config"] = tts_config
        self._save_config(config)

        return {"success": True, "tts_config": tts_config}

    def get_tts_config(self) -> Dict:
        """获取 TTS 配置"""
        config = self._load_config()
        return config.get("tts_config", {})

    def set_voice_traits(self, gender: str = None, age_group: str = None,
                         tone: str = None, description: str = None) -> Dict:
        """设置声音特征描述

        用于生成 voice_traits，帮助 AI 理解角色声音特点
        """
        config = self._load_config()
        traits = config.get("voice_traits", {})

        if gender:
            traits["gender"] = gender
        if age_group:
            traits["age_group"] = age_group
        if tone:
            traits["tone"] = tone
        if description is not None:
            traits["description"] = description

        config["voice_traits"] = traits
        self._save_config(config)

        return {"success": True, "voice_traits": traits}

    def get_voice_traits(self) -> Dict:
        """获取声音特征"""
        config = self._load_config()
        return config.get("voice_traits", {})

    def get_voice_context_for_prompt(self) -> str:
        """生成用于角色 prompt 的声音描述

        返回一段描述角色声音的文本，可插入到 system prompt
        """
        config = self._load_config()
        traits = config.get("voice_traits", {})
        samples = config.get("samples", [])

        if not traits.get("description") and not samples:
            return ""

        parts = ["\n【声音特点】"]

        if traits.get("description"):
            parts.append(traits["description"])

        if samples:
            labels = [s.get("label", "") for s in samples if s.get("label")]
            if labels:
                parts.append(f"声音样本类型: {', '.join(set(labels))}")

        return "\n".join(parts)

    async def clone_voice_fish(self, sample_path: str, api_key: str) -> Dict:
        """使用 Fish Speech 克隆声音

        上传样本到 Fish Speech，获取 reference_id
        """
        try:
            import httpx

            url = "https://api.fish.audio/v1/voices"
            headers = {"Authorization": f"Bearer {api_key}"}

            with open(sample_path, "rb") as f:
                files = {"file": f}
                data = {"title": f"{self.character_id}_voice"}

                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, headers=headers, 
                                            data=data, files=files, timeout=60)

            if resp.status_code == 200:
                result = resp.json()
                reference_id = result.get("id")

                # 保存配置
                self.set_tts_config(backend="fish", fish_reference_id=reference_id)

                return {
                    "success": True,
                    "reference_id": reference_id,
                    "message": "声音克隆成功"
                }
            else:
                return {
                    "success": False,
                    "error": f"API 返回 {resp.status_code}: {resp.text}"
                }

        except Exception as e:
            logger.error(f"[Voice] Fish Speech 克隆失败: {e}")
            return {"success": False, "error": str(e)}

    def get_status(self) -> Dict:
        """获取声音管理状态"""
        config = self._load_config()
        return {
            "character_id": self.character_id,
            "sample_count": len(config.get("samples", [])),
            "tts_backend": config.get("tts_config", {}).get("backend", "auto"),
            "has_cloned_voice": bool(
                config.get("tts_config", {}).get("fish_reference_id") or
                config.get("tts_config", {}).get("sovits_api_url")
            ),
            "voice_traits": config.get("voice_traits", {}),
        }


# ===== 便捷函数 =====

_voice_managers: Dict[str, VoiceManager] = {}


def get_voice_manager(character_id: str = 'chayewoon') -> VoiceManager:
    """获取角色声音管理器"""
    if character_id not in _voice_managers:
        _voice_managers[character_id] = VoiceManager(character_id)
    return _voice_managers[character_id]
