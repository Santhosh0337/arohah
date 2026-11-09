import pytest
from pydantic import ValidationError

from app.models import Note, ProjectInput, PipelineWarning


def test_valid_note():
    note = Note(
        pitch=60,
        start=0.5,
        end=1.0,
        velocity=80,
        confidence=0.9,
    )
    assert note.pitch == 60


def test_note_rejects_invalid_pitch():
    with pytest.raises(ValidationError):
        Note(pitch=128, start=0.0, end=1.0, velocity=80)


def test_note_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        Note(pitch=60, start=0.0, end=1.0, velocity=80, confidence=1.5)


def test_project_input_accepts_hum_without_language():
    item = ProjectInput(
        mode="hum",
        language=None,
        audio_file_id="650000000000000000000003",
        duration_s=8.0,
    )
    assert item.language is None


def test_project_input_rejects_audio_over_60_seconds():
    with pytest.raises(ValidationError):
        ProjectInput(
            mode="hum",
            language=None,
            audio_file_id="650000000000000000000003",
            duration_s=61.0,
        )


def test_pipeline_warning():
    warning = PipelineWarning(
        code="low_pitch_confidence",
        message="Pitch confidence is low.",
        stage="pitch",
    )
    assert warning.stage == "pitch"
