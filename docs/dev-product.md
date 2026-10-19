# 开发与生产：注意事项与操作手册

> 生产版本于 **2026-10-19** 锁定，已正式上线使用。
> 本文件是开发、上线、回滚的唯一操作依据。流程有变化时，先改本文件，再照做。

---

## 〇、阅读须知

- 标 **【禁止】** 的事项，任何情况下都不做。
- 标 **【必须】** 的步骤，不能跳过；跳过一步，就从头重来。
- 每一步命令后面都写了「确认」，确认不通过就停下，不往下做。
- 凡是写「上线」的操作，都会影响正在使用的真实用户。

---

## 一、环境总览

### 1.1 三个环境

| | 本地开发 | 线上前端 | 线上后端 |
|---|---|---|---|
| 地址 | http://localhost:5173（接口 :8000） | https://emotion.knettf.com | https://emotion-api.knettf.com |
| 运行位置 | 本机 | Cloudflare Worker `emotion-talk-frontend` | 服务器 `Lab-tailscale[public-linux]` 上的 Docker 容器，经 Cloudflare Tunnel 对外 |
| 数据库 | 本地 `backend/data/` | 无 | 服务器 `~/emotion-talk/data/app.db` |
| 配置 | `backend/.env`、`frontend/.env` | `frontend/.env.production`（打包时写入） | 服务器 `~/emotion-talk/.env` |
| 启动/更新方式 | `./scripts/dev.sh start` | `./scripts/deploy.sh --frontend` | `./scripts/deploy.sh --backend` |

### 1.2 git 分支

| 分支 | 用途 | 规则 |
|---|---|---|
| `prod` | 与线上完全一致 | 只在上线时从 `dev`（或 `hotfix`）合并进来；不在上面直接改代码 |
| `dev` | 日常开发 | 所有日常修改在这里提交、推送 |
| `main` | 已弃用 | 不再提交；GitHub 默认分支改为 `dev` 后删除 |

远程仓库：`https://github.com/Wk-P/emotion-talk-assistant`

### 1.3 锁定基线（2026-10-19）

| 项目 | 值 |
|---|---|
| 代码提交 | `593e7de`（`prod`、`dev` 当前都指向它） |
| 前端 Cloudflare 版本 | `912f5b78-2179-430f-974b-968ae9c21a2e`，2026-10-19 15:04（日本时间）发布 |
| 后端镜像 | `soar009/emotion-talk-backend:latest`（会被下次部署覆盖，见 4.4） |

### 1.4 git 与线上的关系

- **git 和线上之间没有任何自动连接。** 已核实：仓库里没有 GitHub Actions；Cloudflare 后台没有连接 Git，所有部署记录都是「已手动部署 / Wrangler」。
- 因此 `commit`、`push`、建分支、打标签、合并，**都不会改变线上**。
- 线上只会在以下两种情况下改变：
  1. 执行 `scripts/deploy*.sh`；
  2. 在 `frontend/` 里执行 `wrangler deploy` 或 `npx wrangler deploy`。

---

## 二、红线（禁止事项）

1. **【禁止】在 Cloudflare 后台点「连接 Git 存储库 / 自动化您的 CI」。** 连上后推送代码就可能自动上线，锁定失效。
2. **【禁止】在 `prod` 以外的分支上执行部署脚本。** 脚本目前不检查分支，在 `dev` 上跑会把未测完的代码直接发到线上。
3. **【禁止】在 `frontend/` 里随手执行 `wrangler deploy`。** 前端没有预览环节，执行即生效。`npm run preview` 只在本地运行，可以用。
4. **【禁止】修改服务器 `.env` 里的 `RECORD_ENCRYPTION_KEY`。** 改了之后，数据库里已加密的记录全部无法解开，且无法恢复。
5. **【禁止】随意修改服务器 `.env` 里的 `JWT_SECRET`。** 改了之后所有用户和管理员立即被登出。
6. **【禁止】直接在服务器上改代码、改数据库。** 下次部署时 `rsync --delete` 会把服务器代码覆盖成本地版本，手改的内容会丢。
7. **【禁止】把本地测试账号（`testadmin`、`testuser`）用在线上。** 这些账号只给本地数据库用。
8. **【禁止】在 `prod` 分支上执行 `git push --force`**，除非是按 5.2 回滚、且已确认。
9. **【禁止】把 `.env`、数据库文件提交到 git。**

---

## 三、必须了解的风险

