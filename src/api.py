#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP API（异步 job + SSE 流式）

提供：
- GET  /health
- POST /research            同步生成（兼容）
- POST /research/start     异步创建任务，返回 `job_id`
- GET  /jobs/{job_id}      查询任务状态与最终结果
- GET  /jobs/{job_id}/stream  SSE 流式返回任务进度与最终结果
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.agents.coordinator import MarketResearchAgent, simple_research
from src.core.config import settings
from src.core.logger import logger

load_dotenv()

app = FastAPI(
    title="X-DeepAgents API",
    description="""
## 智能市场研究报告生成系统 API

基于 LangChain DeepAgents 框架构建的多代理协作研究系统。

### 功能特性
- 🔍 **市场研究** - 自动收集和分析市场信息
- 🤖 **多代理协作** - 支持复杂任务的代理协作
- 📊 **报告生成** - 自动生成结构化研究报告
- 🔄 **异步任务** - 支持长时间任务的异步执行
- 📡 **SSE 流式推送** - 实时获取任务进度

### 使用方式
1. **同步模式**: 直接调用 `POST /research`，等待结果返回
2. **异步模式**:
   - 调用 `POST /research/start` 获取 `job_id`
   - 通过 `GET /jobs/{job_id}/stream` 接收 SSE 流式进度
   - 或通过 `GET /jobs/{job_id}` 轮询状态
""",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "health", "description": "健康检查"},
        {"name": "research", "description": "研究任务相关接口"},
        {"name": "jobs", "description": "异步任务管理"},
    ],
)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    port: int
    output_dir: str


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="健康检查",
    description="检查服务是否正常运行，返回服务端口和输出目录信息",
)
def health() -> HealthResponse:
    return HealthResponse(status="ok", port=settings.PORT, output_dir=str(settings.OUTPUT_DIR))


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="研究主题/查询", examples=["中国新能源汽车市场分析报告"])
    simple: bool = Field(False, description="使用简单模式（单代理）")
    verbose: bool = Field(False, description="是否输出更详细日志（仅影响服务端）")
    include_full_result: bool = Field(
        False,
        description="是否返回完整 agent 结果（可能较大；默认不返回以避免序列化问题）",
    )

    # 预留字段，方便你后续扩展 job/stream/auth 等能力
    timeout_seconds: Optional[int] = Field(None, ge=1, description="执行超时（秒），默认使用代理内部策略")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "中国新能源汽车市场分析报告", "simple": False, "verbose": False},
                {"query": "人工智能行业投资机会研究", "simple": True, "verbose": False},
            ]
        }
    }


class SavedReport(BaseModel):
    name: str
    path: str
    mtime_unix: float


class ResearchResponse(BaseModel):
    query: str
    simple: bool
    response: str
    saved_reports: list[SavedReport] = []
    started_at_unix: float
    finished_at_unix: float
    elapsed_seconds: float
    raw: Optional[dict[str, Any]] = None


class JobStartResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "succeeded", "failed"]
    query: str
    simple: bool
    started_at_unix: Optional[float] = None
    finished_at_unix: Optional[float] = None
    elapsed_seconds: Optional[float] = None
    response: Optional[str] = None
    saved_reports: list[SavedReport] = []
    error: Optional[str] = None


def _list_reports(output_dir: str) -> dict[str, float]:
    d = Path(output_dir)
    if not d.exists():
        return {}
    result: dict[str, float] = {}
    for p in d.glob("*"):
        if p.is_file():
            result[p.name] = p.stat().st_mtime
    return result


def _diff_new_reports(before: dict[str, float], after: dict[str, float]) -> list[SavedReport]:
    saved: list[SavedReport] = []
    output_dir = str(settings.OUTPUT_DIR)
    for name, mtime in after.items():
        if name not in before:
            saved.append(
                SavedReport(name=name, path=str(Path(output_dir) / name), mtime_unix=mtime),
            )
    saved.sort(key=lambda x: x.mtime_unix)
    return saved


def _safe_extract_response_from_event(event: Any) -> Optional[str]:
    """
    尝试从 deepagents stream 的事件中提取最终文本。
    由于事件结构可能随 deepagents 版本变化，这里尽量做"宽松解析"。
    """
    try:
        if isinstance(event, dict):
            if event.get("messages"):
                last = event["messages"][-1]
                if hasattr(last, "content"):
                    return str(last.content)
                if isinstance(last, dict) and "content" in last:
                    return str(last["content"])
                if isinstance(last, str):
                    return last
            for key in ("content", "text", "response"):
                val = event.get(key)
                if isinstance(val, str) and val.strip():
                    return val

        if hasattr(event, "content"):
            val = getattr(event, "content")
            if isinstance(val, str) and val.strip():
                return val
    except Exception:
        return None

    return None


