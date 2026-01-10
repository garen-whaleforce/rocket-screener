"""LLM-based transcript extraction (v5).

Extracts structured information from earnings call transcripts using LLM.
Implements chunked processing for long transcripts.

Strategy:
1. Split transcript into ~3000 token chunks with overlap
2. Extract JSON from each chunk via LLM
3. Merge and deduplicate results
4. Return unified TranscriptExtract
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.ingest.transcript_client import TranscriptExtract

logger = logging.getLogger(__name__)

# Approximate tokens per character for English text
CHARS_PER_TOKEN = 4
MAX_CHUNK_TOKENS = 3000
OVERLAP_TOKENS = 200


@dataclass
class ChunkExtract:
    """Extracted data from a single transcript chunk."""

    guidance_snippets: list[str]
    key_topics: list[str]
    new_products: list[str]
    risks: list[str]
    sentiment_indicators: list[str]  # positive/negative phrases
    qa_pairs: list[dict]  # [{question, answer_summary}]
    management_quotes: list[str]  # Notable CEO/CFO quotes


EXTRACTION_PROMPT = """你是財報電話會議分析師。請從以下電話會議逐字稿片段中抽取結構化資訊。

**逐字稿片段**：
{transcript_chunk}

**請以 JSON 格式回答**（僅輸出 JSON，不要其他文字）：
{{
    "guidance_snippets": ["與財務指引相關的句子..."],
    "key_topics": ["AI", "雲端", "毛利率", ...],
    "new_products": ["提及的新產品或服務..."],
    "risks": ["提及的風險因素..."],
    "sentiment_indicators": {{
        "positive": ["積極的詞語或表達..."],
        "negative": ["謹慎或消極的詞語..."]
    }},
    "qa_pairs": [
        {{"question": "分析師問題摘要", "answer": "管理層回答摘要"}}
    ],
    "management_quotes": ["CEO/CFO 的重要引述..."]
}}

注意：
- 只抽取明確提及的內容，不要推測
- key_topics 使用英文縮寫（AI, Cloud, Margin 等）
- 每個欄位如果沒有相關內容就回傳空陣列 []
"""

MERGE_PROMPT = """你是財報分析師。請將以下多個逐字稿分析結果合併成最終分析。

**各段落分析結果**：
{chunk_results}

