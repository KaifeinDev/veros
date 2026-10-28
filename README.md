# Veros

**Veros 是智能合約漏洞掃描工具。** 對 Solidity 專案（Foundry 或 Hardhat）跑 Slither 靜態分析，再補一輪
Slither 抓不到的業務邏輯漏洞掃描，把每一筆發現逐筆分類並寫下判斷依據，最後產出可交給甲方的審計報告，
以及一個可接進 CI 的交付閘門。

**掃得到什麼**

- Slither 的全部檢查器：重入、access control、未初始化變數、`delegatecall`、upgradeable 合約的 storage 配置等
- `references/logic_scan.md` 的十條情境：權限檢查的實作邏輯、未保護的狀態變更、旗標未落實、滑點、價格源等
  —— 這些是靜態分析工具抓不到、必須讀懂業務意圖才看得出來的漏洞
- `references/domain_incidents/` 的領域公開事故比對（目前涵蓋 account abstraction、RWA）

**不掃什麼**

非 Solidity 的程式碼。後端、前端、腳本、CI 設定都不在範圍內 —— Veros 的情境庫、嚴重度模型與報告格式
全是為合約審計設計的，套到其他語言不會得到有意義的結果。那些請用別的工具（例如 Claude Code 內建的
`/security-review`）。

此工具拆成兩層設計：

1. **第一層：語言/工具無關的 CLI**（`veros/cli.py`）—— 環境健檢、跑掃描、產報告，純 Python + 標準 Cli。
2. **第二層：人工確認的分類流程**（`SKILL.md`）—— 「這個發現算不算數」需要工程判斷，刻意設計成必須有人確認才能繼續。

**這兩層的分工要說清楚**：第一層（Step 0/1/3）是純確定性的，同一份輸入永遠得到同一份輸出，可以獨立於 Claude 執行、也可以把 `veros report` 的 exit code 接進 CI 當交付閘門。第二層（Step 2）**需要 LLM 輔助**：它要求對每一份合約跑完 `references/logic_scan.md` 的全部情境、做領域事故比對、產出資產托管地圖與特權角色權限表、並逐筆寫出引用行號的判斷依據（實際案例達 110 筆）——這不是「照著標準手動填」能達成的工作量。Step 2 裡**機械性可檢查的部分**（共用理由、必填欄位、High 降級與 High 判誤報）由 `veros review` 負責，那部分刻意不交給 LLM。

## 機密等級

這個 repo 內含可回溯到特定客戶專案的稽核案例引用，以及來自真實案件的去識別化素材（見
`references/domain_incidents/`、`references/logic_scan.md`）。**整個 repo 屬內部工具，機密等級為
「內部限閱」**：不得交給第三方、不得公開發布，也不得原封不動包進客戶交付物。帶進客戶專案的
submodule 部署方式（見下方「安裝與部署」）不改變這個等級——那是給我方工程師在客戶環境裡用的，
不是給客戶看的。

## 架構

