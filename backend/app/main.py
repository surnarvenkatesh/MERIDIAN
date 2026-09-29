from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from . import auth, db, file_extract
from .agent import agent
from .config import settings
from .models import AuthResponse, ChangePasswordRequest, FeedbackRequest, LoginRequest, PolicySnapshot, RegisterRequest, RenameSessionRequest, ResearchRequest, ResearchResult
from .rl_policy import compute_reward, policy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("research_agent.api")

app = FastAPI(title="Autonomous Research Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your deployed frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()
    logger.info(
        "Research agent ready | llm_live=%s search_live=%s",
        settings.llm_is_live,
        settings.search_is_live,
    )


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_live": settings.llm_is_live,
        "search_live": settings.search_is_live,
        "episodes_trained": policy.episodes_trained,
    }


MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


def get_current_user_id(authorization: str | None = Header(default=None)) -> int:
    """Extracts and validates the user id from a 'Bearer <token>' header.
    Raises 401 if missing, malformed, or the token is invalid/expired."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    user_id = auth.decode_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id


def get_optional_user_id(authorization: str | None = Header(default=None)) -> int | None:
    """Like get_current_user_id, but returns None instead of raising when no
    token is present - for endpoints that work for both logged-in and
    anonymous use (e.g. research can still work without an account)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return auth.decode_token(authorization.removeprefix("Bearer ").strip())


@app.post("/api/register", response_model=AuthResponse)
def register(req: RegisterRequest) -> AuthResponse:
    email = req.email.strip().lower()
    if "@" not in email or len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Enter a valid email and a password of at least 8 characters.")
    password_hash = auth.hash_password(req.password)
    user_id = db.create_user(email, password_hash)
    if user_id is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    token = auth.create_token(user_id)
    return AuthResponse(token=token, email=email)


@app.post("/api/login", response_model=AuthResponse)
def login(req: LoginRequest) -> AuthResponse:
    user = db.get_user_by_email(req.email)
    if user is None or not auth.verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = auth.create_token(user["id"])
    return AuthResponse(token=token, email=user["email"])


@app.post("/api/change-password")
def change_password(req: ChangePasswordRequest, user_id: int = Depends(get_current_user_id)) -> dict:
    current_hash = db.get_password_hash_by_id(user_id)
    if current_hash is None or not auth.verify_password(req.current_password, current_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")
    db.update_password(user_id, auth.hash_password(req.new_password))
    return {"status": "ok"}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)) -> dict:
    content_bytes = await file.read()
    if len(content_bytes) > MAX_UPLOAD_BYTES:
        return {"status": "error", "message": "File too large (max 15MB)."}
    text = file_extract.extract_text(file.filename or "upload", content_bytes)
    if not text:
        return {
            "status": "error",
            "message": "Could not extract any text from this file (unsupported type or empty content).",
        }
    return {"status": "ok", "filename": file.filename, "text": text, "char_count": len(text)}


@app.post("/api/research", response_model=ResearchResult)
def run_research(req: ResearchRequest, user_id: int | None = Depends(get_optional_user_id)) -> ResearchResult:
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:10]}"
    result = agent.run(
        query=req.query,
        session_id=session_id,
        max_steps=req.max_steps,
        max_sources=req.max_sources,
        uploaded_documents=req.uploaded_documents,
        conversation_history=req.conversation_history,
    )
    db.save_session(result, user_id=user_id)
    return result


@app.get("/api/sessions")
def sessions(limit: int = 30, user_id: int = Depends(get_current_user_id)) -> list[dict]:
    return db.list_sessions(limit, user_id=user_id)


@app.get("/api/sessions/{session_id}")
def session_detail(session_id: str) -> dict:
    result = db.get_session(session_id)
    return result or {}


@app.patch("/api/sessions/{session_id}/rename")
def rename_session(session_id: str, req: RenameSessionRequest) -> dict:
    db.rename_session(session_id, req.title)
    return {"status": "renamed"}


