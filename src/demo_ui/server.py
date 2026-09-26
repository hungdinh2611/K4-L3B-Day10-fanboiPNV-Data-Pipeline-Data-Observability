"""Demo UI (phong cach Brutalism): web server local (stdlib) de chay pipeline va xem ket qua.

Endpoints:
- GET  /                  -> giao dien (static/index.html)
- GET  /static/<file>     -> JS/CSS dung chung (demo-core.js)
- GET  /api/state         -> toan bo artifacts: metrics, quality, freshness, corruption log, test set, answers
- GET  /api/job           -> trang thai job dang chay + log
- POST /api/run/phase1    -> chay baseline pipeline (body: {"use_llm": bool})
- POST /api/run/corruption-> chay corruption -> repair flow (body: {"use_llm": bool})
- POST /api/ask           -> hoi RAG tren ca 3 collection (body: {"question": str})
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
import contextlib
import io
import json
import math
import sys
import threading
import time
import traceback
import webbrowser

from core.config import Settings, load_settings, require_llm_credentials

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_LOG_CHARS = 40_000
STATIC_TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}


def _stage_paths(settings: Settings) -> dict[str, dict[str, Path]]:
    paths = settings.paths
    return {
        "baseline": {
            "metrics": paths.baseline_metrics,
            "answers": paths.baseline_answers,
            "quality": paths.baseline_quality_report,
            "freshness": paths.freshness_report,
            "clean": paths.clean_json,
            "embeddings": paths.embeddings_json,
        },
        "corrupted": {
            "metrics": paths.corrupted_metrics,
            "answers": paths.corrupted_answers,
            "quality": paths.corrupted_quality_report,
            "freshness": paths.quality_dir / "corrupted_freshness_report.json",
            "clean": paths.corrupted_clean_json,
            "embeddings": paths.corrupted_embeddings_json,
        },
        "repaired": {
            "metrics": paths.repaired_metrics,
            "answers": paths.repaired_answers,
            "quality": paths.quality_dir / "repaired_quality_report.json",
            "freshness": paths.quality_dir / "repaired_freshness_report.json",
            "clean": paths.repaired_clean_json,
            "embeddings": paths.repaired_embeddings_json,
        },
    }


def _sanitize(value: Any) -> Any:
    """JSON cua trinh duyet khong chap nhan NaN/Infinity."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _mtime(path: Path) -> str | None:
    return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat() if path.exists() else None


def _has_llm_credentials(settings: Settings) -> bool:
    try:
        require_llm_credentials(settings)
        return True
    except RuntimeError:
        return False


class _TeeWriter(io.TextIOBase):
    def __init__(self, runner: "JobRunner", original):
        self.runner = runner
        self.original = original

    def write(self, text: str) -> int:
        self.runner.append_log(text)
        with contextlib.suppress(Exception):
            self.original.write(text)
        return len(text)

    def flush(self) -> None:
        with contextlib.suppress(Exception):
            self.original.flush()