```
veros/                      ← 這個 repo
├── README.md
├── pyproject.toml          ← pip 套件定義，指令入口 veros = veros.cli:main
├── SKILL.md → veros/SKILL.md          （symlink，Claude Code skill 佈局要求放根目錄）
├── references → veros/references      （symlink，同上）
├── veros/                  ← 套件本體，pip install 後這些跟著走
│   ├── cli.py              ← 統一入口，把子指令分派出去
│   ├── run.py              ← veros run：整條流程串起來（--brief / --apply 兩種 Step 2）
│   ├── init_audit.py       ← audit/ 手寫文件的範本，缺檔時由 run 自動建立
│   ├── config.py           ← veros config：AI 判讀用的模型與 API key
│   ├── docs.py             ← veros docs：印出隨套件安裝的方法論
│   ├── env_check.py        ← Step 0：環境健檢（veros doctor）
│   ├── scan.py             ← Step 1：跑 slither + 過濾 + scope.json + 分類 skeleton
│   ├── filter_results.py   ← 依 src 路徑過濾 slither JSON
│   ├── triage.py           ← Step 2：AI 判讀。打 API，或 --emit-brief 產工單交給既有 agent
│   ├── review.py           ← Step 2：classification.json 的機械品質檢查
│   ├── confirm.py          ← Step 2：人工簽核 AI 草稿，清掉 ai_drafted 標記
│   ├── report.py           ← Step 3：串 build_report + md_to_pdf
│   ├── build_report.py     ← 驗證分類 + 判閘門 + 產 report.md 與工作底稿
│   ├── md_to_pdf.py        ← report.md → report.pdf（CJK 斷行、避頭尾、字型偵測）
│   ├── SKILL.md            ← 完整流程指引，也是驅動 LLM 的依據
│   └── references/
│       ├── pitfalls.md         ← 實測踩過的坑
│       ├── severity_grading.md ← 嚴重度評定與閘門行為
│       ├── logic_scan.md       ← 情境庫，補 Slither 抓不到的業務邏輯漏洞
│       └── domain_incidents/   ← 各業務領域的公開事故模式
├── scripts/
│   └── regen_fixtures.sh   ← 迴歸測試：重跑兩個 fixture，比對閘門判定
└── test-fixtures/
    ├── vulnerable-vault/   ← 第四級 ground truth：9+1 個已知漏洞（含 Slither 漏報對照）
    └── timelock-vault/     ← 第二級 ground truth：可交付案例
```

流程對照表：

| Step | 內容 | 誰負責 | 對應指令 |
|---|---|---|---|
| 0 | 環境健檢 | 自動 | `veros doctor` |
| 1 | 跑 Slither + 過濾 + 產範圍清單 | 自動 | `veros scan`（重掃帶 `--prev-classification` 沿用上次分類） |
| 2 | 分類 A/B/C/D + 情境式邏輯掃描 + 記錄人工發現 | **AI 起草、人工確認** | `veros triage`（打 API）或 `veros triage --emit-brief`（交給既有 agent）；`veros review` 機械檢查；`veros confirm` 人工簽核 |
| 3 | 產出交付報告 + 工作底稿 | 自動 | `veros report` |

整條一次跑完：`veros run`（打 API）或 `veros run --brief` → agent 完成工單 → `veros run --apply`。

抑制註解（原 Step 3）已不在編號流程內，改為**選配的收尾動作**：它是開發團隊的 CI 衛生實務，不是審計實務（專業審計公司不改客戶程式碼），外部標的一律跳過。詳見 `SKILL.md` 最後一節。

**兩份產出物**：

| | 交付報告 | 工作底稿 |
|---|---|---|
| 路徑 | `<專案>/audit/report/report.pdf`（+ `report.md`） | `<專案>/audit/worksheet.md` |
| 讀者 | 甲方 | 我方複核者、下次重掃的人 |
| 內容 | 封面／目錄／檢測範圍與方法／摘要（含協定理解）／檢測結果（依處置分類分組）／附錄 | 全量逐筆分類、複核提醒、完整覆蓋矩陣 |
| git | 隨交付物 | **必須 gitignore**（含內部語氣），未忽略時 CLI 會警告 |

`test-fixtures/` 底下是**已知答案的迴歸測試樣本**（測試夾具）：合約與漏洞都是刻意設計、事先寫死答案的，用來測「這套 kit 本身」準不準——不是要交付的產品合約，規則與流程文件也不依賴它們。每個樣本附一份解答卷（如 `vulnerable-vault/VULNERABILITY_CATALOG.md`，記錄植入了哪些漏洞、Slither 抓到/漏掉哪些）；改動判級邏輯或情境庫後，重跑這兩個樣本驗證等級與漏報對照沒被改壞。

## 安裝與部署

這個 kit 是獨立的工具 repo（Python 套件在 `veros/`，倉庫根目錄的 `SKILL.md` 與 `references/` 是指向它的 symlink），有兩種用法：

