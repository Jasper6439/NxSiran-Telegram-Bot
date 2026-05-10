#!/usr/bin/env python3
"""
角色生成工具 - 快速创建新角色模板

用法:
    python tools/create_character.py --name "角色名" --source "来源作品"
    python tools/create_character.py --name "角色名" --source "来源作品" --id "character_id"

示例:
    python tools/create_character.py --name "李明" --source "恋爱播放列表" --id "liming"
"""
import os
import sys
import json
import argparse
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
CHARACTERS_DIR = PROJECT_ROOT / "characters"
TEMPLATES_DIR = CHARACTERS_DIR / "templates"


def create_character(name: str, source: str, character_id: str = None) -> str:
    """创建新角色目录和模板文件"""
    
    # 生成角色 ID
    if not character_id:
        # 将中文名转为拼音或使用英文
        character_id = name.lower().replace(" ", "_")
        # 简单处理：如果是中文名，使用默认 ID
        if any('\u4e00' <= c <= '\u9fff' for c in character_id):
            character_id = f"character_{hash(name) % 10000}"
    
    # 创建角色目录
    char_dir = CHARACTERS_DIR / character_id
    if char_dir.exists():
        return f"错误：角色目录已存在: {char_dir}"
    
    char_dir.mkdir(parents=True)
    
    # 读取模板
    config_template = TEMPLATES_DIR / "config.template.json"
    persona_template = TEMPLATES_DIR / "persona.template.md"
    code_template = TEMPLATES_DIR / "character.template.py"
    
    # 替换模板中的占位符
    replacements = {
        "{角色名}": name,
        "{英文名}": character_id,
        "{作品名}": source,
        "{character_id}": character_id,
    }
    
    # 创建 config.json
    if config_template.exists():
        content = config_template.read_text(encoding='utf-8')
        for old, new in replacements.items():
            content = content.replace(old, new)
        (char_dir / "config.json").write_text(content, encoding='utf-8')
    
    # 创建 persona.md
    if persona_template.exists():
        content = persona_template.read_text(encoding='utf-8')
        for old, new in replacements.items():
            content = content.replace(old, new)
        (char_dir / "persona.md").write_text(content, encoding='utf-8')
    
    # 创建角色代码文件
    if code_template.exists():
        content = code_template.read_text(encoding='utf-8')
        for old, new in replacements.items():
            content = content.replace(old, new)
        (char_dir / f"{character_id}.py").write_text(content, encoding='utf-8')
    
    # 创建空的 memories.md
    (char_dir / "memories.md").write_text(
        f"# {name} — 共同记忆\n\n> 此文件由系统自动生成，记录与玩家的共同经历\n\n",
        encoding='utf-8'
    )
    
    return f"""✅ 角色创建成功！

角色目录: {char_dir}

创建的文件:
├── config.json      # 角色配置
├── persona.md       # 详细人设
├── memories.md      # 共同记忆
└── {character_id}.py # 角色实现

下一步:
1. 编辑 config.json 填写角色配置
2. 编辑 persona.md 按 6 层架构填写人设
3. 编辑 {character_id}.py 实现角色逻辑
4. 参考 CHARACTER_DISTILLATION_GUIDE.md 进行完善
"""


def list_characters():
    """列出所有角色"""
    print("已创建的角色:")
    print("-" * 40)
    
    for item in CHARACTERS_DIR.iterdir():
        if item.is_dir() and item.name not in ['templates', '__pycache__']:
            config_file = item / "config.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                name = config.get('name', item.name)
                source = config.get('source', '未知')
                print(f"  {item.name}: {name} (来源: {source})")
            else:
                print(f"  {item.name}: (无配置)")


def main():
    parser = argparse.ArgumentParser(description="角色生成工具")
    parser.add_argument("--name", "-n", help="角色名称")
    parser.add_argument("--source", "-s", help="来源作品")
    parser.add_argument("--id", "-i", help="角色ID（可选）")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有角色")
    
    args = parser.parse_args()
    
    if args.list:
        list_characters()
        return
    
    if not args.name or not args.source:
        parser.print_help()
        print("\n示例:")
        print('  python tools/create_character.py --name "李明" --source "恋爱播放列表"')
        return
    
    result = create_character(args.name, args.source, args.id)
    print(result)


if __name__ == "__main__":
    main()