class JobRunner:
    """Chay 1 pipeline tai 1 thoi diem trong background thread, gom stdout lam log."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {
            "name": None,
            "status": "idle",
            "log": "",
            "started_at": None,
            "finished_at": None,
            "error": None,
            "use_llm": False,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state, now=time.time())

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._state["status"] == "running"

    def append_log(self, text: str) -> None:
        with self._lock:
            self._state["log"] = (self._state["log"] + text)[-MAX_LOG_CHARS:]

    def start(self, name: str, fn: Callable[[], Any], use_llm: bool) -> bool:
        with self._lock:
            if self._state["status"] == "running":
                return False
            self._state = {
                "name": name,
                "status": "running",
                "log": "",
                "started_at": time.time(),
                "finished_at": None,
                "error": None,
                "use_llm": use_llm,
            }
        threading.Thread(target=self._run, args=(fn,), daemon=True).start()
        return True

    def _run(self, fn: Callable[[], Any]) -> None:
        status, error = "done", None
        try:
            with contextlib.redirect_stdout(_TeeWriter(self, sys.__stdout__)):
                fn()
        except Exception as exc:  # pragma: no cover - hien thi loi len UI
            status, error = "error", f"{type(exc).__name__}: {exc}"
            self.append_log(traceback.format_exc())
        with self._lock:
            self._state.update(status=status, error=error, finished_at=time.time())


def _settings_for_run(use_llm: bool) -> Settings:
    """Tat LLM -> provider 'mock': judge dung heuristic, bo qua agent demo, chay nhanh."""
    settings = load_settings()
    return settings if use_llm else replace(settings, llm_provider="mock")


def _run_phase1(use_llm: bool) -> None:
    from pipelines.phase1 import run_phase1_pipeline

    run_phase1_pipeline(_settings_for_run(use_llm))


def _run_corruption(use_llm: bool) -> None:
    from pipelines.corruption_flow import run_corruption_flow_pipeline

    run_corruption_flow_pipeline(_settings_for_run(use_llm))


JOBS: dict[str, Callable[[bool], None]] = {"phase1": _run_phase1, "corruption": _run_corruption}


def build_state(runner: JobRunner) -> dict[str, Any]:
    settings = load_settings()
    stages: dict[str, Any] = {}
    for stage, paths in _stage_paths(settings).items():
        clean = _read(paths["clean"])
        answers = _read(paths["answers"]) or []
        for answer in answers:
            answer.pop("retrieved_contexts", None)
        stages[stage] = {
            "metrics": _read(paths["metrics"]),
            "quality": _read(paths["quality"]),
            "freshness": _read(paths["freshness"]),
            "answers": answers,
            "rows": len(clean) if isinstance(clean, list) else None,
            "indexed": paths["embeddings"].exists(),
            "updated_at": _mtime(paths["metrics"]),
        }
    return {
        "config": {
            "provider": settings.llm_provider,
            "model": settings.model_name,
            "has_llm_credentials": _has_llm_credentials(settings),
            "embedding_model": settings.embedding_model,
            "top_k": settings.top_k,
            "freshness_threshold_days": settings.freshness_threshold_days,
            "source_api": settings.source_api,
        },
        "stages": stages,
        "test_set": _read(settings.paths.eval_testset) or [],
        "corruption_log": _read(settings.paths.corruption_log),
        "job": runner.snapshot(),
    }


def _summary_snippet(content: str, limit: int = 220) -> str:
    summary = content.split("Summary:", 1)[-1].strip()
    return summary if len(summary) <= limit else summary[:limit].rstrip() + "…"


def ask_oracle(question: str) -> dict[str, Any]:
    from retrieval.index import LocalEmbeddingIndex
    from retrieval.qa import answer_question

    settings = load_settings()
    results: dict[str, Any] = {}
    for stage, paths in _stage_paths(settings).items():
        manifest = paths["embeddings"]
        if not manifest.exists():
            results[stage] = {"available": False}
            continue
        try:
            index = LocalEmbeddingIndex.load(settings, manifest)
            result = answer_question(question, settings=settings, index=index)
            scores = {item.paper_id: item.score for item in index.search(question)}
            results[stage] = {
                "available": True,
                "answer": result.answer,
                "retrieved": [
                    {
                        "paper_id": paper_id,
                        "title": title,
                        "score": scores.get(paper_id),
                        "snippet": _summary_snippet(context),
                    }
                    for paper_id, title, context in zip(
                        result.retrieved_doc_ids, result.retrieved_titles, result.retrieved_contexts, strict=False
                    )
                ],
            }
        except Exception as exc:
            results[stage] = {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    return results


def _warm_up() -> None:
    """Nap san MiniLM de lan hoi dau tien khong bi cham."""
    with contextlib.suppress(Exception):
        from retrieval.embeddings import MiniLMEmbeddings

        MiniLMEmbeddings(load_settings().embedding_model)


class DemoHandler(BaseHTTPRequestHandler):
    runner: JobRunner
    ask_lock = threading.Lock()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - chu ky cua stdlib
        return

    def _send_bytes(self, body: bytes, content_type: str, status: int = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(_sanitize(payload), ensure_ascii=False).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8", status)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object.")
        return payload

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            self._send_bytes((STATIC_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif path.startswith("/static/"):
            self._send_static(path.removeprefix("/static/"))
        elif path == "/api/state":
            self._send_json(build_state(self.runner))
        elif path == "/api/job":
            self._send_json(self.runner.snapshot())
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def _send_static(self, name: str) -> None:
        file_path = (STATIC_DIR / name).resolve()
        content_type = STATIC_TYPES.get(file_path.suffix)
        if file_path.parent != STATIC_DIR or content_type is None or not file_path.is_file():
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_bytes(file_path.read_bytes(), content_type)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._read_body()
        except ValueError as exc:
            self._send_json({"error": f"Invalid JSON: {exc}"}, HTTPStatus.BAD_REQUEST)
            return

        if path.startswith("/api/run/"):
            name = path.removeprefix("/api/run/")
            job = JOBS.get(name)
            if job is None:
                self._send_json({"error": f"Unknown job: {name}"}, HTTPStatus.NOT_FOUND)
                return
            use_llm = bool(body.get("use_llm"))
            if not self.runner.start(name, lambda: job(use_llm), use_llm):
                self._send_json({"error": "Một pipeline khác đang chạy."}, HTTPStatus.CONFLICT)
                return
            self._send_json(self.runner.snapshot(), HTTPStatus.ACCEPTED)
        elif path == "/api/ask":
            question = str(body.get("question") or "").strip()
            if not question:
                self._send_json({"error": "Câu hỏi đang trống."}, HTTPStatus.BAD_REQUEST)
            elif self.runner.busy:
                self._send_json({"error": "Pipeline đang chạy, chờ xong rồi hỏi lại."}, HTTPStatus.CONFLICT)
            else:
                with self.ask_lock:
                    self._send_json({"question": question, "stages": ask_oracle(question)})
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)


class DemoServer(ThreadingHTTPServer):
    # Tren Windows, SO_REUSEADDR cho phep server thu 2 bind trung cong ma khong bao loi,
    # khien trinh duyet noi vao server cu. Tat di de loi "cong dang ban" hien ra ngay.
    allow_reuse_address = sys.platform != "win32"


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    DemoHandler.runner = JobRunner()
    try:
        server = DemoServer((host, port), DemoHandler)
    except OSError as exc:
        raise SystemExit(
            f"Port {port} is already in use ({exc}). Stop the other demo server or run with --port <other>."
        ) from exc
    url = f"http://{host}:{port}"
    print(f"Demo UI running at {url}  (Ctrl+C to stop)")
    threading.Thread(target=_warm_up, daemon=True).start()
    if open_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
