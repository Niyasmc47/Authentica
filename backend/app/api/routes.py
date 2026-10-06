from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

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


@router.get(
    "/train/dataset",
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
    file: UploadFile = File(..., description="Video or audio file to inspect and analyze"),
    service: AnalysisService = Depends(get_analysis_service)
):
    try:
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
