#!/usr/bin/env python3
"""Put SKILL.md and references/ where Claude Code actually looks for skills.

pip installs the methodology inside the package, which is not a path Claude
Code searches: it discovers skills at `<root>/.claude/skills/<name>/SKILL.md`,
personal under `~` or per-project under the project root. So `pip install`
alone gives the CLI and no slash command, and the gap used to be closed by
hand — a `cp` line in the README that nobody remembers after a `pip install
--upgrade`. This command is that step.

    veros skill                       印出裝在哪、跟套件內容一不一致
    veros skill --install             個人：~/.claude/skills/<name>
    veros skill --install --project   當前專案：./.claude/skills/<name>

A project that carries the kit as a git submodule is left alone: that
deployment updates with `git submodule update --remote`, and copying over it
would turn a tracked submodule into a pile of untracked files.
"""
import argparse
import filecmp
import os
import shutil
import sys

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_SRC = os.path.join(PKG_DIR, "SKILL.md")
REFERENCES_SRC = os.path.join(PKG_DIR, "references")


def skill_name() -> str:
    """Read the name out of SKILL.md's own frontmatter.

    The directory has to be named after it. Claude Code matches the two, so a
    directory called `veros` holding a skill named `security-scan` installs
    files that are never found — the failure is silent, and the fix is not to
    pick a name here but to use the one the file declares.
    """
    with open(SKILL_SRC, encoding="utf-8") as f:
        for line in f:
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip()
    sys.exit(f"{SKILL_SRC} 找不到 frontmatter 的 name: 欄位 —— 安裝不完整？")


def target_dir(project: bool) -> str:
    root = os.getcwd() if project else os.path.expanduser("~")
    return os.path.join(root, ".claude", "skills", skill_name())


def _rel_files(root: str) -> set:
    return {
        os.path.relpath(os.path.join(dirpath, name), root)
        for dirpath, _, names in os.walk(root)
        for name in names
    }


def _identical(dest: str) -> bool:
    """Whether the installed copy still matches what this package ships."""
    if not os.path.isfile(os.path.join(dest, "SKILL.md")):
        return False
    if not filecmp.cmp(SKILL_SRC, os.path.join(dest, "SKILL.md"), shallow=False):
        return False
    dest_refs = os.path.join(dest, "references")
    if not os.path.isdir(dest_refs):
        return False
    if _rel_files(REFERENCES_SRC) != _rel_files(dest_refs):
        return False
    return all(
        filecmp.cmp(
            os.path.join(REFERENCES_SRC, rel), os.path.join(dest_refs, rel), shallow=False
        )
        for rel in _rel_files(REFERENCES_SRC)
    )


def _git_managed(dest: str) -> bool:
    """A submodule or symlink deployment, which this command must not clobber."""
    return os.path.islink(dest) or os.path.exists(os.path.join(dest, ".git"))


def status(dest: str) -> None:
    print(f"套件安裝位置  {PKG_DIR}")
    print(f"skill 名稱    {skill_name()}")
    print(f"預計安裝到    {dest}\n")

    if not os.path.exists(dest):
        print("尚未安裝 —— 用 `veros skill --install` 裝進去。")
        return
    if _git_managed(dest):
        print("已以 submodule／symlink 部署，不由本指令管理。")
        print("更新方式：git submodule update --remote")
        return
    if _identical(dest):
        print("已安裝，內容與套件一致。")
    else:
        print("已安裝，但內容與套件不同（套件升級過，或這份被改過）。")
        print("要用套件的版本覆寫：`veros skill --install`")


def install(dest: str, force: bool) -> None:
    if _git_managed(dest) and not force:
        sys.exit(
            f"{dest} 是 submodule／symlink 部署，不覆寫。\n"
            "更新請用 git submodule update --remote；真要改成複製部署加 --force。"
        )

    os.makedirs(dest, exist_ok=True)
    shutil.copy2(SKILL_SRC, os.path.join(dest, "SKILL.md"))
    dest_refs = os.path.join(dest, "references")
    # Replace rather than merge: a reference file dropped from the package
    # should not keep being read from a stale copy of it.
    if os.path.isdir(dest_refs):
        shutil.rmtree(dest_refs)
    shutil.copytree(REFERENCES_SRC, dest_refs)

    print(f"已寫入 {dest}")
    print("  SKILL.md")
    print(f"  references/   （{len(_rel_files(dest_refs))} 個檔案）")
    print(f"\n重啟 Claude Code（或開新 session）後即可用 /{skill_name()}。")
    print("skill 執行時呼叫的是 PATH 上的 veros 指令，所以這個套件要保持安裝狀態。")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--install", action="store_true", help="複製 SKILL.md 與 references/ 到 skill 目錄"
    )
    parser.add_argument(
        "--project",
        action="store_true",
        help="裝進當前目錄的 .claude/skills/（預設裝進 ~/.claude/skills/）",
    )
    parser.add_argument(
        "--force", action="store_true", help="覆寫 submodule／symlink 部署的目錄"
    )
    args = parser.parse_args()

    if not os.path.isfile(SKILL_SRC) or not os.path.isdir(REFERENCES_SRC):
        sys.exit(f"{PKG_DIR} 底下找不到 SKILL.md 或 references/ —— 安裝不完整？")

    dest = target_dir(args.project)
    if args.install:
        install(dest, args.force)
    else:
        status(dest)


if __name__ == "__main__":
    main()