# -----------------------------
# 同步执行（兼容）
# -----------------------------
@app.post(
    "/research",
    response_model=ResearchResponse,
    tags=["research"],
    summary="同步执行研究",
    description="""
同步执行市场研究任务，请求会阻塞直到研究完成。

**注意**: 研究任务可能需要较长时间（通常 30秒-2分钟），建议：
- 对于简单查询，设置 `simple=true`
- 对于长时间任务，使用异步接口 `/research/start`
    """,
    responses={
        200: {
            "description": "研究完成，返回结果",
            "content": {
                "application/json": {
                    "example": {
                        "query": "中国新能源汽车市场分析",
                        "simple": False,
                        "response": "## 市场概述\n...",
                        "saved_reports": [{"name": "report_20240101.md", "path": "reports/report_20240101.md", "mtime_unix": 1704067200.0}],
                        "started_at_unix": 1704067100.0,
                        "finished_at_unix": 1704067200.0,
                        "elapsed_seconds": 100.0,
                    }
                }
            },
        }
    },
)
def research(req: ResearchRequest) -> ResearchResponse:
    """
    同步执行：请求返回时，报告已生成并写入 `reports/` 目录。
    """
    output_dir = str(settings.OUTPUT_DIR)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    before = _list_reports(output_dir)
    started_at = time.time()
    logger.info(f"API 开始研究（sync）: query='{req.query}', simple={req.simple}, verbose={req.verbose}")

    raw: Optional[dict[str, Any]] = None
    if req.simple:
        result_text = simple_research(req.query)
    else:
        agent = MarketResearchAgent(verbose=req.verbose)
        research_result = agent.research(req.query)
        result_text = research_result.get("response", "")
        if req.include_full_result:
            raw = {"full_result_str": str(research_result.get("full_result"))}

    after = _list_reports(output_dir)
    saved_reports = _diff_new_reports(before, after)
    finished_at = time.time()

    return ResearchResponse(
        query=req.query,
        simple=req.simple,
        response=result_text,
        saved_reports=saved_reports,
        started_at_unix=started_at,
        finished_at_unix=finished_at,
        elapsed_seconds=finished_at - started_at,
        raw=raw,
    )


# -----------------------------
# 异步 job + SSE
# -----------------------------
class JobState:
    def __init__(self, *, queue: asyncio.Queue):
        self.queue = queue
        self.status: str = "pending"
        self.query: str = ""
        self.simple: bool = False
        self.started_at_unix: Optional[float] = None
        self.finished_at_unix: Optional[float] = None
        self.response: Optional[str] = None
        self.saved_reports: list[SavedReport] = []
        self.error: Optional[str] = None


_jobs: Dict[str, JobState] = {}
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=int(os.environ.get("JOB_WORKERS", "4")))


def _push_event(loop: asyncio.AbstractEventLoop, state: JobState, payload: dict[str, Any]) -> None:
    """从线程中向 SSE 队列推送事件（线程安全）。"""
    try:
        msg = json.dumps(payload, ensure_ascii=False)
        asyncio.run_coroutine_threadsafe(state.queue.put(msg), loop)
    except Exception as e:
        logger.error(f"push event failed: {e}")


def _run_research_job(job_id: str, req: ResearchRequest, loop: asyncio.AbstractEventLoop) -> None:
    with _jobs_lock:
        state = _jobs.get(job_id)

    if state is None:
        return

    output_dir = str(settings.OUTPUT_DIR)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    before = _list_reports(output_dir)
    started_at = time.time()

    with _jobs_lock:
        state.status = "running"
        state.started_at_unix = started_at
        state.query = req.query
        state.simple = req.simple

    _push_event(
        loop,
        state,
        {
            "type": "status",
            "status": "running",
            "job_id": job_id,
            "started_at_unix": started_at,
        },
    )
    _push_event(loop, state, {"type": "progress", "message": "开始执行任务"})

    raw: Optional[dict[str, Any]] = None
    result_text: Optional[str] = None

    try:
        if req.simple:
            _push_event(loop, state, {"type": "progress", "message": "simple 模式：单代理执行"})
            result_text = simple_research(req.query)
        else:
            _push_event(loop, state, {"type": "progress", "message": "full 模式：开始流式协作执行"})
            agent = MarketResearchAgent(verbose=req.verbose)

            for event in agent.stream_research(req.query):
                extracted = _safe_extract_response_from_event(event)
                if extracted:
                    result_text = extracted
                    _push_event(loop, state, {"type": "stream", "chunk": extracted})
                else:
                    preview = str(event)
                    if len(preview) > 800:
                        preview = preview[:800] + "...(truncated)"
                    _push_event(loop, state, {"type": "stream", "chunk": preview})

            # 如果 stream 没提取到最终内容，尝试兜底同步生成
            if not result_text:
                _push_event(loop, state, {"type": "progress", "message": "未解析到最终文本，进行兜底同步生成"})
                research_result = agent.research(req.query)
                result_text = research_result.get("response", "")
                if req.include_full_result:
                    raw = {"full_result_str": str(research_result.get("full_result"))}
    except Exception as e:
        finished_at = time.time()
        with _jobs_lock:
            state.status = "failed"
            state.finished_at_unix = finished_at
            state.error = str(e)
        _push_event(loop, state, {"type": "error", "error": str(e)})
        _push_event(loop, state, {"type": "done", "status": "failed", "elapsed_seconds": finished_at - started_at})
        return

    after = _list_reports(output_dir)
    saved_reports = _diff_new_reports(before, after)
    finished_at = time.time()
    elapsed = finished_at - started_at

    with _jobs_lock:
        state.status = "succeeded"
        state.finished_at_unix = finished_at
        state.response = result_text or ""
        state.saved_reports = saved_reports

    _push_event(loop, state, {"type": "result", "saved_reports": [r.model_dump() for r in saved_reports]})
    if result_text:
        _push_event(loop, state, {"type": "final", "response": result_text})
    if req.include_full_result and raw is not None:
        _push_event(loop, state, {"type": "raw", "raw": raw})
    _push_event(loop, state, {"type": "done", "status": "succeeded", "elapsed_seconds": elapsed})


