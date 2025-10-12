#!/usr/bin/env python
"""
Example: Post to X (Twitter) with optional media using x_client.

This example demonstrates:
- Loading credentials from environment or .env file
- Creating a client using the factory
- Uploading media (image or video)
- Creating a post with or without media

Usage:
    # Text-only post
    python examples/create_post.py "Hello from x_client!"

    # Post with image
    python examples/create_post.py "Check out this image!" --image path/to/image.png

    # Post with video
    python examples/create_post.py "Check out this video!" --video path/to/video.mp4

Requirements:
    Set environment variables or create a .env file with:
    - X_API_KEY
    - X_API_SECRET
    - X_ACCESS_TOKEN
    - X_ACCESS_TOKEN_SECRET
    - X_BEARER_TOKEN (optional, but recommended for v2 API)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script (e.g. python examples/create_post.py)
if __package__ is None:  # pragma: no cover - runtime convenience
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from x_client.config import ConfigManager
from x_client.exceptions import (
    ConfigurationError,
    MediaProcessingFailed,
    MediaValidationError,
    XClientError,
)
from x_client.factory import XClientFactory
from x_client.services.media_service import MediaService
from x_client.services.post_service import PostService


def main() -> int:
    """Main entry point for the example."""
    parser = argparse.ArgumentParser(
        description="Post to X with optional media attachment"
    )
    parser.add_argument("text", help="Post text content")
    parser.add_argument(
        "--image",
        type=Path,
        help="Path to image file (png, jpg, gif, webp, max 5MB)",
    )
    parser.add_argument(
        "--video",
        type=Path,
        help="Path to video file (mp4, max 512MB with chunked upload)",
    )
    parser.add_argument(
        "--dotenv",
        type=Path,
        help="Path to .env file (default: ./.env)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.image and args.video:
        print("Error: Cannot attach both image and video to a single post")
        return 1

    try:
        # Step 1: Load credentials
        print("Loading credentials...")
        config = ConfigManager(dotenv_path=args.dotenv) if args.dotenv else ConfigManager()
        credentials = config.load_credentials()
        print("✅ Credentials loaded")

        # Step 2: Create client using factory
        print("Initializing X client...")
        client = XClientFactory.create_from_credentials(credentials)
        print("✅ Client initialized (dual-client: v2 + v1.1)")

        # Step 3: Initialize services
        post_service = PostService(client)
        media_service = MediaService(client)

        # Step 4: Upload media if provided
        media_id = None
        if args.image:
            print(f"Uploading image: {args.image}")
            result = media_service.upload_image(args.image)
            media_id = result.media_id
            print(f"✅ Image uploaded: {media_id}")

        elif args.video:
            print(f"Uploading video: {args.video}")
            print("(This may take a while for large videos...)")
            result = media_service.upload_video(args.video)
            media_id = result.media_id
            print(f"✅ Video uploaded: {media_id}")
            if result.processing_info:
                print(
                    f"   Processing status: {result.processing_info.state}"
                )

        # Step 5: Create post
        print(f"Creating post: '{args.text}'")
        if media_id:
            post = post_service.create_post(
                text=args.text, media_ids=[media_id]
            )
            print(f"✅ Post created with media: {post.id}")
        else:
            post = post_service.create_post(text=args.text)
            print(f"✅ Post created: {post.id}")

        print(f"\n🎉 Success! Post URL: https://x.com/i/web/status/{post.id}")
        return 0

    except ConfigurationError as e:
        print(f"❌ Configuration error: {e}")
        print("\nPlease set environment variables or create a .env file:")
        print("  - X_API_KEY")
        print("  - X_API_SECRET")
        print("  - X_ACCESS_TOKEN")
        print("  - X_ACCESS_TOKEN_SECRET")
        print("  - X_BEARER_TOKEN (optional)")
        return 1

    except MediaValidationError as e:
        print(f"❌ Media validation error: {e}")
        print("\nSupported formats:")
        print("  - Images: PNG, JPEG, GIF, WebP (max 5MB)")
        print("  - Videos: MP4 (max 512MB)")
        return 1

    except MediaProcessingFailed as e:
        print(f"❌ Media processing failed: {e}")
        print("\nX's media processing encountered an error.")
        print("Please check the file format and encoding.")
        return 1

    except XClientError as e:
        print(f"❌ X API error: {e}")
        return 1

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
