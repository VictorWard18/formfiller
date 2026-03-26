"""
PDF Extractor — sends corporate PDFs to Claude API, returns structured JSON.
Handles multiple PDFs and merges into a single dictionary.
"""

import anthropic
import base64
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

EXTRACTION_PROMPT_RU = """Извлеки ВСЕ структурированные данные из этого корпоративного документа на русском языке.
Верни ТОЛЬКО валидный JSON без markdown-разметки. Используй следующую структуру:
{
  "company_name": "полное наименование компании",
  "previous_name": "прежнее наименование (если есть)",
  "legal_form": "организационно-правовая форма",
  "country": "страна регистрации",
  "registration_number": "регистрационный номер",
  "registration_date": "дата регистрации",
  "address_registered": "юридический адрес",
  "address_primary": "основной адрес (если отличается)",
  "share_capital": "уставный капитал",
  "shares_count": "количество акций",
  "share_value": "номинальная стоимость акции",
  "phone": "телефон",
  "email": "электронная почта",
  "licences": [
    {
      "number": "номер лицензии",
      "type": "тип (торговая / на услуги)",
      "issue_date": "дата выдачи",
      "expiry_date": "срок действия до",
      "status": "статус",
      "activities": ["вид деятельности 1", "вид деятельности 2"]
    }
  ],
  "shareholders": [
    {
      "full_name": "ФИО полностью",
      "surname": "фамилия",
      "given_name": "имя",
      "patronymic": "отчество",
      "nationality": "гражданство",
      "date_of_birth": "дата рождения",
      "place_of_birth": "место рождения",
      "sex": "пол",
      "passport_number": "номер паспорта",
      "passport_issue_date": "дата выдачи паспорта",
      "passport_authority": "орган выдачи паспорта",
      "passport_expiry": "срок действия паспорта",
      "address": "адрес",
      "shares": "количество акций",
      "share_type": "тип акций",
      "ownership_pct": "доля участия %"
    }
  ],
  "directors": [
    {
      "full_name": "ФИО",
      "position": "должность",
      "appointment_date": "дата назначения",
      "powers": "полномочия"
    }
  ],
  "tax_registration": {
    "inn": "ИНН",
    "kpp": "КПП",
    "tax_office": "налоговый орган",
    "registration_date": "дата постановки на учёт"
  },
  "bank_accounts": [
    {
      "currency": "валюта",
      "beneficiary": "получатель",
      "account_number": "номер счёта",
      "bank_name": "наименование банка",
      "bank_address": "адрес банка",
      "bic_swift": "БИК / SWIFT",
      "correspondent_bank": "банк-корреспондент",
      "correspondent_swift": "SWIFT корреспондента"
    }
  ]
}
Для полей, которых нет в документе, используй null. Включи ВСЕ найденные данные."""

EXTRACTION_PROMPT_EN = """Extract ALL structured data from this corporate document in English.
Return ONLY valid JSON with no markdown. Use this structure:
{
  "company_name": "full legal name",
  "previous_name": "previous name if any",
  "legal_form": "legal form",
  "country": "country of registration",
  "registration_number": "registration number",
  "registration_date": "date of registration",
  "address_registered": "registered address",
  "address_primary": "primary address (if different)",
  "share_capital": "share capital",
  "shares_count": "number of shares",
  "share_value": "nominal value per share",
  "phone": "phone",
  "email": "email",
  "licences": [
    {
      "number": "licence number",
      "type": "type (trading / service)",
      "issue_date": "issue date",
      "expiry_date": "expiry date",
      "status": "status",
      "activities": ["activity 1", "activity 2"]
    }
  ],
  "shareholders": [
    {
      "full_name": "full name",
      "surname": "surname",
      "given_name": "given name",
      "patronymic": "patronymic",
      "nationality": "nationality",
      "date_of_birth": "date of birth",
      "place_of_birth": "place of birth",
      "sex": "sex",
      "passport_number": "passport number",
      "passport_issue_date": "passport issue date",
      "passport_authority": "issuing authority",
      "passport_expiry": "passport expiry",
      "address": "address",
      "shares": "number of shares",
      "share_type": "type of shares",
      "ownership_pct": "ownership %"
    }
  ],
  "directors": [
    {
      "full_name": "full name",
      "position": "position",
      "appointment_date": "date of appointment",
      "powers": "powers"
    }
  ],
  "tax_registration": {
    "inn": "INN / TIN",
    "kpp": "KPP",
    "tax_office": "tax office",
    "registration_date": "registration date"
  },
  "bank_accounts": [
    {
      "currency": "currency",
      "beneficiary": "beneficiary",
      "account_number": "account number",
      "bank_name": "bank name",
      "bank_address": "bank address",
      "bic_swift": "BIC / SWIFT",
      "correspondent_bank": "correspondent bank",
      "correspondent_swift": "correspondent SWIFT"
    }
  ]
}
Use null for fields not found. Include ALL data you find."""

MERGE_PROMPT_RU = """Ниже приведены данные, извлечённые из нескольких корпоративных документов одной компании:

{extractions}

Объедини их в ОДИН полный справочник данных. Правила:
- Удали дубликаты, оставь наиболее полную версию каждого поля
- Если есть конфликты (например, старое и новое наименование), сохрани оба значения
- Верни ТОЛЬКО валидный JSON без markdown
- Язык: русский"""

MERGE_PROMPT_EN = """Below are data extractions from multiple corporate documents for the same company:

{extractions}

Merge into ONE comprehensive data dictionary. Rules:
- Deduplicate: keep the most complete version of each field
- If conflicts exist (e.g. old name vs new name), keep both values
- Return ONLY valid JSON with no markdown
- Language: English"""


def extract_single_pdf(pdf_bytes: bytes, language: str = "ru") -> dict:
    """Extract structured data from a single PDF."""
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    prompt = EXTRACTION_PROMPT_RU if language == "ru" else EXTRACTION_PROMPT_EN

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse extraction JSON: {e}\nRaw: {raw[:500]}")
        return {"_raw_text": raw, "_parse_error": str(e)}


def merge_extractions(extractions: list[dict], language: str = "ru") -> dict:
    """Merge multiple PDF extractions into one dictionary via Claude."""
    if len(extractions) == 1:
        return extractions[0]

    template = MERGE_PROMPT_RU if language == "ru" else MERGE_PROMPT_EN
    prompt = template.format(
        extractions=json.dumps(extractions, ensure_ascii=False, indent=2)
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse merged JSON: {e}")
        # Fallback: return first extraction
        return extractions[0]


async def extract_and_merge(pdf_files: list[tuple[str, bytes]], language: str = "ru") -> dict:
    """
    Main entry point: takes list of (filename, bytes) pairs,
    extracts from each, merges into one dictionary.
    """
    extractions = []
    for filename, pdf_bytes in pdf_files:
        logger.info(f"Extracting from {filename}...")
        result = extract_single_pdf(pdf_bytes, language)
        result["_source_file"] = filename
        extractions.append(result)

    logger.info(f"Merging {len(extractions)} extractions...")
    merged = merge_extractions(extractions, language)
    return merged