1. **獨立使用（不需要 Claude Code）**：`pip install` 之後直接用 `veros` 指令，不必知道 repo 放在哪；要跑未安裝的工作區版本則是 `python3 <kit>/veros/cli.py`。
2. **作為 Claude Code skill**：Claude Code 的 skill 發現機制要求 `SKILL.md` 位在 `.claude/skills/<skill 名>/` 的根目錄，所以要讓 `/security-scan` 跑得起來，得把方法論檔案放到這個固定位置。**這條路也需要先 `pip install`**——`SKILL.md` 自己不含邏輯，它每一步都在呼叫 `veros` CLI。

   實際要帶的檔案是 `SKILL.md` + `references/`（`SKILL.md` 會讀 `references/` 底下的文件，缺一份 Step 2/3 會找不到依據或直接報錯）；`test-fixtures/` 是 kit 自己的迴歸測試樣本，掃描流程不會讀它，**不需要**帶進新專案。`README.md` 對執行流程不是必要的，帶不帶都行。

   **已經 pip install 的話最省事**：`SKILL.md` 與 `references/` 是跟著 wheel 一起裝的（`veros docs --path` 會印出位置），symlink 過去就好，之後升級 kit 時 skill 內容也一起更新：
   ```bash
   cd <新專案根目錄>
   mkdir -p .claude/skills
   ln -s "$(veros docs --path)" .claude/skills/security-scan
   ```

   或以 git submodule 帶入（推薦，之後 `git submodule update --remote` 可以拉 kit 更新）：
   ```bash
   cd <新專案根目錄>
   mkdir -p .claude/skills
   git submodule add https://github.com/KaifeinDev/veros.git .claude/skills/security-scan
   ```

   `git submodule add` 一定會把整個 repo（含 `test-fixtures/`）拉下來，沒有「只抓部分路徑」的選項。如果想讓工作目錄乾淨、不帶 `test-fixtures/`，接著設 sparse-checkout（cone mode 下根目錄檔案預設保留，只有你指定的子目錄會被 checkout）：
   ```bash
   cd .claude/skills/security-scan
   git sparse-checkout init --cone
   git sparse-checkout set veros
   cd -
   ```
   這個設定存在 submodule 自己的 `.git/info/sparse-checkout`，**不會**隨 `.gitmodules` 同步給其他人——同事 clone 這個專案並跑 `git submodule update --init` 後預設仍會拉出完整內容，得自己重跑上面兩行 `git sparse-checkout` 指令，或把它們包進專案的 setup script（例如 `Makefile` / `scripts/setup.sh`）裡跟 `submodule update --init` 一起執行。

   或直接複製（不需要保留 kit 自己的 git 歷史時）：
   ```bash
   cd <新專案根目錄>
   mkdir -p .claude/skills/security-scan
   cp -rL <kit 路徑>/{SKILL.md,references} .claude/skills/security-scan/
   ```

## 專案裡的檔案配置

Veros 在一個受檢專案裡寫的東西全部在 `audit/` 底下，各步驟的預設值都指向這裡：

```
audit/
├── scan/            ← Step 1 產物（results_before.json / scope.json / scan_env.json / skeleton）
├── overview.md      ← 你寫：協定理解，進報告的「摘要」章（缺檔時自動產生範本）
├── scope_note.md    ← 你寫：本次偏離標準程序之處，沒有就留著空範本（自動產生）
├── worksheet.md     ← 內部工作底稿，含內部語氣與全量明細
└── report/          ← 交付物：report.md + report.pdf
```

**只有 `audit/report/` 可以交給甲方**，其餘都是內部文件。工作底稿刻意放在 `audit/` 根目錄而不是
`report/` 裡面，所以整個 `report/` 目錄拿走就不會夾帶到它。`audit/` 的其他部分建議加進 `.gitignore`。

## 使用方式

### 先確認這三件事

1. **環境裝好了**：Foundry（`forge`）或 Hardhat（`npx hardhat`）、Slither（`slither`）、系統 python 的
   `fpdf2`、一套 CJK 字型。全部步驟見下方「環境安裝」，`veros doctor` 會逐項檢查並告訴你缺什麼。
