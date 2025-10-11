#!/usr/bin/env python
"""
Example: Post a tweet with optional media using twitter_client.

This example demonstrates:
- Loading credentials from environment or file
- Creating a client using the factory
- Uploading media (image or video)
- Creating a tweet with or without media

Usage:
    # Text-only tweet
    python examples/post_tweet.py "Hello from twitter_client!"

    # Tweet with image
    python examples/post_tweet.py "Check out this image!" --image path/to/image.png

    # Tweet with video
    python examples/post_tweet.py "Check out this video!" --video path/to/video.mp4

Requirements:
    Set environment variables or create credentials/twitter_config.json:
    - TWITTER_API_KEY
    - TWITTER_API_SECRET
    - TWITTER_ACCESS_TOKEN
    - TWITTER_ACCESS_TOKEN_SECRET
    - TWITTER_BEARER_TOKEN (optional, but recommended for v2 API)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from twitter_client.config import ConfigManager
from twitter_client.exceptions import (
    ConfigurationError,
    MediaProcessingFailed,
    MediaValidationError,
    TwitterClientError,
)
from twitter_client.factory import TwitterClientFactory
from twitter_client.services.media_service import MediaService
from twitter_client.services.tweet_service import TweetService


def main() -> int:
    """Main entry point for the example."""
    parser = argparse.ArgumentParser(
        description="Post a tweet with optional media attachment"
    )
    parser.add_argument("text", help="Tweet text content")
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
        "--config",
        type=Path,
        help="Path to credentials JSON file (default: credentials/twitter_config.json)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.image and args.video:
        print("Error: Cannot attach both image and video to a single tweet")
        return 1

    try:
        # Step 1: Load credentials
        print("Loading credentials...")
        config_path = args.config if args.config else None
        config = ConfigManager(credential_path=config_path)
        credentials = config.load_credentials()
        print("✅ Credentials loaded")

        # Step 2: Create client using factory
        print("Initializing Twitter client...")
        client = TwitterClientFactory.create_from_credentials(credentials)
        print("✅ Client initialized (dual-client: v2 + v1.1)")

        # Step 3: Initialize services
        tweet_service = TweetService(client)
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

        # Step 5: Create tweet
        print(f"Creating tweet: '{args.text}'")
        if media_id:
            tweet = tweet_service.create_tweet(
                text=args.text, media_ids=[media_id]
            )
            print(f"✅ Tweet created with media: {tweet.id}")
        else:
            tweet = tweet_service.create_tweet(text=args.text)
            print(f"✅ Tweet created: {tweet.id}")

        print(f"\n🎉 Success! Tweet URL: https://twitter.com/i/web/status/{tweet.id}")
        return 0

    except ConfigurationError as e:
        print(f"❌ Configuration error: {e}")
        print("\nPlease set environment variables or create credentials file:")
        print("  - TWITTER_API_KEY")
        print("  - TWITTER_API_SECRET")
        print("  - TWITTER_ACCESS_TOKEN")
        print("  - TWITTER_ACCESS_TOKEN_SECRET")
        print("  - TWITTER_BEARER_TOKEN (optional)")
        return 1

    except MediaValidationError as e:
        print(f"❌ Media validation error: {e}")
        print("\nSupported formats:")
        print("  - Images: PNG, JPEG, GIF, WebP (max 5MB)")
        print("  - Videos: MP4 (max 512MB)")
        return 1

    except MediaProcessingFailed as e:
        print(f"❌ Media processing failed: {e}")
        print("\nTwitter's media processing encountered an error.")
        print("Please check the file format and encoding.")
        return 1

    except TwitterClientError as e:
        print(f"❌ Twitter API error: {e}")
        return 1

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