| # | 事项 | 后果 | 对策 |
|---|---|---|---|
| 1 | 前端部署即生效 | 页面坏了，所有用户立刻看到 | 上线前本地完整测试；出问题按 5.1 在 Cloudflare 后台回滚，1 分钟内恢复 |
| 2 | 后端部署会重启容器 | 正在对话的用户断开约 10–30 秒 | 选没人使用的时段；提前通知管理员 |
| 3 | 后端启动时自动改数据库（`backend/app/db/session.py`） | 会加字段，还会**删除未使用的会话及其消息、记录、总结卡片**，删除不可撤销 | 部署脚本会先自动备份；改了数据库相关代码的版本，部署前再手动备份一次（4.2） |
| 4 | 部署会把本地 `backend/.env` 里的 `OPENAI_API_KEY`、`OPENAI_MODEL` 同步到服务器 | 本地填错，线上 AI 全部无法回复 | 部署前核对本地这两行；脚本最后会做 AI 检查，失败会报错 |
| 5 | 部署会用 `backend/app/db/seed.py` 覆盖危机求助资源 | 管理员在后台改过的同 id 资源会被覆盖 | 改 `seed.py` 前先和管理员确认 |
| 6 | 后端镜像标签固定为 `latest` | 新部署覆盖旧镜像，无法直接切回旧镜像 | 回滚靠「切回旧代码再部署一次」（5.2）；或部署前按 4.4 给旧镜像打版本标签 |
| 7 | 部署时旧镜像会被清理（`docker image prune`） | 没打标签的旧镜像会被删掉 | 同上，需要保留就先打标签 |
| 8 | 前端接口地址在打包时写死（`frontend/.env.production`） | 改了这个文件，前端会连到别的后端 | 非必要不改 |
| 9 | 数据库备份只保留最近 10 份，且都在同一台服务器上 | 服务器出故障时备份一起丢失 | 每次重要上线后，把备份拷一份到服务器以外（4.2） |

---

## 四、操作手册

### 4.1 日常开发

```bash
git checkout dev
git pull                      # 先同步远程
./scripts/dev.sh start        # 启动本地前后端
# 修改代码，在 http://localhost:5173 测试
./scripts/dev.sh stop

git status                    # 确认：没有 .env、数据库文件等不该提交的东西
git add <具体文件>
git commit -m "写清楚改了什么，不要只写 update"
git push
```

**确认：** `git branch` 显示 `* dev`。

### 4.2 上线前准备

**【必须】逐项打勾，全部通过才能进入 4.3。**

- [ ] 本地完整测试过：普通用户登录、完整走一遍对话流程、保存记录、导出；管理员登录、修改设置、保存。
- [ ] `cd frontend && npm run build` 成功，无报错。
- [ ] `cd backend && uv run python -c "import app.main"` 成功。
- [ ] 本地 `backend/.env` 里的 `OPENAI_API_KEY`、`OPENAI_MODEL` 是线上要用的正确值。
- [ ] 本次是否改了 `backend/app/db/`（数据库结构、启动迁移、`seed.py`）？改了就**手动备份数据库**：
  ```bash
  ssh "Lab-tailscale[public-linux]" 'sqlite3 ~/emotion-talk/data/app.db ".backup $HOME/emotion-talk-backups/manual-$(date +%Y%m%d-%H%M%S).db"'
  scp "Lab-tailscale[public-linux]":~/emotion-talk-backups/manual-*.db ~/emotion-talk-backup/
  ```
  确认：本机 `~/emotion-talk-backup/` 里有刚生成的文件，大小不为 0。
- [ ] 本次是否改了 `seed.py` 里的危机资源？改了就已和管理员确认。
- [ ] 已选好部署时间（用户少的时段），已告知管理员。
- [ ] 记下当前线上版本，作为回滚目标：
  - 前端：Cloudflare 后台 → `emotion-talk-frontend` → 部署 → 最上面一条的版本号。
  - 后端：`git log prod -1 --format=%h`。

### 4.3 上线

```bash
# 1. 确认工作区干净
git checkout dev
git status                    # 确认：nothing to commit, working tree clean
git pull

# 2. 合并到 prod
git checkout prod
git pull
git merge dev                 # 确认：没有冲突。有冲突就 git merge --abort，回 dev 解决
git push

# 3. 打版本标签（按顺序递增：v1.0、v1.1、v1.2……）
git tag -a v1.1 -m "上线内容简述"
git push origin v1.1

# 4. 再次确认分支
git branch                    # 确认：* prod

# 5. 部署
./scripts/deploy.sh              # 前后端都改了
./scripts/deploy.sh --backend    # 只改了后端
./scripts/deploy.sh --frontend   # 只改了前端

# 6. 回到开发分支
git checkout dev
```

**部署脚本会依次做什么（后端）：** 本地检查 → 同步代码到服务器 → 备份数据库 → 在服务器构建镜像 → 推送到 Docker Hub → 同步 OpenAI 配置 → 重启容器 → 健康检查 → AI 检查 → 同步危机资源 → 公网检查。

**确认：** 最后显示 `all done`，没有任何红色报错。

**中途失败时线上处于什么状态：**

| 失败在哪一步 | 线上状态 | 处理 |
|---|---|---|
| 1/3 本地检查 | 没变化 | 修好代码，从 4.3 第 1 步重来 |
| 同步代码 / 备份 / 构建 / 推送 | 服务器代码已更新，但容器还在跑旧版本，用户无感知 | 修好后重新部署；或切回上个标签重新部署，让服务器代码和线上一致 |
| 重启容器之后（健康检查、AI 检查失败） | **新版本已上线且有问题** | 立即按第五节回滚 |
| 前端部署 | Cloudflare 没有收到新版本则没变化；收到了就已生效 | 打开网站检查，有问题按 5.1 回滚 |