2. **在要掃的專案根目錄下執行**。Veros 寫出來的所有檔案都在那個專案的 `audit/` 底下（見上方「專案裡的
   檔案配置」），不會動到專案的其他部分。
3. **`--src-prefix` 指向合約原始碼的根目錄**：Foundry 專案通常是 `src/`，Hardhat 專案通常是 `contracts/`。
   這個參數決定哪些發現算「專案自己的」—— 給錯的話 `lib/` 底下相依套件的發現會混進來。

### 選一條路

掃描（Step 1）與產報告（Step 3）四條路完全一樣，差別只在 **Step 2 的分類由誰起草**：

| 怎麼跑 | 分類誰起草 | 需要 | 適合 |
|---|---|---|---|
| **A.** `/security-scan` | 對話裡的 Claude | Claude Code | 想邊看邊確認、過程中可以隨時追問 |
| **B.** `veros run` | Veros 自己打 Anthropic API | API key（另計費） | 要一行跑完、可塞進腳本 |
| **C.** `veros run --brief` → 你的 agent → `--apply` | 你自己的 agent 讀工單完成 | 不需要 API key | 有 Claude Pro／Max 訂閱（訂閱不含 API key） |
| **D.** 逐步手動 | 你自己 | — | 要精細控制每一步，或在除錯 |

**不管走哪條，AI 起草的分類都只是草稿**：每一筆都標記為未經人工確認，閘門一律不判為可交付，PDF 第一頁
就寫明。分類是整份報告唯一的可信度來源，必須有人逐筆看過才算完成 —— 做法見下方「人工確認」。

#### A. 有 Claude Code：跑 `/security-scan`

在專案根目錄的 Claude Code 對話裡輸入：

```
/security-scan
```

（要連 `lib/` 底下相依套件本身的發現也納入報告，用 `/security-scan --full-audit`。）

Claude 會照 `SKILL.md` 走完整流程：自動跑 Step 0（環境健檢）與 Step 1（掃描），把發現列給你看並**停下來
等你確認分類**（Step 2），確認後才產出報告（Step 3）。加抑制註解是選配的收尾動作，不在編號流程內。

#### B. `veros run`：一行跑完（打 API）

```bash
veros config --api-key sk-ant-...                      # 或 export ANTHROPIC_API_KEY
veros run --src-prefix src/ --client "<甲方名稱>"
```

依序跑 doctor → scan → AI 判讀 → review → report，產出草稿報告。接著做下方的「人工確認」。

#### C. `veros run --brief`：不打 API，交給你自己的 agent

```bash
veros run --brief --src-prefix src/            # 跑到產出工單為止，不打 API
# 讓你的 agent 讀 audit/scan/brief/README.md 逐份完成，結果寫進 brief/results/
veros run --apply --client "<甲方名稱>"         # 套用 → review → report
```

工單裡已經包含原始碼、情境庫與 schema，agent 不需要額外 context，也不需要 API key。驗證仍留在 Veros
這邊 —— 分類值、必填欄位、編號能不能對上掃描結果都會檢查，不合格的會列出來且**不寫入**。

#### D. 逐步手動執行

