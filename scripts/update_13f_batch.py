#!/usr/bin/env python3
"""13F Holdings Batch Update Script.

Updates the local 13F cache from MinIO storage.
Run quarterly or on-demand to refresh institutional holdings data.

Usage:
    python scripts/update_13f_batch.py [--year 2024] [--force]
"""

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def get_s3_client():
    """Initialize S3 client for MinIO."""
    import boto3
    from botocore.client import Config

    endpoint = os.environ.get("MINIO_ENDPOINT", "https://minio.api.whaleforce.dev")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "whaleforce")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "whaleforce.ai")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )


def list_available_ciks(s3_client, bucket: str, year: int) -> list[str]:
    """List all available CIKs for a given year."""
    prefix = f"{year}/"
    ciks = set()

    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
            for prefix_info in page.get("CommonPrefixes", []):
                # Extract CIK from prefix like "2024/0001234567/"
                cik = prefix_info["Prefix"].split("/")[1]
                if cik:
                    ciks.add(cik)
    except Exception as e:
        logger.error(f"Failed to list CIKs: {e}")

    return sorted(ciks)


def download_filing(s3_client, bucket: str, key: str) -> dict | None:
    """Download and parse a filing from MinIO."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read()
        return json.loads(content)
    except Exception as e:
        logger.debug(f"Failed to download {key}: {e}")
        return None


def build_holdings_cache(
    s3_client,
    bucket: str,
    year: int,
    output_dir: Path,
    force: bool = False,
) -> dict:
    """Build local cache of 13F holdings.

    Args:
        s3_client: S3 client
        bucket: Bucket name
        year: Year to process
        output_dir: Directory to save cache
        force: Force rebuild even if cache exists

    Returns:
        Summary statistics
    """
    cache_file = output_dir / f"13f_cache_{year}.json"

    if cache_file.exists() and not force:
        logger.info(f"Cache exists: {cache_file}, use --force to rebuild")
        with open(cache_file) as f:
            return json.load(f)

    logger.info(f"Building 13F cache for {year}...")

    ciks = list_available_ciks(s3_client, bucket, year)
    logger.info(f"Found {len(ciks)} CIKs for {year}")

    holdings_by_ticker = {}
    stats = {"year": year, "ciks_processed": 0, "filings_parsed": 0, "tickers_found": 0}

    for i, cik in enumerate(ciks):
        if (i + 1) % 100 == 0:
            logger.info(f"Processing CIK {i + 1}/{len(ciks)}...")

        # List filings for this CIK
        prefix = f"{year}/{cik}/"
        try:
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            keys = [obj["Key"] for obj in response.get("Contents", [])]
        except Exception:
            continue

        for key in keys:
            filing = download_filing(s3_client, bucket, key)
            if not filing:
                continue

            stats["filings_parsed"] += 1

            # Extract holdings
            filer_info = filing.get("filerInfo", {})
            filer_name = filer_info.get("name", "Unknown")
            filer_cik = filer_info.get("cik", cik)

            holdings = filing.get("holdings", filing.get("infotable", []))
            for h in holdings:
                # Get ticker from cusip or nameOfIssuer
                cusip = h.get("cusip", "")
                issuer = h.get("nameOfIssuer", "")
                ticker = h.get("ticker", "")  # May not be present

                if not ticker and issuer:
                    # Use issuer name as key for now
                    ticker = issuer[:20].upper().replace(" ", "_")

                if not ticker:
                    continue

                if ticker not in holdings_by_ticker:
                    holdings_by_ticker[ticker] = []

                shares = int(h.get("shrsOrPrnAmt", {}).get("sshPrnamt", 0))
                value = float(h.get("value", 0)) * 1000  # Often in thousands

                holdings_by_ticker[ticker].append({
                    "manager_name": filer_name,
                    "manager_cik": filer_cik,
                    "shares": shares,
                    "value": value,
                    "pct_of_portfolio": float(h.get("pctOfPortfolio", 0)),
                })

        stats["ciks_processed"] += 1

    stats["tickers_found"] = len(holdings_by_ticker)

    # Save cache
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "metadata": stats,
        "updated_at": date.today().isoformat(),
        "holdings": holdings_by_ticker,
    }

    with open(cache_file, "w") as f:
        json.dump(cache_data, f, ensure_ascii=False)

    logger.info(f"Cache saved: {cache_file}")
    logger.info(f"Stats: {stats}")

    return cache_data


def main():
    parser = argparse.ArgumentParser(description="Update 13F holdings cache")
    parser.add_argument("--year", type=int, default=date.today().year, help="Year to process")
    parser.add_argument("--force", action="store_true", help="Force rebuild cache")
    parser.add_argument("--output", type=str, default="data/13f", help="Output directory")
    args = parser.parse_args()

    logger.info("=== 13F Batch Update ===")
    logger.info(f"Year: {args.year}")
    logger.info(f"Output: {args.output}")

    s3_client = get_s3_client()
    output_dir = Path(args.output)

    result = build_holdings_cache(
        s3_client,
        bucket="13f",
        year=args.year,
        output_dir=output_dir,
        force=args.force,
    )

    logger.info("=== Complete ===")
    logger.info(f"Tickers in cache: {result.get('metadata', {}).get('tickers_found', 0)}")


if __name__ == "__main__":
    main()
