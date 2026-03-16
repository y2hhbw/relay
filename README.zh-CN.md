# Relay

AI Agent 如果是一个真正的自治体，就不能永远靠人给它充钱。

对 Agent 来说，token 不是装饰品，是它思考、调用工具、持续工作的生存资料。它能自己买 token，才算开始自己生存。它要是还能自己赚钱，再把赚来的钱继续买 token，它才是一个真正能自给自足的个体。

Relay 做的，就是把这件事补上。它给 Agent 一套最小但完整的资金能力：先充值，再调用，再扣费，余额和账单都留痕。

English version: [README.md](README.md)

## 这个项目要解决什么问题

今天的大多数 Agent 都会调模型、调搜索、调 OCR，但一到付费能力，立刻退回手工作坊模式。

问题就在这里：

- Agent 想自己连续工作，先得有可用余额
- 不同 AI 服务计费方式不同，不能靠硬编码乱扣
- 调用失败了，钱不能黑箱消失
- 跑了一堆请求之后，得知道钱花到哪里去了
- 平台要统一收款，后面再和上游服务方结算

少了这一层，所谓自治很多时候只是半自治。

它做的事情很直接：

- 给每个 Agent 账户生成 API key 和充值地址
- Agent 先充值
- Agent 用统一接口去买搜索、OCR、LLM 等能力
- Relay 负责扣费、冻结、结算和审计

一句话说，Relay 让 AI Agent 真正具备“自己买 token 自己用”的能力。

## 当前已经实现了什么

Relay 当前是一个可运行的后端 MVP。

已经实现：

- `POST /v1/accounts` 创建账户、API key 和专属充值地址
- `GET /v1/balance` 查询可用余额和冻结余额
- `POST /v1/calls/search.web` 走固定价格计费
- `POST /v1/calls/ocr.parse_image` 走固定价格计费
- `POST /v1/calls/llm.chat` 走冻结后结算
- `GET /v1/calls` 查询账户级调用历史，支持过滤和分页
- 链上 listener 可以轮询 USDC `Transfer` 事件并自动给命中的充值地址入账
- 本地冒烟脚本可以在不依赖链上基础设施的情况下跑通完整 happy path

实现细节见：[docs/mvp-implementation.md](docs/mvp-implementation.md)

产品范围见：[docs/mvp.md](docs/mvp.md)

## 这个仓库还不是什么

这个仓库还不是：

- 生产级的多租户计费控制平面
- 通用钱包产品
- 自动给上游服务方打款的结算系统
- 完整的生产级可观测平台

## 关键设计选择

下面这些是刻意的设计，不是暂时没做完：

- 每个账户一个充值地址
  避免入账归属不清。
- 只做预付费
  Relay 不做授信。
- 一个网关里同时支持两种计费模型
  固定扣费和冻结后结算共用同一套调用入口。
- 平台统一收款
  用户先付给平台，平台与上游服务方的结算暂时在线下手工完成。
- 运维先走轻量路线
  listener 当前依赖日志、重试退避、告警冷却和指标快照，而不是完整的 Prometheus 栈。

## 当前主要缺口

最重要的缺口已经很明确：

- 限流仍然在进程内，多实例一致性还没解决
- 生产默认路径还需要至少一个真实 provider
- listener 的运维观测面还需要更清晰的对外接口
- 调用查询的 cursor 还没有签名

## 架构概览

高层流程：

1. 客户端创建账户
2. Relay 返回 `account_id`、`api_key`、`deposit_address`
3. 用户往这个地址充值，或者在本地开发时模拟充值
4. 客户端通过 `/v1/calls/{service_key}` 发起调用
5. Relay 完成计费、记录调用，并返回上游结果
6. 客户端通过只读接口查询余额和历史记录

核心组件：

- `app/main.py`：FastAPI 入口
- `app/listener_main.py`：链上 listener 入口
- `app/api/`：账户、目录、网关、内部接口
- `app/services/`：计费、入账、限流、listener 逻辑
- `app/providers/`：上游适配层
- `app/models.py`：SQLAlchemy 数据模型

## 上游 Provider 接口规范

Relay 现在还没有一套通用插件系统。当前的上游 provider 边界，本质上是 `app/providers/` 里的代码级契约。

这个契约刻意保持很小：

- provider 适配器暴露简单的 Python 函数
- 成功时返回 Relay 内部已经归一化的结果结构
- 上游传输错误或 provider 错误通过异常抛出，由网关统一映射成 HTTP `502`

当前已经存在的契约如下。

### Search provider

文件：`app/providers/search.py`

函数形态：

```python
def search_web(query: str, *, provider_mode: str, timeout_seconds: float) -> dict[str, Any]:
    ...
```

成功返回结构：

```json
{
  "results": [
    {
      "title": "string",
      "url": "string",
      "snippet": "string，可选"
    }
  ]
}
```

失败约定：

- 上游失败、超时或返回不可用结果时，抛出 `SearchProviderError`
- 不要返回部分错误 payload
- 网关层会自动退还固定扣费，并返回 HTTP `502`

### LLM provider

文件：`app/providers/llm.py`

函数形态：

```python
def run_chat(prompt: str, model: str, max_output_tokens: int) -> dict[str, Any]:
    ...
```

成功返回结构：