**請輸出合併後的 JSON**（去重、整理、保留最重要的內容）：
{{
    "outlook_tone": "bullish/neutral/cautious",
    "sentiment_score": 0.0-1.0,
    "guidance": {{
        "revenue_mentioned": true/false,
        "eps_mentioned": true/false,
        "key_guidance": "主要指引摘要..."
    }},
    "key_topics": ["去重後的主題清單..."],
    "new_products": ["去重後的新產品..."],
    "risks_mentioned": ["去重後的風險..."],
    "qa_highlights": [
        {{"question": "重要問題", "answer_summary": "回答重點"}}
    ],
    "management_key_quotes": ["最重要的 2-3 句管理層引述"]
}}
"""


def chunk_transcript(text: str, max_tokens: int = MAX_CHUNK_TOKENS) -> list[str]:
    """Split transcript into overlapping chunks.

    Args:
        text: Full transcript text
        max_tokens: Maximum tokens per chunk

    Returns:
        List of text chunks with overlap
    """
    if not text:
        return []

    max_chars = max_tokens * CHARS_PER_TOKEN
    overlap_chars = OVERLAP_TOKENS * CHARS_PER_TOKEN

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + max_chars, text_len)

        # Try to break at sentence boundary
        if end < text_len:
            # Look for period, question mark, or newline near the end
            for offset in range(min(200, max_chars // 4)):
                check_pos = end - offset
                if check_pos > start and text[check_pos] in ".?!\n":
                    end = check_pos + 1
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start with overlap
        start = end - overlap_chars
        if start <= chunks[-1] if chunks else 0:
            start = end  # Avoid infinite loop

    logger.info(f"Split transcript into {len(chunks)} chunks")
    return chunks


def extract_from_chunk(
    llm_client,
    chunk: str,
    chunk_num: int,
    total_chunks: int,
    max_retries: int = 2,
) -> Optional[dict]:
    """Extract structured data from a single chunk using LLM.

    Args:
        llm_client: LLM client instance
        chunk: Transcript text chunk
        chunk_num: Current chunk number (1-indexed)
        total_chunks: Total number of chunks
        max_retries: Maximum retry attempts on failure

    Returns:
        Extracted data as dict, or None if failed
    """
    # Progressive chunk size reduction for retries
    chunk_limits = [8000, 6000, 4000]

    for attempt in range(max_retries + 1):
        chunk_limit = chunk_limits[min(attempt, len(chunk_limits) - 1)]
        truncated_chunk = chunk[:chunk_limit]

        prompt = EXTRACTION_PROMPT.format(transcript_chunk=truncated_chunk)

        try:
            response = llm_client.generate(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.3,
            )

            # Parse JSON from response
            json_str = response.strip()

            # Handle markdown code blocks
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            result = json.loads(json_str)
            logger.debug(f"Extracted chunk {chunk_num}/{total_chunks}")
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from chunk {chunk_num} (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                continue
            return None
        except Exception as e:
            error_str = str(e).lower()
            # Check for token limit errors
            if "token" in error_str or "length" in error_str or "limit" in error_str:
                logger.warning(f"Token limit hit for chunk {chunk_num}, reducing size (attempt {attempt + 1})")
                if attempt < max_retries:
                    continue
            logger.error(f"LLM extraction failed for chunk {chunk_num}: {e}")
            return None

    return None


def merge_chunk_results(
    llm_client,
    chunk_results: list[dict],
) -> Optional[dict]:
    """Merge multiple chunk extraction results using LLM.

    Args:
        llm_client: LLM client instance
        chunk_results: List of extraction results from chunks

    Returns:
        Merged and deduplicated result
    """
    if not chunk_results:
        return None

    if len(chunk_results) == 1:
        # Single chunk, simple conversion
        result = chunk_results[0]
        sentiment = result.get("sentiment_indicators", {})
        pos_count = len(sentiment.get("positive", []))
        neg_count = len(sentiment.get("negative", []))

        if pos_count > neg_count + 2:
            tone = "bullish"
            score = 0.7 + min(0.2, (pos_count - neg_count) * 0.02)
        elif neg_count > pos_count + 2:
            tone = "cautious"
            score = 0.3 - min(0.2, (neg_count - pos_count) * 0.02)
        else:
            tone = "neutral"
            score = 0.5

        return {
            "outlook_tone": tone,
            "sentiment_score": round(score, 2),
            "guidance": {
                "mentioned": bool(result.get("guidance_snippets")),
                "key_guidance": result.get("guidance_snippets", [""])[0] if result.get("guidance_snippets") else "",
            },
            "key_topics": result.get("key_topics", [])[:7],
            "new_products": result.get("new_products", []),
            "risks_mentioned": result.get("risks", [])[:5],
            "qa_highlights": result.get("qa_pairs", [])[:3],
            "management_key_quotes": result.get("management_quotes", [])[:3],
        }

    # Multiple chunks: use LLM to merge
    prompt = MERGE_PROMPT.format(
        chunk_results=json.dumps(chunk_results, ensure_ascii=False, indent=2)[:6000]
    )

    try:
        response = llm_client.generate(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.3,
        )

        json_str = response.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        return json.loads(json_str)

    except Exception as e:
        logger.error(f"Failed to merge chunk results: {e}")
        # Fallback: simple merge without LLM
        return _simple_merge(chunk_results)


def _simple_merge(chunk_results: list[dict]) -> dict:
    """Simple merge fallback without LLM."""
    all_topics = []
    all_risks = []
    all_products = []
    all_quotes = []
    all_qa = []
    positive_count = 0
    negative_count = 0

    for result in chunk_results:
        all_topics.extend(result.get("key_topics", []))
        all_risks.extend(result.get("risks", []))
        all_products.extend(result.get("new_products", []))
        all_quotes.extend(result.get("management_quotes", []))
        all_qa.extend(result.get("qa_pairs", []))

        sentiment = result.get("sentiment_indicators", {})
        positive_count += len(sentiment.get("positive", []))
        negative_count += len(sentiment.get("negative", []))

    # Deduplicate
    all_topics = list(dict.fromkeys(all_topics))
    all_risks = list(dict.fromkeys(all_risks))
    all_products = list(dict.fromkeys(all_products))

    # Calculate sentiment
    if positive_count > negative_count + 3:
        tone = "bullish"
        score = 0.7
    elif negative_count > positive_count + 3:
        tone = "cautious"
        score = 0.3
    else:
        tone = "neutral"
        score = 0.5

    return {
        "outlook_tone": tone,
        "sentiment_score": score,
        "guidance": {"mentioned": any(r.get("guidance_snippets") for r in chunk_results)},
        "key_topics": all_topics[:7],
        "new_products": all_products[:3],
        "risks_mentioned": all_risks[:5],
        "qa_highlights": all_qa[:3],
        "management_key_quotes": all_quotes[:3],
    }


def extract_transcript_with_llm(
    raw_transcript: dict,
    llm_client,
) -> Optional[TranscriptExtract]:
    """Extract structured data from transcript using LLM.

    Main entry point for LLM-based transcript extraction.

    Args:
        raw_transcript: Raw transcript from API (with 'text' or 'speakers')
        llm_client: LLM client for generation

    Returns:
        TranscriptExtract with LLM-enhanced extraction
    """
    if not raw_transcript:
        return None

    ticker = raw_transcript.get("ticker", "")
    quarter = raw_transcript.get("quarter", "")
    call_date_str = raw_transcript.get("date", "")

    try:
        call_date = datetime.fromisoformat(call_date_str.replace("Z", "+00:00"))
    except ValueError:
        call_date = datetime.now()

    # Get full text from transcript
    speakers = raw_transcript.get("speakers", [])
    if speakers:
        # Combine speaker texts with speaker attribution
        text_parts = []
        for s in speakers:
            name = s.get("name", "Speaker")
            title = s.get("title", "")
            text = s.get("text", "")
            if title:
                text_parts.append(f"[{name} - {title}]: {text}")
            else:
                text_parts.append(f"[{name}]: {text}")
        full_text = "\n\n".join(text_parts)
    else:
        full_text = raw_transcript.get("text", raw_transcript.get("content", ""))

    if not full_text:
        logger.warning(f"No transcript text found for {ticker}")
        return None

    # Chunk the transcript
    chunks = chunk_transcript(full_text)
    if not chunks:
        logger.warning(f"No chunks generated for {ticker}")
        return None

    # Extract from each chunk
    chunk_results = []
    for i, chunk in enumerate(chunks):
        result = extract_from_chunk(llm_client, chunk, i + 1, len(chunks))
        if result:
            chunk_results.append(result)

    if not chunk_results:
        logger.warning(f"All chunk extractions failed for {ticker}")
        return None

    # Merge results
    merged = merge_chunk_results(llm_client, chunk_results)
    if not merged:
        logger.warning(f"Failed to merge results for {ticker}")
        return None

    logger.info(f"LLM extraction completed for {ticker}: tone={merged.get('outlook_tone')}")

    # Convert to TranscriptExtract
    return TranscriptExtract(
        ticker=ticker,
        quarter=quarter,
        call_date=call_date,
        guidance=merged.get("guidance", {}),
        outlook_tone=merged.get("outlook_tone", "neutral"),
        key_topics=merged.get("key_topics", []),
        new_products=merged.get("new_products", []),
        risks_mentioned=merged.get("risks_mentioned", []),
        qa_highlights=merged.get("qa_highlights", []),
        sentiment_score=merged.get("sentiment_score", 0.5),
        speakers=speakers,
    )


def get_enhanced_management_signals(
    transcript_extract: Optional[TranscriptExtract],
    merged_data: Optional[dict] = None,
) -> dict:
    """Get enhanced management signals from LLM extraction.

    Args:
        transcript_extract: LLM-extracted transcript data
        merged_data: Optional raw merged data from LLM

    Returns:
        Enhanced management signals dict for Article 2
    """
    if not transcript_extract:
        return {}

    signals = {
        "quarter": transcript_extract.quarter,
        "call_date": transcript_extract.call_date.isoformat(),
        "outlook_tone": transcript_extract.outlook_tone,
        "sentiment_score": transcript_extract.sentiment_score,
        "key_topics": transcript_extract.key_topics,
        "risks_mentioned": transcript_extract.risks_mentioned,
        "guidance_mentioned": bool(transcript_extract.guidance),
    }

    # Add enhanced fields if available
    if transcript_extract.qa_highlights:
        signals["qa_highlights"] = transcript_extract.qa_highlights

    if transcript_extract.new_products:
        signals["new_products"] = transcript_extract.new_products

    if merged_data:
        if merged_data.get("management_key_quotes"):
            signals["key_quotes"] = merged_data["management_key_quotes"]
        if merged_data.get("guidance", {}).get("key_guidance"):
            signals["guidance_summary"] = merged_data["guidance"]["key_guidance"]

    return signals
