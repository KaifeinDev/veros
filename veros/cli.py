#!/usr/bin/env python3
"""Veros — 智能合約交付前的安全自檢工具。"""
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

SUBCOMMANDS = {
    "run": "run.py",
    "config": "config.py",
    "docs": "docs.py",
    "skill": "skill_install.py",
    "doctor": "env_check.py",
    "scan": "scan.py",
    "triage": "triage.py",
    "review": "review.py",
    "confirm": "confirm.py",
    "report": "report.py",
}

# `check` was this command's name before it became `doctor`. Kept working so a
# pinned CI job does not break on upgrade; undocumented, and not listed below.
ALIASES = {"check": "doctor"}

HELP = """Veros — 智能合約交付前的安全自檢工具

  Slither 掃描 → AI 判讀 → 人工簽核 → 交付報告（PDF）

用法
  veros <指令> [選項]
  veros <指令> --help        每個指令自己的選項

最短路徑
  cd <專案根目錄>
  veros run --brief          掃描並產出判讀工單（不需 API key）
  # 讓你的 agent 讀 audit/scan/brief/README.md 完成工單
  veros run --apply          套用結果並產出報告
  veros confirm --list       逐筆複核 AI 草稿
  veros confirm <編號...>    簽核
  veros report               重新評定是否可交付

  有 Anthropic API key 的話，`veros run` 一行跑完，中間不用停。

指令
  run       整條流程。--brief／--apply 是不打 API 的兩段式；不帶則直接呼叫模型
  doctor    環境健檢：專案編不編得起來、solc／slither／forge 版本、OZ 版本判斷
  scan      跑 Slither、過濾出專案自己的發現、產出分類 skeleton 與掃描範圍
  triage    讓模型起草分類與報告欄位。--emit-brief／--apply-brief 為工單模式
  review    對 classification.json 做機械檢查（共用理由、必填欄位、High 降級）
  confirm   簽核 AI 草稿。未簽核完畢前，報告一律不判定為可交付
  report    產出 report.md 與 report.pdf
  config    AI 判讀用的模型與 API key
  docs      印出隨工具安裝的方法論（情境庫、嚴重度標準、踩坑紀錄）
  skill     把 /security-scan 裝進 Claude Code（--install，見下方「安裝 skill」）

檔案配置（全部在專案的 audit/ 底下，缺的會自動建立）
  audit/scan/           掃描產物與 classification.json
  audit/overview.md     你寫：協定理解，進報告的「摘要」章
  audit/scope_note.md   你寫：本次偏離標準程序之處，沒有就留空
  audit/worksheet.md    內部工作底稿
  audit/report/         交付物：report.md + report.pdf

  只有 audit/report/ 可以交給甲方，其餘是內部文件。

兩件容易誤解的事
  * report 的 exit code 是交付判定，不是錯誤碼：
      0 可交付　3／4 內部工作版本（仍會產出，帶浮水印）　2 分類驗證失敗（不產出）
  * AI 起草的分類一律標記為未經人工確認，閘門不會判定為可交付。
    「可交付」始終是人的簽核 —— 模型省掉的是打字，不是責任。

安裝 skill（Claude Code 的 /security-scan）
  pip 只裝 CLI；slash 指令要把 SKILL.md 與 references/ 放到 Claude Code 找得到的位置：
      veros skill              看現在裝在哪、跟套件內容一不一致
      veros skill --install    裝進 ~/.claude/skills/（個人，每個專案都能用）
      veros skill --install --project
                               裝進當前專案的 .claude/skills/
  裝完重啟 Claude Code。skill 跑的是 PATH 上的 veros，所以兩者都要在。

前置需求
  Slither 與 Foundry 是外部工具，不隨 pip 安裝：
      pip install slither-analyzer
      solc-select install <版本> && solc-select use <版本>
  報告為繁中，PDF 需要涵蓋 CJK 的字型（macOS 把 Noto Sans CJK 放進 ~/Library/Fonts/）。
  `veros doctor` 會一次告訴你缺什麼。
"""


def main() -> None:
    argv = sys.argv[1:]
    sub = argv[0] if argv else None

    if sub in (None, "-h", "--help", "help"):
        print(HELP)
        # Asking for help is not an error; a bare `veros` is a usage mistake.
        sys.exit(0 if sub else 2)

    sub = ALIASES.get(sub, sub)
    if sub not in SUBCOMMANDS:
        print(f"未知的指令：{argv[0]}\n", file=sys.stderr)
        print(HELP, file=sys.stderr)
        sys.exit(2)

    script_path = os.path.join(SCRIPTS_DIR, SUBCOMMANDS[sub])
    proc = subprocess.run([sys.executable, script_path, *argv[1:]])
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()
