from __future__ import annotations

import base64
import json
import re
from datetime import date, datetime
from typing import Any

import requests

from app.config import KIMI_API_KEY, KIMI_BASE_URL, KIMI_MODEL


class OCRError(Exception):
    pass


def _extract_json_block(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise OCRError("OCR 返回内容为空")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise OCRError("OCR 返回内容不是合法 JSON")

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise OCRError(f"OCR JSON 解析失败: {exc}") from exc


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_date = str(payload.get("report_date") or date.today().isoformat())
    try:
        report_date = datetime.strptime(raw_date, "%Y-%m-%d").date().isoformat()
    except ValueError:
        report_date = date.today().isoformat()
    records = payload.get("records") or []
    if not isinstance(records, list) or len(records) == 0:
        raise OCRError("OCR 未提取到员工数据")

    normalized: list[dict[str, Any]] = []
    for raw in records:
        employee_name = str(raw.get("employee_name", "")).strip()
        if not employee_name:
            continue

        try:
            deal_count = max(0, int(raw.get("deal_count", 0)))
            high_intent_count = max(0, int(raw.get("high_intent_count", 0)))
            private_domain_new = max(0, int(raw.get("private_domain_new", 0)))
            confidence = float(raw.get("confidence", 0.85))
        except (TypeError, ValueError) as exc:
            raise OCRError(f"员工 {employee_name} 的字段格式异常") from exc

        normalized.append(
            {
                "employee_name": employee_name,
                "deal_count": deal_count,
                "high_intent_count": high_intent_count,
                "private_domain_new": private_domain_new,
                "confidence": max(0.0, min(confidence, 1.0)),
            }
        )

    if not normalized:
        raise OCRError("OCR 结果中没有可用员工数据")

    return {"report_date": report_date, "records": normalized}


def parse_sales_board(image_bytes: bytes, mime_type: str) -> dict[str, Any]:
    if not KIMI_API_KEY:
        raise OCRError("缺少 KIMI_API_KEY，无法执行自动识别")

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "你是销售白板识别助手。请从图片中提取当日每位员工数据，并只返回 JSON。"
        "JSON 结构必须是："
        '{"report_date":"YYYY-MM-DD","records":[{"employee_name":"姓名","deal_count":0,'
        '"high_intent_count":0,"private_domain_new":0,"confidence":0.0}]}'
        "。如果无法确定日期，report_date 使用今天日期。"
        "不要输出任何额外说明。"
    )

    payload = {
        "model": KIMI_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": 1200,
    }

    headers = {
        "Authorization": f"Bearer {KIMI_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            f"{KIMI_BASE_URL.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
    except requests.RequestException as exc:
        raise OCRError(f"OCR 服务连接失败: {exc}") from exc

    if response.status_code >= 400:
        raise OCRError(f"OCR 服务调用失败: HTTP {response.status_code} {response.text[:300]}")

    try:
        data = response.json()
    except ValueError as exc:
        raise OCRError("OCR 响应不是合法 JSON") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OCRError("OCR 响应结构异常，缺少 choices[0].message.content") from exc

    if isinstance(content, list):
        output_text = "\n".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
        ).strip()
    else:
        output_text = str(content).strip()

    if not output_text:
        raise OCRError("OCR 响应为空")

    parsed = _extract_json_block(output_text)
    return _normalize_payload(parsed)
