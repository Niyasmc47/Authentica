import asyncio
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.core.config import settings
from app.core.logging import logger
from app.schemas.analysis import AnalysisResponse, HealthResponse
from app.services.analysis_service import (
    AnalysisService,
    FileTooLargeError,
    InvalidFileExtensionError,
    InvalidMimeTypeError,
    ValidationException,
)
from app.services.video_processor import (
    CorruptedVideoError,
    VideoDurationExceededError,
    VideoProcessingError,
)
from app.utils.ffmpeg import check_ffmpeg_available

from app.db import DatabaseService, FeedbackPayload

router = APIRouter()

# In-memory client IP rate limiter (Phase 18 security)
_RATE_LIMIT_MAX_REQUESTS = 30
_RATE_LIMIT_WINDOW_SECONDS = 60.0
_client_request_history = defaultdict(list)

# Concurrency semaphore: protect CPU from starvation under burst concurrent analyses (P1.12)
_ANALYSIS_SEMAPHORE = asyncio.Semaphore(2)


def get_client_ip(request: Request) -> str:
    """
    Secure client IP resolution:
    Only trust CF-Connecting-IP / X-Forwarded-For when Cloudflare CF-Ray header is present;
    otherwise fallback to direct client socket host.
    """
    cf_ray = request.headers.get("CF-Ray") or request.headers.get("cf-ray")
    if cf_ray:
        cf_ip = request.headers.get("CF-Connecting-IP") or request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()
        xfwd = request.headers.get("X-Forwarded-For") or request.headers.get("x-forwarded-for")
        if xfwd:
            return xfwd.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def check_rate_limit(request: Request) -> None:
    """Enforces client IP rate limits in-memory without external cache dependencies."""
    client_ip = get_client_ip(request)
    now = time.time()
    # Retain only timestamps within the rolling window
    timestamps = [ts for ts in _client_request_history[client_ip] if now - ts < _RATE_LIMIT_WINDOW_SECONDS]
    if len(timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
        _client_request_history[client_ip] = timestamps
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 30 analysis requests per minute allowed.",
        )
    timestamps.append(now)
    _client_request_history[client_ip] = timestamps


def get_analysis_service() -> AnalysisService:
    """Dependency injection provider for AnalysisService."""
    return AnalysisService()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description="Returns server status, MongoDB connectivity, and verification of FFmpeg/FFprobe availability."
)
async def health_check():
    ffmpeg_ok, ffprobe_ok, _ = check_ffmpeg_available()
    return HealthResponse(
        status="ok",
        ffmpeg_available=ffmpeg_ok,
        ffprobe_available=ffprobe_ok,
        version=settings.VERSION
    )


@router.get(
    "/analyses",
    summary="List analysis history",
    description="Retrieves historical forensic reports with optional text search and pagination."
)
async def list_analyses(
    limit: int = 50,
    skip: int = 0,
    search: Optional[str] = None
):
    items = await DatabaseService.list_analyses(limit=limit, skip=skip, search=search)
    return {"count": len(items), "items": items, "mongodb_connected": DatabaseService.is_connected()}


@router.get(
    "/analyses/{analysis_id}",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Get analysis report by ID",
    description="Retrieves a completed forensic analysis report by its unique UUID."
)
async def get_analysis_by_id(analysis_id: str):
    analysis = await DatabaseService.get_analysis(analysis_id)
    if analysis:
        return analysis
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Analysis with ID '{analysis_id}' was not found or has expired."
    )


@router.post(
    "/analyses/{analysis_id}/feedback",
    summary="Record human verification feedback for active learning",
    description="Stores verified ground-truth labels (Real vs Fake / Harmless vs Scam) to train future model checkpoints."
)
async def record_feedback(
    analysis_id: str,
    feedback: FeedbackPayload
):
    try:
        sample = await DatabaseService.record_feedback(analysis_id, feedback)
        return {
            "ok": True,
            "message": "Ground-truth feedback recorded successfully. Sample staged for active learning.",
            "sample": sample
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Feedback recording error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record feedback."
        )


def verify_admin_access(request: Request) -> None:
    """Optional admin security: requires X-Admin-Key if ADMIN_API_KEY is configured."""
    admin_key = getattr(settings, "ADMIN_API_KEY", None) or os.getenv("ADMIN_API_KEY")
    if admin_key:
        provided = request.headers.get("X-Admin-Key") or request.headers.get("Authorization")
        if not provided or (provided != admin_key and f"Bearer {admin_key}" != provided):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: invalid or missing admin API key.",
            )


@router.get(
    "/train/dataset",
    dependencies=[Depends(verify_admin_access)],
    summary="Get verified active learning dataset",
    description="Lists all human-confirmed ground-truth training samples stored in MongoDB / local feedback archive."
)
async def get_training_dataset(limit: int = 200):
    samples = await DatabaseService.get_verified_training_dataset(limit=limit)
    return {
        "count": len(samples),
        "samples": samples,
        "mongodb_connected": DatabaseService.is_connected()
    }


@router.post(
    "/analyses",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and analyze video/audio",
    description="Uploads a media file, validates it, extracts frames/audio, calculates SHA-256, and returns Stage 1, 2, 3 results."
)
async def analyze_video(
    request: Request,
    file: UploadFile = File(..., description="Video or audio file to inspect and analyze"),
    service: AnalysisService = Depends(get_analysis_service)
):
    check_rate_limit(request)
    try:
        async with _ANALYSIS_SEMAPHORE:
            result = await service.analyze_video(file)
        await DatabaseService.save_analysis(result)
        return result
    except (InvalidFileExtensionError, InvalidMimeTypeError) as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileTooLargeError as e:
        logger.warning(f"Payload too large: {e}")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e)
        )
    except VideoDurationExceededError as e:
        logger.warning(f"Duration exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (CorruptedVideoError, ValidationException) as e:
        logger.warning(f"Invalid media input: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except VideoProcessingError as e:
        logger.error(f"Video processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process video: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Unexpected server error during analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your request."
        )
