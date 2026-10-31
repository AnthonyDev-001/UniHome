import hashlib
import io
import json
import os
import subprocess
import tempfile
import warnings

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError


class UploadInvalid(ValidationError):
    pass


def digest(file):
    file.seek(0)
    value = hashlib.sha256(file.read()).hexdigest()
    file.seek(0)
    return value


def normalize_image(file):
    if file.size > 5 * 1024 * 1024:
        raise UploadInvalid('Images must be at most 5 MiB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(file)
            if image.format not in {'JPEG', 'PNG', 'WEBP'} or getattr(image, 'n_frames', 1) != 1:
                raise UploadInvalid('Use a single-frame JPEG, PNG or WebP image.')
            if image.width * image.height > 20_000_000:
                raise UploadInvalid('Images must not exceed 20 megapixels.')
            image.load()
            image = ImageOps.exif_transpose(image).convert('RGB')
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=85)
            return ContentFile(output.getvalue(), name='image.jpg'), 'image/jpeg', 0
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise UploadInvalid('Invalid or unsafe image.')


def normalize_evidence(file):
    if not 0 < file.size <= 10 * 1024 * 1024:
        raise UploadInvalid('Evidence must be between 1 byte and 10 MiB.')
    header = file.read(8)
    file.seek(0)
    if header.startswith(b'%PDF-'):
        # Signature sniffing is not malware clearance. Always serve as attachment.
        return ContentFile(file.read(), name='evidence.pdf'), 'application/pdf', 0
    return normalize_image(file)


def validate_video(file):
    if not 0 < file.size <= 50 * 1024 * 1024:
        raise UploadInvalid('Videos must be between 1 byte and 50 MiB.')
    with tempfile.NamedTemporaryFile(suffix='.mp4') as temp:
        for chunk in file.chunks():
            temp.write(chunk)
        temp.flush()
        try:
            result = subprocess.run([
                settings.FFPROBE_BINARY, '-v', 'error', '-protocol_whitelist', 'file,pipe',
                '-f', 'mov', '-enable_drefs', '0', '-i', temp.name, '-show_entries',
                'format=duration:stream=codec_type,codec_name,width,height', '-of', 'json',
            ], capture_output=True, timeout=15, check=True)
            info = json.loads(result.stdout)
            duration = float(info['format']['duration'])
            streams = info['streams']
            video = [s for s in streams if s['codec_type'] == 'video']
            if (not 0 < duration <= 180 or len(video) != 1 or video[0]['codec_name'] != 'h264'
                    or not 0 < video[0]['width'] <= 3840 or not 0 < video[0]['height'] <= 2160
                    or any(s['codec_type'] not in {'audio', 'video'} for s in streams)
                    or any(s['codec_name'] != 'aac' for s in streams if s['codec_type'] == 'audio')):
                raise UploadInvalid('Use an H.264 MP4 up to 180 seconds and 3840×2160, with optional AAC audio.')
        except FileNotFoundError:
            raise UploadInvalid('Video inspection is unavailable; contact support.')
        except (subprocess.SubprocessError, ValueError, KeyError, TypeError):
            raise UploadInvalid('Video could not be validated as MP4.')
        # Remux only approved audio/video streams; drop standard container/stream
        # metadata and chapters. This is not a malware scan or frame redaction.
        with tempfile.NamedTemporaryFile(suffix='.mp4') as output:
            try:
                subprocess.run([
                    settings.FFMPEG_BINARY, '-nostdin', '-v', 'error', '-y',
                    '-protocol_whitelist', 'file,pipe', '-f', 'mov', '-enable_drefs', '0', '-i', temp.name,
                    '-map', '0:v:0', '-map', '0:a?', '-c', 'copy', '-map_metadata', '-1',
                    '-map_metadata:s', '-1', '-map_chapters', '-1', '-fflags', '+bitexact',
                    '-movflags', '+faststart', output.name,
                ], capture_output=True, timeout=30, check=True)
                if os.path.getsize(output.name) > 50 * 1024 * 1024:
                    raise UploadInvalid('Normalized video exceeds 50 MiB.')
                output.seek(0)
                normalized = ContentFile(output.read(), name='tour.mp4')
            except FileNotFoundError:
                raise UploadInvalid('Video normalization is unavailable; contact support.')
            except subprocess.SubprocessError:
                raise UploadInvalid('Video could not be normalized safely.')
    return normalized, 'video/mp4', duration
