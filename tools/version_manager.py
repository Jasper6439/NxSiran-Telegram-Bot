#!/usr/bin/env python3
"""
角色版本管理器

负责角色文件的版本存档和回滚。
适配恋爱至上主义区域角色蒸馏标准。

用法：
    python tools/version_manager.py --action list --slug chayewoon --base-dir characters
    python tools/version_manager.py --action backup --slug chayewoon --base-dir characters
    python tools/version_manager.py --action rollback --slug chayewoon --version v2 --base-dir characters
    python tools/version_manager.py --action cleanup --slug chayewoon --base-dir characters
"""

from __future__ import annotations

import json
import shutil
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

MAX_VERSIONS = 10  # 最多保留的版本数


def list_versions(skill_dir: Path) -> list:
    """列出所有历史版本"""
    versions_dir = skill_dir / "versions"
    if not versions_dir.exists():
        return []

    versions = []
    for v_dir in sorted(versions_dir.iterdir()):
        if not v_dir.is_dir():
            continue

        version_name = v_dir.name
        mtime = v_dir.stat().st_mtime
        archived_at = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        files = [f.name for f in v_dir.iterdir() if f.is_file()]

        versions.append({
            "version": version_name,
            "archived_at": archived_at,
            "files": files,
            "path": str(v_dir),
        })

    return versions


def backup(skill_dir: Path) -> str:
    """存档当前版本"""
    meta_path = skill_dir / "meta.json"
    version = "v1"

    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            version = meta.get("version", "v1")
        except Exception:
            pass

    version_dir = skill_dir / "versions" / version
    version_dir.mkdir(parents=True, exist_ok=True)

    backed_up = []
    for fname in ("persona.md", "memories.md", "config.json", "meta.json"):
        src = skill_dir / fname
        if src.exists():
            shutil.copy2(src, version_dir / fname)
            backed_up.append(fname)

    # 更新 meta.json 的版本号
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            current_version = meta.get("version", "v1")
            try:
                version_num = int(current_version.lstrip("v").split("_")[0]) + 1
            except ValueError:
                version_num = 2
            meta["version"] = f"v{version_num}"
            meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            new_version = meta["version"]
        except Exception:
            new_version = version
    else:
        new_version = version

    print(f"✅ 已存档版本 {version}，文件：{', '.join(backed_up)}")
    print(f"   当前版本号已更新为 {new_version}")
    return new_version


def rollback(skill_dir: Path, target_version: str) -> bool:
    """回滚到指定版本"""
    version_dir = skill_dir / "versions" / target_version

    if not version_dir.exists():
        print(f"❌ 错误：版本 {target_version} 不存在", file=sys.stderr)
        return False

    # 先存档当前版本
    meta_path = skill_dir / "meta.json"
    current_version = "v?"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            current_version = meta.get("version", "v?")
        except Exception:
            pass

    backup_dir = skill_dir / "versions" / f"{current_version}_before_rollback"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("persona.md", "memories.md", "config.json", "meta.json"):
        src = skill_dir / fname
        if src.exists():
            shutil.copy2(src, backup_dir / fname)

    # 从目标版本恢复文件
    restored_files = []
    for fname in ("persona.md", "memories.md", "config.json", "meta.json"):
        src = version_dir / fname
        if src.exists():
            shutil.copy2(src, skill_dir / fname)
            restored_files.append(fname)

    # 更新 meta
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["version"] = target_version + "_restored"
            meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            meta["rollback_from"] = current_version
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    print(f"✅ 已回滚到 {target_version}，恢复文件：{', '.join(restored_files)}")
    print(f"   回滚前版本已存档为 {current_version}_before_rollback")
    return True


def cleanup_old_versions(skill_dir: Path, max_versions: int = MAX_VERSIONS):
    """清理超出限制的旧版本"""
    versions_dir = skill_dir / "versions"
    if not versions_dir.exists():
        return

    version_dirs = sorted(
        [d for d in versions_dir.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
    )

    to_delete = version_dirs[:-max_versions] if len(version_dirs) > max_versions else []

    for old_dir in to_delete:
        shutil.rmtree(old_dir)
        print(f"   已清理旧版本：{old_dir.name}")

    if not to_delete:
        print("   无需清理")


def main():
    parser = argparse.ArgumentParser(description="角色版本管理器")
    parser.add_argument("--action", required=True, choices=["list", "backup", "rollback", "cleanup"])
    parser.add_argument("--slug", required=True, help="角色 ID（目录名）")
    parser.add_argument("--version", help="目标版本号（rollback 时使用）")
    parser.add_argument(
        "--base-dir",
        default="characters",
        help="角色根目录（默认：characters）",
    )

    args = parser.parse_args()
    base_dir = Path(args.base_dir).expanduser()
    skill_dir = base_dir / args.slug

    if not skill_dir.exists():
        print(f"❌ 错误：找不到角色目录 {skill_dir}", file=sys.stderr)
        sys.exit(1)

    if args.action == "list":
        versions = list_versions(skill_dir)
        if not versions:
            print(f"📋 {args.slug} 暂无历史版本")
        else:
            print(f"📋 {args.slug} 的历史版本：\n")
            for v in versions:
                print(f"  📁 {v['version']}  存档时间: {v['archived_at']}  文件: {', '.join(v['files'])}")

    elif args.action == "backup":
        backup(skill_dir)

    elif args.action == "rollback":
        if not args.version:
            print("❌ 错误：rollback 操作需要 --version", file=sys.stderr)
            sys.exit(1)
        rollback(skill_dir, args.version)

    elif args.action == "cleanup":
        print(f"🧹 清理 {args.slug} 的旧版本（最多保留 {MAX_VERSIONS} 个）：")
        cleanup_old_versions(skill_dir)
        print("✅ 清理完成")


if __name__ == "__main__":
    main()
