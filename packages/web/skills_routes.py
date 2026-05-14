"""
Skills + 额度 API 模块
包含 Skills 列表/切换/安装/卸载和额度监控等 API 端点。
"""

import logging
import os
import subprocess

from aiohttp import web

from system.config import *
from system.auth import *
from characters.stats import load_quota_usage, check_quota_status, get_current_month, QUOTA_LIMITS
from packages.web.skills_state import (
    _save_skills_state,
    is_skill_enabled_for_character,
    set_skill_for_character,
)


async def api_skills_list(request):
    """[Skill: skills-manager] 获取所有 skills 列表"""
    try:
        character_id = request.query.get('character_id')

        skills_list = []
        for sid, sdata in SKILLS_REGISTRY.items():
            enabled = is_skill_enabled_for_character(sid, character_id)
            skills_list.append({
                "id": sid,
                "name": sdata.get("name", sid),
                "description": sdata.get("desc", ""),
                "desc": sdata.get("desc", ""),
                "enabled": enabled,
                "category": sdata.get("category", "其他"),
                "version": sdata.get("version", "1.0"),
            })

        return web.json_response({'success': True, 'skills': skills_list})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_toggle(request):
    """[Skill: skills-manager] 启用/禁用 skill - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可管理技能'})

        data = await request.json()
        skill_id = data.get('skill_id', '')
        enabled = data.get('enabled', True)
        character_id = data.get('character_id')

        if character_id:
            set_skill_for_character(skill_id, character_id, enabled)
        else:
            # Global toggle
            if skill_id in SKILLS_REGISTRY:
                SKILLS_REGISTRY[skill_id]['enabled'] = enabled
                _save_skills_state()

        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_install(request):
    """[Skill: skills-manager] 安装新 skill - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可安装技能'})

        data = await request.json()
        skill_name = data.get('skill_name', '').strip()

        if not skill_name:
            return web.json_response({'success': False, 'error': '缺少 skill_name 参数'})

        # 执行 clawhub install
        logging.info(f"[skills-manager] 正在安装 skill: {skill_name}")
        result = subprocess.run(
            ["clawhub", "install", skill_name, "--force"],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "安装失败（未知错误）"
            logging.warning(f"[skills-manager] 安装 skill '{skill_name}' 失败: {error_msg}")
            return web.json_response({
                'success': False,
                'error': f'安装失败: {error_msg}',
            })

        # 安装成功，尝试读取 SKILL.md 提取描述
        desc = ""
        skill_md_path = f"/workspace/skills/{skill_name}/SKILL.md"
        try:
            if os.path.exists(skill_md_path):
                with open(skill_md_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                # 从前几行提取描述信息
                for line in lines[:20]:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('---'):
                        desc = line[:200]  # 取前200字符作为描述
                        break
        except Exception:
            pass

        # 添加到 SKILLS_REGISTRY
        SKILLS_REGISTRY[skill_name] = {
            "name": skill_name,
            "desc": desc or f"通过 clawhub 安装的 skill: {skill_name}",
            "enabled": True,
            "category": "自定义",
        }
        _save_skills_state()

        logging.info(f"[skills-manager] Skill '{skill_name}' 安装成功")
        return web.json_response({
            'success': True,
            'skill_id': skill_name,
            'desc': desc,
            'message': f'Skill "{skill_name}" 安装成功',
        })
    except subprocess.TimeoutExpired:
        return web.json_response({'success': False, 'error': '安装超时（60秒）'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_uninstall(request):
    """[Skill: skills-manager] 卸载 skill（从注册表移除，不删除代码）"""
    try:
        data = await request.json()
        skill_id = data.get('skill_id', '')

        if not skill_id:
            return web.json_response({'success': False, 'error': '缺少 skill_id 参数'})

        if skill_id not in SKILLS_REGISTRY:
            return web.json_response({'success': False, 'error': f'Skill "{skill_id}" 不存在'})

        # 从注册表移除（不删除代码文件）
        removed = SKILLS_REGISTRY.pop(skill_id)
        _save_skills_state()

        logging.info(f"[skills-manager] Skill '{skill_id}' 已从注册表移除（代码未删除）")
        return web.json_response({
            'success': True,
            'skill_id': skill_id,
            'removed': removed,
            'message': f'Skill "{skill_id}" 已卸载（代码文件保留）',
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_quota_status(request):
    """额度监控 API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        usage = load_quota_usage()
        status = check_quota_status(usage)
        month = get_current_month()

        items = [
            {
                'name': 'API 请求',
                'icon': '📡',
                'used': usage.get('requests', 0),
                'limit': QUOTA_LIMITS['requests'],
                'unit': '次',
                'color': '#8E24AA',
            },
            {
                'name': 'CPU 用量',
                'icon': '⚡',
                'used': round(usage.get('cpu_seconds', 0), 1),
                'limit': QUOTA_LIMITS['cpu_seconds'],
                'unit': '秒',
                'color': '#2a5290',
            },
            {
                'name': '内存用量',
                'icon': '🧠',
                'used': round(usage.get('memory_gib_seconds', 0), 1),
                'limit': QUOTA_LIMITS['memory_gib_seconds'],
                'unit': 'GiB·s',
                'color': '#6CD9A8',
            },
            {
                'name': '网络流量',
                'icon': '🌐',
                'used': round(usage.get('network_gb', 0), 3),
                'limit': QUOTA_LIMITS['network_gb'],
                'unit': 'GB',
                'color': '#F4A4A4',
            },
        ]

        # 计算各项百分比
        for item in items:
            item['percent'] = round(min(item['used'] / item['limit'] * 100, 100), 1) if item['limit'] > 0 else 0

        # AI 请求统计
        ai_requests = usage.get('ai_requests', 0)
        image_gens = usage.get('image_generations', 0)

        return web.json_response({
            'success': True,
            'status': status,
            'month': month,
            'items': items,
            'ai_requests': ai_requests,
            'image_generations': image_gens,
            'shutdown': usage.get('shutdown_triggered', False),
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})
