"""Mock responses for Twitter API integration tests."""

from __future__ import annotations

# Twitter API v2 responses
TWEET_RESPONSE = {
    "data": {
        "id": "1234567890",
        "text": "Hello from integration test!",
        "edit_history_tweet_ids": ["1234567890"],
    }
}

DELETE_TWEET_RESPONSE = {
    "data": {
        "deleted": True,
    }
}

GET_TWEET_RESPONSE = {
    "data": {
        "id": "1234567890",
        "text": "Test tweet",
        "author_id": "123456",
        "created_at": "2024-01-01T00:00:00.000Z",
    }
}

SEARCH_TWEETS_RESPONSE = {
    "data": [
        {
            "id": "1111111111",
            "text": "First result",
            "author_id": "123456",
        },
        {
            "id": "2222222222",
            "text": "Second result",
            "author_id": "789012",
        },
    ],
    "meta": {
        "result_count": 2,
    },
}

# Twitter API v1.1 media upload responses
MEDIA_UPLOAD_IMAGE_RESPONSE = {
    "media_id": 1234567890123456789,
    "media_id_string": "1234567890123456789",
    "media_key": "3_1234567890123456789",
    "size": 12345,
    "expires_after_secs": 86400,
    "image": {
        "image_type": "image/png",
        "w": 1200,
        "h": 675,
    },
}

MEDIA_UPLOAD_VIDEO_INIT_RESPONSE = {
    "media_id": 9876543210987654321,
    "media_id_string": "9876543210987654321",
    "media_key": "7_9876543210987654321",
    "expires_after_secs": 86400,
}

MEDIA_UPLOAD_VIDEO_FINALIZE_RESPONSE = {
    "media_id": 9876543210987654321,
    "media_id_string": "9876543210987654321",
    "media_key": "7_9876543210987654321",
    "size": 5242880,
    "expires_after_secs": 86400,
    "processing_info": {
        "state": "pending",
        "check_after_secs": 1,
    },
}

MEDIA_UPLOAD_VIDEO_STATUS_PROCESSING = {
    "media_id": 9876543210987654321,
    "media_id_string": "9876543210987654321",
    "processing_info": {
        "state": "in_progress",
        "check_after_secs": 1,
        "progress_percent": 50,
    },
}

MEDIA_UPLOAD_VIDEO_STATUS_SUCCEEDED = {
    "media_id": 9876543210987654321,
    "media_id_string": "9876543210987654321",
    "processing_info": {
        "state": "succeeded",
        "progress_percent": 100,
    },
    "video": {
        "video_type": "video/mp4",
    },
}

MEDIA_UPLOAD_VIDEO_STATUS_FAILED = {
    "media_id": 9876543210987654321,
    "media_id_string": "9876543210987654321",
    "processing_info": {
        "state": "failed",
        "error": {
            "code": 1,
            "name": "InvalidMedia",
            "message": "Invalid video format",
        },
    },
}

# Rate limit error response
RATE_LIMIT_ERROR_RESPONSE = {
    "errors": [
        {
            "message": "Rate limit exceeded",
            "code": 88,
        }
    ]
}
