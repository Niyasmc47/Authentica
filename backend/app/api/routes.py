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

router = APIRouter()


def get_analysis_service() -> AnalysisService:
    """Dependency injection provider for AnalysisService."""
    return AnalysisService()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description="Returns server status and verification of FFmpeg/FFprobe availability."
)
async def health_check():
    ffmpeg_ok, ffprobe_ok, _ = check_ffmpeg_available()
    return HealthResponse(
        status="ok",
        ffmpeg_available=ffmpeg_ok,
        ffprobe_available=ffprobe_ok,
        version=settings.VERSION
    )


@router.post(
    "/analyses",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and analyze video",
    description="Uploads a video, validates it, extracts frames/audio, calculates SHA-256, and returns Stage 1 results."
)
async def analyze_video(
    file: UploadFile = File(..., description="Video file to inspect and analyze"),
    service: AnalysisService = Depends(get_analysis_service)
):
    try:
        return await service.analyze_video(file)
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