### 4.4 （可选）保留旧后端镜像

在部署**之前**执行，把当前线上镜像另存为版本标签，以后可直接切回：

```bash
ssh "Lab-tailscale[public-linux]" 'docker tag soar009/emotion-talk-backend:latest soar009/emotion-talk-backend:v1.0'
```

只是起别名，不会重启容器、不影响线上。

### 4.5 上线后检查

**【必须】部署完 10 分钟内完成：**

```bash
./scripts/status.sh
```

确认：容器 `Up`、`cloudflared` 为 `active`、两个健康检查都有返回、前端 `HTTP 200`。

然后人工检查（电脑浏览器 + 手机浏览器各一次，**不要用微信内置浏览器**，它访问不了接口）：

- [ ] https://emotion.knettf.com 能打开，样式正常
- [ ] 普通用户能登录，能开始对话，AI 有回复
- [ ] 历史记录能看到，旧数据没丢
- [ ] 管理员能登录，后台设置能打开、能保存
- [ ] 本次修改的功能本身正常

有任一项不通过，按第五节回滚，再查原因。

### 4.6 线上紧急修复

线上出问题，而 `dev` 上有还不能上线的改动时，不要合并 `dev`，从 `prod` 拉修复分支：

```bash
git checkout prod
git pull
git checkout -b hotfix
# 只改问题本身，本地测试
git add <具体文件> && git commit -m "修复：……"

git checkout prod
git merge hotfix
git push
git tag -a v1.1.1 -m "紧急修复：……" && git push origin v1.1.1
./scripts/deploy.sh --backend    # 或 --frontend，按实际改动
# 按 4.5 检查

git checkout dev
git merge hotfix                 # 修复同步回 dev，否则下次上线会把问题带回来
git push
git branch -d hotfix
```

---

## 五、回滚

**原则：先恢复服务，再查原因。** 回滚后在第六节记录。

### 5.1 前端回滚（最快，约 1 分钟）

1. 打开 Cloudflare 后台 → Workers 和 Pages → `emotion-talk-frontend` → 部署。
2. 找到上一个正常版本（4.2 记下的版本号）。
3. 点该版本右侧菜单 → 回滚 → 确认。
4. 浏览器强制刷新 https://emotion.knettf.com 确认恢复。

### 5.2 后端回滚

**方法 A：已按 4.4 保留了旧镜像**

```bash
ssh "Lab-tailscale[public-linux]" 'docker tag soar009/emotion-talk-backend:v1.0 soar009/emotion-talk-backend:latest && cd ~/emotion-talk && docker compose up -d'
./scripts/status.sh
```

**方法 B：用旧代码重新部署**

```bash
git checkout prod
git reset --hard v1.0             # 上一个正常的版本标签
git push --force origin prod      # 仅限回滚时使用
./scripts/deploy.sh --backend
./scripts/status.sh
git checkout dev
```

回滚后，`dev` 上的问题修好再按 4.3 重新上线。

**注意：** 后端回滚只换代码，**不会撤销数据库改动**。新版本已经加的字段会留着（旧代码一般能正常运行），已经删除的会话不会回来。需要恢复数据时看 5.3。

### 5.3 数据库恢复（会丢失备份之后的所有新数据，慎用）

只在数据确实损坏或误删时使用。

```bash
ssh "Lab-tailscale[public-linux]"
ls -lt ~/emotion-talk-backups/          # 选部署前那一份
cd ~/emotion-talk
docker compose stop backend
cp data/app.db ~/emotion-talk-backups/before-restore-$(date +%Y%m%d-%H%M%S).db   # 先保存当前库
cp ~/emotion-talk-backups/<选中的备份>.db data/app.db
docker compose start backend
curl -s http://localhost:8000/api/health
exit
```

恢复后按 4.5 全部检查一遍。

---

## 六、上线记录

每次上线、回滚都在下面加一行。

| 日期 | 版本标签 | 内容 | 前端版本号 | 结果 | 操作人 |
|---|---|---|---|---|---|
| 2026-10-19 | v1.0（593e7de） | 生产版本锁定 | 912f5b78 | 正常 | |
| （待上线） | v1.1 | 修复：部分 iPhone 上「每日记录」保存失败。手机把日期写成 `10/19/2026`，请求变成 `PUT /api/reflections/10/19/2026` 返回 404。`displayDay()`（frontend/src/utils/time.ts）改为按韩国时间手动计算 YYYY-MM-DD。只改前端 | | | |

---

## 七、待办

- [ ] GitHub：Settings → General → Default branch 改为 `dev`，之后删除 `main`（`git push origin --delete main`、`git branch -d main`）。
- [x] 给锁定版本打标签（2026-10-19 已完成）：`git checkout prod && git tag -a v1.0 -m "生产版本锁定" && git push origin v1.0`。
- [ ] 按 4.4 给当前线上后端镜像打 `v1.0` 标签。
- [ ] 把服务器 `~/emotion-talk/.env`（含加密密钥）备份到服务器以外的安全位置。
- [ ] 部署脚本加分支检查：不在 `prod` 分支就拒绝部署（目前只靠人工遵守第二节第 2 条）。