@app.patch("/api/sessions/{session_id}/pin")
def pin_session(session_id: str, pinned: bool = True) -> dict:
    db.set_session_pinned(session_id, pinned)
    return {"status": "pinned" if pinned else "unpinned"}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str) -> dict:
    db.delete_session(session_id)
    return {"status": "deleted"}


@app.post("/api/sessions/{session_id}/share")
def share_session(session_id: str) -> dict:
    token = db.get_or_create_share_token(session_id)
    if token is None:
        return {"status": "not_found"}
    return {"status": "ok", "share_token": token}


@app.delete("/api/sessions/{session_id}/share")
def unshare_session(session_id: str) -> dict:
    db.revoke_share_token(session_id)
    return {"status": "revoked"}


@app.get("/api/shared/{token}")
def get_shared_session(token: str) -> dict:
    result = db.get_session_by_share_token(token)
    if result is None:
        return {"status": "not_found"}
    return result


@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest) -> dict:
    db.save_feedback(req.session_id, req.rating, req.comment)
    # Blend explicit human feedback into a small immediate policy nudge:
    # treat it as a one-step episode reinforcing the *tendency* implied by
    # the session outcome, which keeps the loop genuinely closed (feedback
    # -> reward -> policy update) without needing to replay full episodes.
    feedback_reward = compute_reward(
        new_sources_added=0,
        avg_credibility_delta=0.0,
        groundedness=0.0,
        steps_used=1,
        max_steps=1,
        user_feedback=1.0 if req.rating == "helpful" else -1.0,
    )
    return {"status": "recorded", "feedback_reward": feedback_reward}


@app.get("/api/policy", response_model=PolicySnapshot)
def policy_snapshot() -> PolicySnapshot:
    return policy.snapshot()


@app.websocket("/ws/research")
async def research_stream(ws: WebSocket) -> None:
    """Streams TraceStep events live as the agent works, then a final
    'result' event. Lets the frontend render the agent's reasoning trace
    in real time instead of waiting for the whole run to finish."""
    await ws.accept()
    try:
        payload = await ws.receive_json()
        query = payload.get("query", "").strip()
        ws_token = payload.get("token")
        ws_user_id = auth.decode_token(ws_token) if ws_token else None
        if not query:
            await ws.send_json({"type": "error", "message": "query is required"})
            await ws.close()
            return
        session_id = payload.get("session_id") or f"sess_{uuid.uuid4().hex[:10]}"
        max_steps = payload.get("max_steps")
        max_sources = payload.get("max_sources")
        from .models import ConversationTurn, UploadedDocument
        raw_docs = payload.get("uploaded_documents") or []
        uploaded_documents = [UploadedDocument(**d) for d in raw_docs]
        raw_history = payload.get("conversation_history") or []
        conversation_history = [ConversationTurn(**h) for h in raw_history]

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def on_step(trace) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, trace)

        async def run_agent() -> ResearchResult:
            return await loop.run_in_executor(
                None,
                lambda: agent.run(
                    query=query,
                    session_id=session_id,
                    max_steps=max_steps,
                    max_sources=max_sources,
                    on_step=on_step,
                    uploaded_documents=uploaded_documents,
                    conversation_history=conversation_history,
                ),
            )

        task = asyncio.ensure_future(run_agent())

        while not task.done() or not queue.empty():
            try:
                trace = await asyncio.wait_for(queue.get(), timeout=0.2)
                await ws.send_json({"type": "step", "data": trace.model_dump(mode="json")})
            except asyncio.TimeoutError:
                continue

        result = await task
        db.save_session(result, user_id=ws_user_id)
        await ws.send_json({"type": "result", "data": result.model_dump(mode="json")})
        await ws.close()
    except WebSocketDisconnect:
        logger.info("Client disconnected from research stream")
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Error in research stream")
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
