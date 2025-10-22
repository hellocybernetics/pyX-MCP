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

    # Post a long thread (auto split every 180 characters)
    python examples/create_post.py "Long thread text..." --thread --chunk-limit 180

    # Post a thread sourced from file contents
    python examples/create_post.py --thread-file notes/thread.txt

    # Japanese long thread example (proactively shortened to keep sentences intact)
    python examples/create_post.py --thread-file examples/long_thread_ja.txt --chunk-limit 180

    # English long thread example (leave headroom for URLs and emojis)
    python examples/create_post.py --thread-file examples/long_thread_en.txt --chunk-limit 240

    # Reduce posting cadence to avoid 429 (segment pause of 8 seconds)
    python examples/create_post.py --thread-file examples/long_thread_en.txt --segment-pause 8

    # Repost / undo repost by post ID
    python examples/create_post.py --repost 1234567890
    python examples/create_post.py --undo-repost 1234567890

    # Delete a post by ID (useful when cleaning up failed thread attempts)
    python examples/create_post.py --delete 1234567890

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
    RateLimitExceeded,
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
    parser.add_argument(
        "text",
        nargs="?",
        help="Post text content (required for post/thread actions)",
    )
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
    parser.add_argument(
        "--thread",
        action="store_true",
        help="Split provided text into a thread (requires text)",
    )
    parser.add_argument(
        "--thread-file",
        type=Path,
        help="Path to a text/markdown file to post as thread",
    )
    parser.add_argument(
        "--chunk-limit",
        type=int,
        default=280,
        help="Maximum characters per thread segment (default: 280)",
    )
    parser.add_argument(
        "--segment-pause",
        type=float,
        default=5.0,
        help="Seconds to wait between thread segments (default: 5.0)",
    )
    parser.add_argument(
        "--split-strategy",
        choices=["simple", "sentence", "paragraph"],
        default=None,
        help=(
            "Thread split strategy: 'simple' (whitespace, default), "
            "'sentence' (句読点で文単位), 'paragraph' (空行で段落優先)."
        ),
    )
    parser.add_argument(
        "--repost",
        metavar="POST_ID",
        help="Repost the given post ID",
    )
    parser.add_argument(
        "--undo-repost",
        metavar="POST_ID",
        help="Undo a repost for the given post ID",
    )
    parser.add_argument(
        "--delete",
        metavar="POST_ID",
        help="Delete the given post ID (utility for cleaning failed threads)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.image and args.video:
        print("Error: Cannot attach both image and video to a single post")
        return 1

    if args.repost and args.undo_repost:
        print("Error: --repost and --undo-repost cannot be used together")
        return 1

    thread_mode = bool(args.thread or args.thread_file)
    repost_mode = bool(args.repost or args.undo_repost)
    delete_mode = bool(args.delete)

    if sum(int(flag) for flag in (thread_mode, repost_mode, delete_mode)) > 1:
        print("Error: Choose only one action (thread, repost/undo, or delete)")
        return 1

    if args.thread_file and not args.thread_file.exists():
        print(f"Error: Thread file not found: {args.thread_file}")
        return 1

    if args.chunk_limit <= 0:
        print("Error: --chunk-limit must be a positive integer")
        return 1

    # Japanese text often uses full-width punctuation, so keeping chunk_limit below 200 avoids
    # breaking sentences mid-clause. English threads with URLs or emojis should also leave room
    # because Twitter treats each URL as 23 characters regardless of length.
    if thread_mode and (args.image or args.video):
        print("Error: Thread posting currently supports text-only content")
        return 1

    if repost_mode and (args.image or args.video):
        print("Error: Media attachments are not compatible with repost actions")
        return 1

    if not (thread_mode or repost_mode or delete_mode) and not args.text:
        print("Error: Provide text for single post actions")
        return 1

    if thread_mode and not (args.text or args.thread_file):
        print("Error: Provide text or --thread-file for post/thread actions")
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

        if delete_mode:
            target_id = args.delete
            print(f"Deleting post ID: {target_id}")
            try:
                post_service.delete_post(target_id)
            except XClientError as exc:
                print(f"❌ Failed to delete post: {exc}")
                return 1
            print("✅ Post deleted")
            return 0

        # Step 4: Upload media if provided
        if repost_mode:
            if args.repost:
                target_id = args.repost
                print(f"Reposting post ID: {target_id}")
                result = post_service.repost_post(target_id)
                print(
                    "✅ Repost successful"
                    f" (target={target_id}, reposted={result.reposted})"
                )
            else:
                target_id = args.undo_repost
                print(f"Undoing repost for post ID: {target_id}")
                result = post_service.undo_repost(target_id)
                print(
                    "✅ Repost undone"
                    f" (target={target_id}, reposted={result.reposted})"
                )
            return 0

        # Step 4: Upload media if provided (post mode only)
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

        # Step 5: Create post or thread
        if thread_mode:
            thread_source = (
                args.thread_file.read_text(encoding="utf-8")
                if args.thread_file
                else args.text
            )
            assert thread_source is not None  # for mypy/static analyzers
            print(
                f"Creating thread from {'file' if args.thread_file else 'text'}"
                f" (chunk_limit={args.chunk_limit})"
            )
            result = post_service.create_thread(
                thread_source,
                chunk_limit=args.chunk_limit,
                rollback_on_failure=True,
                segment_pause=max(args.segment_pause, 0.0),
                split_strategy=args.split_strategy,
            )

            if result.succeeded:
                print("✅ Thread posted successfully")
                for idx, post in enumerate(result.posts, start=1):
                    print(
                        f"   Segment {idx}: {post.id}"
                        f" → https://x.com/i/web/status/{post.id}"
                    )
                return 0

            print(
                f"❌ Thread failed at segment {result.failed_index + 1 if result.failed_index is not None else '?'}:"
                f" {result.error}"
            )
            if result.rolled_back:
                print("   Rolled back previously created posts.")
            elif result.posts:
                print("   The following posts remain published:")
                for post in result.posts:
                    print(f"     - https://x.com/i/web/status/{post.id}")
            if isinstance(result.error, RateLimitExceeded):
                print(
                    "   Tip: X returned 429 (rate limit). Wait for the"
                    " reset window (usually a few minutes) before retrying."
                )
            return 1

        post_text = args.text or ""
        print(f"Creating post: '{post_text}'")
        if media_id:
            post = post_service.create_post(
                text=post_text, media_ids=[media_id]
            )
            print(f"✅ Post created with media: {post.id}")
        else:
            post = post_service.create_post(text=post_text)
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