```bash
# 安裝（一次）
python3 -m pip install --user git+https://github.com/KaifeinDev/veros.git

# Step 0：環境健檢。exit code 0 才代表可以往下走
veros doctor --src-prefix src/

# Step 1：跑 Slither 掃描，預設寫到 ./audit/scan
veros scan --src-prefix src/
#   --full-audit               連 lib/ 底下相依套件的發現也保留
#   --exclude-path <前綴>      排除 src/ 內部的 mock／測試樁目錄（可重複）
#   --prev-classification <上次的 classification.json>
#                              重掃時沿用上次分類：同一筆發現自動帶入上次的
#                              category/dev_note（標記 carried_from_previous），
#                              只有新發現留空；上次的 manual_findings 原樣帶入待重新確認

# Step 2：分類。這一步是人工判斷關卡，三種做法
veros triage                   #  (a) 打 API 逐筆起草，全部標記為草稿
veros triage --emit-brief      #  (b) 產工單，交給你既有的 agent
#  (c) 純手工：把 classification_skeleton.json 複製成 classification.json 自己填
#      —— 要填什麼見下方「Step 2 要填的欄位」

# Step 2 收尾：機械檢查（共用理由、必填欄位、High 降級／High 判誤報）
veros review --classification ./audit/scan/classification.json

# Step 3：產出交付報告 + 工作底稿
veros report --client "<甲方名稱>" \
  --engagement-from 2026-08-01 --engagement-to 2026-08-14
#   --scan-dir/--overview/--scope-note/--out-dir 都有 audit/ 底下的預設值，通常不用給
#   --include-false-positives  把誤報（C）也逐筆列進報告（預設不列）
#   --skip-pdf                 只產 report.md，不轉 PDF
```

### 人工確認

AI 起草的分類要逐筆簽核過，閘門才會把報告判為可交付：

```bash
veros confirm --list          # 還有哪些待確認
veros confirm ISL-02 ISL-03   # 確認你已經讀過的（可一次給多筆編號）
veros report                  # 重新評定，產出乾淨版面的報告
```

`veros report` 的 **exit code 就是交付閘門**：`0` = 可交付；`3`／`4` = 不可交付（報告照常產出，但開頭
帶「內部工作版本」標記，僅供內部追蹤）；`2` = 驗證失敗，不產出報告。完整判定規則見
`references/severity_grading.md`。

### Step 2 要填的欄位

從 Step 1 產出的 `classification_skeleton.json` 開始，**不要手打**。skeleton 已預填每筆的
`id`/`check`/`impact`/`file`/`lines`/`description`，**預填的 `check`/`impact`/`file`/`lines` 不要動** ——
Step 3 會逐筆核對，不一致直接拒絕產報告。

每筆都要填：

- `category`：`A` 已確認需修復／`B` 可接受風險／`C` 誤報／`D` 待確認。**信心不足一律 D，不要猜。**
- `dev_note`：具體理由，禁止「沒問題」這類空泛字眼。
- `severity`：業界五級（Critical／High／Medium／Low／Informational），skeleton 已預填工具的對應值。
- `severity_rationale`：只有判得比工具輕（降級）時必填。

依分類追加：

- `category = A`：`remediation`（怎麼修）
- `category = D`：`confirm_what`／`confirm_who`／`confirm_branches` 三格。**D 類不得停在問句。**

判定成立的發現（`category = A`／`D` 與全部 `manual_findings`）另外要寫報告正文的四段：`title`（根因 +
影響的一句話標題，不是 detector 名稱）、`explanation`（哪個函式、正常該怎麼運作、為何出錯）、
`impact_detail`（具體危害與業務損失）、`proof_of_concept`（攻擊邏輯或可重現的測試碼）。缺的話報告會
顯示「待補」並在 stdout 列出，不擋產出。

**還要另外跑一輪邏輯漏洞掃描**：依 `references/logic_scan.md` 的十條情境（權限檢查的實作、未保護的狀態
變更、旗標未落實、滑點、價格源…）對每一份合約跑過，這是補 Slither 抓不到的業務邏輯漏洞的步驟。命中的
情境與其他讀碼發現的工具外問題寫進 `manual_findings[]`（格式範例見 `SKILL.md`），覆蓋紀錄寫進
`scenario_coverage`。完整的分類標準與欄位定義以 `SKILL.md`「Step 2」為準。

### 只想快速看一次掃描結果

`veros report` 的 `--classification`／`--env`／`--scope`／`--overview`／`--scope-note` 都是選填 —— 沒提供時
報告對應章節會註明「未提供」而不是報錯。所以可以只跑 `veros scan` 再直接 `veros report`，先看一眼掃描
結果，之後再回頭走完整分類流程。`--overview` 的內容進「摘要」章（協定怎麼運作、資產保管、角色與權限），
`--scope-note` 進「檢測範圍與方法」章末尾，用來揭露這次掃描偏離標準程序之處（例如為了讓工具跑起來而
暫時改過原始碼，使部分檔案雜湊與交付版本不符）。

