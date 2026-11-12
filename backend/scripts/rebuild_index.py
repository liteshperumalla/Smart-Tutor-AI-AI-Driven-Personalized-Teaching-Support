#!/usr/bin/env python3
"""Rebuild the RAG vector index for the active embedding model.

Reads every chunk under ``chunks/`` in S3_DOCUMENTS_BUCKET, embeds its text
with the model set by EMBEDDING_PROVIDER / EMBEDDING_MODEL, and uploads the
index to that model's own key (config.VECTOR_INDEX_KEY). Other models'
indexes, including the Titan one, are left untouched, so switching back is
just a config change.

Replaces the scripts in scripts/s3-vectors/ for this job.

Usage (from the repository root, with the backend env loaded):

    EMBEDDING_PROVIDER=huggingface python -m backend.scripts.rebuild_index --dry-run
    EMBEDDING_PROVIDER=huggingface python -m backend.scripts.rebuild_index

    # Inside the running backend container on the server:
    docker exec smart-tutor-staging-backend python -m backend.scripts.rebuild_index

    # Is the index there yet? (exit 0 yes, 3 no)
    python -m backend.scripts.rebuild_index --check

Re-embedding ~13k chunks takes hours on one CPU, so progress is saved to a
checkpoint file every couple of minutes (``--checkpoint``; by default under
/app/chroma_db, which staging mounts from the host). Running it again after
an interruption carries on from there. The checkpoint is deleted once the
index is uploaded.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

CHECKPOINT_DIRS = ("/app/chroma_db", ".")


def default_checkpoint(index_key: str) -> str:
    """A writable place that survives container restarts when it can."""
    configured = os.getenv("REINDEX_CHECKPOINT_DIR", "").strip()
    dirs = (configured,) if configured else CHECKPOINT_DIRS
    for directory in dirs:
        if os.path.isdir(directory) and os.access(directory, os.W_OK):
            return str(Path(directory) / f"reindex-{Path(index_key).name}.ckpt")
    return f"reindex-{Path(index_key).name}.ckpt"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="count the chunks and show where the index would go")
    parser.add_argument("--bucket", help="override S3_DOCUMENTS_BUCKET")
    parser.add_argument(
        "--allow-titan",
        action="store_true",
        help="allow rebuilding the Titan (AWS) index; it is normally rebuilt from inline vectors on demand",
    )
    parser.add_argument("--check", action="store_true", help="exit 0 if this model's index exists, 3 if not")
    parser.add_argument("--checkpoint", help="checkpoint file (default: under /app/chroma_db or the current directory)")
    parser.add_argument("--no-checkpoint", action="store_true", help="don't save or resume progress")
    parser.add_argument("--checkpoint-every", type=float, default=120.0, help="seconds between checkpoints (default 120)")
    args = parser.parse_args(argv)

    from backend.config import config
    from backend.s3_vector_store import S3VectorStore

    bucket = args.bucket or config.S3_DOCUMENTS_BUCKET
    print(f"Embedding provider : {config.EMBEDDING_PROVIDER}")
    print(f"Embedding model    : {config.EMBEDDING_MODEL_ID}")
    print(f"Bucket             : {bucket} ({config.S3_ENDPOINT_URL or 'AWS S3'})")
    print(f"Index key          : {config.VECTOR_INDEX_KEY}")

    if config.EMBEDDING_PROVIDER == "bedrock" and not args.allow_titan:
        print(
            "\nEMBEDDING_PROVIDER is bedrock: the Titan index is built from the chunks' inline "
            "vectors and needs no re-embedding. Set EMBEDDING_PROVIDER=huggingface to build the "
            "free index, or pass --allow-titan.",
            file=sys.stderr,
        )
        return 2

    store = S3VectorStore(bucket_name=bucket)
    if args.check:
        if store.index_exists():
            print("Index status       : ready")
            return 0
        print("Index status       : missing (run without --check to build it)")
        return 3

    records = store.list_chunk_records()
    print(f"Chunks found       : {len(records)}")
    if args.dry_run:
        return 0
    if not records:
        print("No chunks to index.", file=sys.stderr)
        return 1

    checkpoint = None if args.no_checkpoint else (args.checkpoint or default_checkpoint(config.VECTOR_INDEX_KEY))
    if checkpoint:
        state = "resuming from it" if os.path.exists(checkpoint) else "new"
        print(f"Checkpoint         : {checkpoint} ({state})")
    sys.stdout.flush()

    started = time.monotonic()
    count = store.rebuild(checkpoint_path=checkpoint, checkpoint_every=args.checkpoint_every)
    elapsed = time.monotonic() - started
    stats = store.embedder.get_stats() if hasattr(store.embedder, "get_stats") else {}
    print(f"\n✓ Indexed {count} chunks in {elapsed:.0f}s ({stats.get('dimension', '?')} dimensions)")
    print(f"  Uploaded s3://{bucket}/{config.VECTOR_INDEX_KEY}")
    if count < len(records):
        print(f"  {len(records) - count} chunks were skipped (empty text or read errors; see the log).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