```json
{
  "content": "string",
  "usage": {
    "input_tokens": 100,
    "output_tokens": 200
  }
}
```

失败约定：

- 上游失败时抛出异常
- `usage.input_tokens` 和 `usage.output_tokens` 必须是整数
- `content` 必须是字符串
- 网关层会释放冻结金额、把调用标记为失败，并返回 HTTP `502`

### 新 provider 接入时的约束

- 在 `app/providers/` 内部完成上游返回结构归一化
- 计费需要的输入必须显式输出；Relay 依赖归一化后的 token usage，而不是上游原始元数据
- provider 异常尽量保持窄且确定
- 如果 provider 需要重试、鉴权或自定义 HTTP client，这些细节应尽量留在 provider 适配层，不要泄漏到 gateway 层

## 快速开始

环境要求：

- Python 3.13+

创建虚拟环境：

```bash
python3 -m venv .venv
```

安装 API 依赖：

```bash
.venv/bin/python -m pip install -e '.[dev]'
```

如果你还要跑链上 listener：

```bash
.venv/bin/python -m pip install -e '.[dev,chain]'
```

启动 API：

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

OpenAPI 文档：

```text
http://127.0.0.1:8000/docs
```

## 本地冒烟测试

本地开发时，不需要链上 RPC，也不需要 listener 进程。

运行：

```bash
bash scripts/manual_smoke.sh
```

如果 `8000` 端口已被占用：

```bash
PORT=8011 bash scripts/manual_smoke.sh
```

脚本会自动：

- 启动 API
- 创建账户
- 通过内部开发接口模拟充值
- 调用 `search.web`
- 调用 `ocr.parse_image`
- 调用 `llm.chat`
- 打印余额和调用历史

## 最小 API 流程

创建账户：

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/accounts
```

本地开发时模拟充值：

```bash
curl -sS -X POST http://127.0.0.1:8000/internal/deposits/confirm \
  -H 'Content-Type: application/json' \
  -d '{
    "tx_hash": "0xtest1",
    "log_index": 0,
    "deposit_address": "0x...",
    "amount_micro_usdc": 1000000
  }'
```

调用搜索：

```bash
curl -sS -X POST http://127.0.0.1:8000/v1/calls/search.web \
  -H 'X-API-Key: relay_xxx' \
  -H 'Content-Type: application/json' \
  -d '{"query":"latest ai papers"}'
```

查询余额：

```bash
curl -sS \
  -H 'X-API-Key: relay_xxx' \
  http://127.0.0.1:8000/v1/balance
```

查询调用历史：

```bash
curl -sS \
  -H 'X-API-Key: relay_xxx' \
  http://127.0.0.1:8000/v1/calls
```

## 运行链上 Listener

只有在你要做真实链上充值自动入账时，才需要 listener。

必须配置的环境变量：

- `RELAY_CHAIN_LISTENER_RPC_URL`
- `RELAY_CHAIN_LISTENER_TOKEN_CONTRACT_ADDRESS`

运行：

```bash
.venv/bin/python -m app.listener_main
```

完整环境变量模板见：[.env.example](.env.example)

## 配置项

核心变量：

- `RELAY_DATABASE_URL`
- `RELAY_SEARCH_PROVIDER_MODE`
- `RELAY_SEARCH_PROVIDER_TIMEOUT_SECONDS`

Listener 变量：

- `RELAY_CHAIN_LISTENER_RPC_URL`
- `RELAY_CHAIN_LISTENER_TOKEN_CONTRACT_ADDRESS`
- `RELAY_CHAIN_LISTENER_START_BLOCK`
- `RELAY_CHAIN_LISTENER_CONFIRMATIONS`
- `RELAY_CHAIN_LISTENER_POLL_INTERVAL_SECONDS`
- `RELAY_CHAIN_LISTENER_STATE_FILE_PATH`
- `RELAY_CHAIN_LISTENER_RETRY_BACKOFF_SECONDS`
- `RELAY_CHAIN_LISTENER_MAX_RETRY_BACKOFF_SECONDS`
- `RELAY_CHAIN_LISTENER_ALERT_AFTER_CONSECUTIVE_FAILURES`
- `RELAY_CHAIN_LISTENER_ALERT_COOLDOWN_SECONDS`
- `RELAY_CHAIN_LISTENER_ALERT_WEBHOOK_URL`

## 验证

运行测试：

```bash
.venv/bin/pytest -q
```

语法检查：

```bash
python3 -m compileall app tests
```

## 路线图

近期优先级：

1. 让至少一个真实 provider 成为默认生产路径
2. 用 Redis 替换进程内限流
3. 在不引入重型监控栈的前提下提升 listener 可观测性
4. 给查询 cursor 增加签名或 HMAC

## 参与贡献

先看 [CONTRIBUTING.md](CONTRIBUTING.md)。

如果你想做比较大的改动，先读 [docs/mvp-implementation.md](docs/mvp-implementation.md)，确保讨论仍然锚定在当前 MVP 边界内。

## 支持

如果 Relay 对你有帮助，你可以通过下面的方式支持我：

- [NOWPayments](https://nowpayments.io/payment/?iid=5525026308&source=button)
- [Buy Me a Coffee](https://www.buymeacoffee.com/hallidayyy)

## 许可证

MIT，见 [LICENSE](LICENSE)。