### CLI 子指令細節

**`veros doctor`**（`env_check.py`）
- 檢查 `foundry.toml` 存在且 `src` 不是危險的 `"."`
- 跑 `forge build`
- 掃描 `--src-prefix` 底下的 `.sol` 檔，比對 OpenZeppelin v4/v5 API 特徵（`__UUPSUpgradeable_init`、`_beforeTokenTransfer` vs `_update`、`__Ownable_init` 有無參數），同一檔案內出現互斥版本特徵會被標成 `CONFLICTING` 並要求人工處理，**不會自動選版本**
- 蒐集 solc / slither / forge 版本與 `lib/` 底下每個相依套件的版本（git tag 或 `package.json`）
- exit code：0 = 全部通過；1 = 有項目需要人工處理

**`veros scan`**（`scan.py`）
- 跑 `slither . --json`
- 用 `filter_results.is_own_finding` 過濾（`--full-audit` 跳過過濾）
- 寫 `results_raw.json` / `results_before.json` / `scan_env.json` / `scope.json` / `classification_skeleton.json` 到 `--out-dir`（`scope.json` 記錄納入掃描的每個 `.sol` 檔、行數與 sha256，以及 `--exclude-path` 的排除清單，供報告的「掃描範圍」章節使用）（skeleton 已預填每筆發現的所有欄位，Step 2 只需填 `category` / `dev_note`，杜絕手抄造成的分類檔與掃描結果脫鉤）
- `--prev-classification <path>`：跨次掃描的增量分類 —— 與上次分類檔比對（先 check + file + 起始行號完全比對；行號位移時退用 check + file、且兩邊都唯一才配對，避免張冠李戴），對上的沿用 category/dev_note 並標記 `carried_from_previous`（`exact`/`fallback`），新發現留空，上次的 manual_findings 原樣帶入（標 `manual`）；「上次有、這次沒有」的項目列在終端機供確認已修復。沿用結果只可能把等級拉低不可能拉高（未分類視同 D），fallback 與 manual 標記的項目 Step 2 須逐筆複核
- 印出摘要表（check / impact / 位置 / 描述）方便直接看

**`veros review`**（`review.py`）
- 讀 `classification.json`，做**規則式**檢查（不做語意判斷）：多筆共用完全相同的 `dev_note`、`dev_note` 過短、A 類缺 `remediation`、D 類缺三格、缺 `severity`、降級未附 `severity_rationale`
- 另外單獨成節列出兩組重點：**工具判 High 而我方判誤報（C）**、**工具判 High 而我方降級** —— 這是整份分類裡權重最高、甲方最可能挑戰的判斷
- exit code：`0` = 無待抽查項目；`1` = 有待抽查項目（**提醒，不是錯誤**）；`2` = 檔案讀不到
- `--json` 輸出結構化結果

**`veros report`**（`report.py`）
- 先驗證 `classification.json`：逐筆與 `--before` 的掃描結果核對（比對鍵：check + file + 起始行號），對不上的過期項目、無效的 `category`/`impact`/`severity` 值、`impact` 與掃描結果不符、B/C 類缺 `dev_note`、A 類缺 `remediation`、D 類缺確認三格、降級缺 `severity_rationale`、`id` 格式錯或重複，一律列出錯誤並以 exit code `2` 結束、**不產出報告**；掃描有但分類檔漏掉的發現則視同「未分類」（判級時當 D 算，未分類的 High 直接第四級）
- 呼叫 `build_report.py` 產生 `report.md`（封面、目錄，以及三個章節：檢測範圍與方法／摘要（含協定理解）／檢測結果（發現依處置分類分組），末尾附處置分類說明）與 `audit/worksheet.md`（工作底稿）
- 呼叫 `md_to_pdf.py` 轉成 `report.pdf`（`--skip-pdf` 可跳過這步，只留 markdown）
- **exit code 即交付閘門**（見 `references/severity_grading.md`）：`0` = 可交付；`3`/`4` = 不可交付（報告照常產出但帶「內部工作版本」標記，僅供內部追蹤）；`2` = 驗證失敗。**等級本身不出現在報告本文**，只驅動 exit code 與浮水印
- 自動探測系統上哪個 python 裝有 `fpdf2`（即使目前在 Slither 的 venv 底下執行也一樣能找到系統 python），找不到就用 `SECURITY_SCAN_REPORT_PYTHON` 環境變數指定
- `--font` 可指定 CJK 字型路徑（對應 `md_to_pdf.py` 的 `SECURITY_SCAN_CJK_FONT`）

