import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import httpx

from app.services.voice_service import VoiceService
from app.config import settings


@pytest.fixture
def voice_service():
    return VoiceService()


@pytest.mark.asyncio
async def test_transcribe_audio_success(voice_service):
    """Test successful transcription using the Hugging Face Inference API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "Bonjour tout le monde"}

    # Mock open and st_size of file
    with patch("builtins.open", mock_open(read_data=b"audio data")), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat") as mock_stat, \
         patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        
        mock_stat.return_value.st_size = 1000
        
        result = await voice_service.transcribe_audio("dummy.webm")
        assert result == "Bonjour tout le monde"
        mock_post.assert_called_once()
        # Verify HF URL
        assert "openai/whisper-large-v3" in mock_post.call_args[0][0]


@pytest.mark.asyncio
async def test_transcribe_audio_retry_on_503(voice_service):
    """Test transcription retries when HF returns 503 (model loading)."""
    mock_response_503 = MagicMock()
    mock_response_503.status_code = 503
    mock_response_503.json.return_value = {"error": "Model loading", "estimated_time": 0.01}

    mock_response_200 = MagicMock()
    mock_response_200.status_code = 200
    mock_response_200.json.return_value = {"text": "Re-bonjour"}

    with patch("builtins.open", mock_open(read_data=b"audio data")), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat") as mock_stat, \
         patch("httpx.AsyncClient.post") as mock_post, \
         patch("asyncio.sleep") as mock_sleep:
        
        mock_stat.return_value.st_size = 1000
        # First return 503, then return 200
        mock_post.side_effect = [mock_response_503, mock_response_200]
        
        result = await voice_service.transcribe_audio("dummy.webm")
        assert result == "Re-bonjour"
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_transcribe_audio_all_retries_fail(voice_service):
    """Test transcription raises error when all retries are exhausted."""
    mock_response_500 = MagicMock()
    mock_response_500.status_code = 500
    mock_response_500.text = "Internal Server Error"
    # Make raise_for_status raise the HTTPStatusError
    mock_response_500.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=MagicMock(),
        response=mock_response_500
    )

    with patch("builtins.open", mock_open(read_data=b"audio data")), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat") as mock_stat, \
         patch("httpx.AsyncClient.post", return_value=mock_response_500) as mock_post, \
         patch("asyncio.sleep") as mock_sleep:
        
        mock_stat.return_value.st_size = 1000
        
        with pytest.raises(httpx.HTTPStatusError):
            await voice_service.transcribe_audio("dummy.webm")
            
        assert mock_post.call_count == settings.HF_VOICE_RETRIES


@pytest.mark.asyncio
async def test_test_transcription_model_status_success(voice_service):
    """Test connectivity check for transcription model."""
    mock_hub_response = MagicMock()
    mock_hub_response.status_code = 200
    mock_hub_response.json.return_value = {"id": "openai/whisper-large-v3", "downloads": 500}

    mock_inf_response = MagicMock()
    mock_inf_response.status_code = 400  # 400 is expected for empty body POST

    with patch("httpx.AsyncClient.get", return_value=mock_hub_response), \
         patch("httpx.AsyncClient.post", return_value=mock_inf_response):
        
        status_info = await voice_service.test_transcription_model_status()
        assert status_info["status"] == "ok"
        assert status_info["inference_status"] == "ready"
        assert status_info["model_id"] == "openai/whisper-large-v3"