@app.post(
    "/research/start",
    response_model=JobStartResponse,
    tags=["research"],
    summary="异步启动研究任务",
    description="""
异步启动市场研究任务，立即返回任务 ID。

**使用流程**:
1. 调用此接口获取 `job_id`
2. 通过 `GET /jobs/{job_id}/stream` 接收 SSE 流式进度推送
3. 或通过 `GET /jobs/{job_id}` 轮询任务状态
    """,
    responses={
        200: {
            "description": "任务已创建",
            "content": {"application/json": {"example": {"job_id": "a1b2c3d4e5f6..."}}},
        }
    },
)
async def research_start(req: ResearchRequest) -> JobStartResponse:
    """
    异步启动研究任务：
    - 立即返回 job_id
    - 通过 SSE: GET /jobs/{job_id}/stream 获取进度与最终结果
    """
    job_id = uuid.uuid4().hex
    queue: asyncio.Queue = asyncio.Queue()
    state = JobState(queue=queue)

    with _jobs_lock:
        _jobs[job_id] = state

    loop = asyncio.get_running_loop()
    _executor.submit(_run_research_job, job_id, req, loop)
    return JobStartResponse(job_id=job_id)


@app.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    tags=["jobs"],
    summary="查询任务状态",
    description="查询异步研究任务的当前状态和结果。状态包括：pending（等待中）、running（执行中）、succeeded（成功）、failed（失败）",
    responses={
        200: {"description": "任务状态"},
        404: {"description": "任务不存在"},
    },
)
def job_status(job_id: str) -> JobStatusResponse:
    with _jobs_lock:
        state = _jobs.get(job_id)
        if not state:
            raise HTTPException(status_code=404, detail="job not found")

        finished_at = state.finished_at_unix
        started_at = state.started_at_unix
        elapsed = (finished_at - started_at) if (finished_at is not None and started_at is not None) else None

        return JobStatusResponse(
            job_id=job_id,
            status=state.status,  # type: ignore[arg-type]
            query=state.query,
            simple=state.simple,
            started_at_unix=state.started_at_unix,
            finished_at_unix=state.finished_at_unix,
            elapsed_seconds=elapsed,
            response=state.response,
            saved_reports=state.saved_reports,
            error=state.error,
        )


@app.get(
    "/jobs/{job_id}/stream",
    tags=["jobs"],
    summary="SSE 流式获取任务进度",
    description="""
通过 Server-Sent Events (SSE) 实时接收任务进度和结果。

**事件类型**:
- `status` - 状态变更（pending → running → succeeded/failed）
- `progress` - 进度消息
- `stream` - 流式内容片段
- `result` - 生成的报告文件信息
- `final` - 最终响应文本
- `done` - 任务完成
- `error` - 错误信息

**示例**:
```
data: {"type": "status", "status": "running", "job_id": "xxx", "started_at_unix": 1704067100.0}

data: {"type": "progress", "message": "开始执行任务"}

data: {"type": "stream", "chunk": "正在分析市场数据..."}

data: {"type": "final", "response": "## 研究报告\\n..."}

data: {"type": "done", "status": "succeeded", "elapsed_seconds": 100.0}
```
    """,
    responses={
        200: {"description": "SSE 事件流", "content": {"text/event-stream": {}}},
        404: {"description": "任务不存在"},
    },
)
async def job_stream(job_id: str) -> StreamingResponse:
    with _jobs_lock:
        state = _jobs.get(job_id)
        if not state:
            raise HTTPException(status_code=404, detail="job not found")

    async def event_generator():
        # SSE：每个事件以 "\n\n" 结尾
        while True:
            msg = await state.queue.get()
            yield f"data: {msg}\n\n"

            # 依据最终事件类型退出，避免无限阻塞
            try:
                payload = json.loads(msg)
                event_type = payload.get("type")
                if event_type in ("done", "error"):
                    break
            except Exception:
                continue

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def main() -> None:
    """
    方便你直接在本地运行：`python -m src.api`
    """
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", str(settings.PORT)))
    uvicorn.run("src.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