### 環境安裝

```bash
# Veros 本身。用 `python3 -m pip` 而不是 `pip` —— macOS 沒有 `pip` 這個指令，
# 而 `pip3` 有可能指向跟你的 `python3` 不同的直譯器。
python3 -m pip install --user git+https://github.com/KaifeinDev/veros.git
```

裝完若看到 `The script veros is installed in '.../bin' which is not on PATH`，
把那個目錄加進 PATH 才能直接打 `veros`（macOS 系統 Python 通常是
`~/Library/Python/3.9/bin`）：

```bash
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**Python 版本**：3.9 以上皆可。3.9 會裝到 fpdf2 2.8.4，3.10+ 會裝到 2.8.8 以上；
兩者都可用，中間的 2.8.7 有字型子集化 bug 已在依賴中排除（見 `veros docs pitfalls` 第 6 條）。

```bash
# Slither（建議裝在 venv，避免污染系統 python）
python3 -m venv venv && source venv/bin/activate
pip install slither-analyzer
solc-select install <version> && solc-select use <version>

# 報告產生需要的套件，裝在系統 python（不是上面的 venv）
python3 -m pip install --user --break-system-packages "fpdf2>=2.8.4,!=2.8.7" matplotlib

# 中文字型：報告是繁中，PDF 需要涵蓋 CJK 的字型。macOS 不內建 Noto Sans CJK，
# 裝到 ~/Library/Fonts/ 即可自動偵測；Linux 用 apt install fonts-noto-cjk。
# 也可以用 --font 或 $SECURITY_SCAN_CJK_FONT 指定任一 .ttc/.otf/.ttf。
```

`report` 會另外挑一個「有 fpdf2 + matplotlib」的直譯器來跑產報告的部分（Slither 的 venv
會遮蔽 `python3`，所以不能直接沿用當下的）。挑錯時用 `$SECURITY_SCAN_REPORT_PYTHON` 指定。

## 測試 Fixtures

`test-fixtures/` 底下是兩組已知答案的迴歸測試樣本，合約與掃描結果都是刻意設計、事先寫死的，
用來驗證這套 kit 本身的判級邏輯有沒有被改壞，不是要交付的產品合約。兩組合起來覆蓋交付閘門
的兩側，各自附一份完整跑完 Step 0～3 產出的報告：

- **vulnerable-vault** — 不可交付（閘門 exit 4）的 ground truth，未加抑制註解。
  合約與已知漏洞明細見 `test-fixtures/vulnerable-vault/VULNERABILITY_CATALOG.md`。
- **timelock-vault** — 可交付（閘門 exit 0）的 ground truth，實際加過抑制註解：
  `src/TimelockVault.sol.original` 是加抑制註解前的最原始版本，`src/TimelockVault.sol`
  是加上抑制註解後、實際交付的版本，兩份都保留在 repo 裡方便直接比對。設計細節見
  `test-fixtures/timelock-vault/FIXTURE_NOTES.md`。

完整報告：

- [可交付範例｜timelock-vault 報告](test-fixtures/timelock-vault/security-scan-report/report.md)
- [不可交付範例｜vulnerable-vault 報告](test-fixtures/vulnerable-vault/security-scan-report/report.md)

