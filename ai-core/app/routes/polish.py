import json
import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

from ..config import FILE_DIR
from ..database import add_message, get_files_by_conv, get_conversation, update_conversation_title, create_task, update_task
from ..services.actor_critic import run_actor_critic_stream
from ..services.file_service import save_upload_file, save_generated_file, read_text_file
from ..services.mode_detector import detect_mode_suggestion
from ..services.auto_file_service import try_auto_generate_file
from ..services.rag_service import build_rag_context
from ..services.tool_registry import get_tools_for_mode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/polish", tags=["polish"])

LANGUAGE_MAP = {
    "auto": {"name": "自动识别", "native": "自动识别", "prompt_lang": "auto"},
    "en": {"name": "英文", "native": "English", "prompt_lang": "auto"},
    "zh": {"name": "中文", "native": "中文", "prompt_lang": "auto"},
    "ja": {"name": "日文", "native": "日本語", "prompt_lang": "auto"},
    "ko": {"name": "韩文", "native": "한국어", "prompt_lang": "auto"},
    "fr": {"name": "法文", "native": "Français", "prompt_lang": "auto"},
    "de": {"name": "德文", "native": "Deutsch", "prompt_lang": "auto"},
    "es": {"name": "西班牙文", "native": "Español", "prompt_lang": "auto"},
    "ru": {"name": "俄文", "native": "Русский", "prompt_lang": "auto"},
    "pt": {"name": "葡萄牙文", "native": "Português", "prompt_lang": "auto"},
    "it": {"name": "意大利文", "native": "Italiano", "prompt_lang": "auto"},
    "ar": {"name": "阿拉伯文", "native": "العربية", "prompt_lang": "auto"},
}

STYLE_MAP = {
    "academic": {
        "zh": "学术风格 - 正式、严谨、逻辑清晰，使用专业术语",
        "en": "Academic style - formal, rigorous, logically clear, use professional terminology",
        "ja": "学術スタイル - 正式で厳密、論理的で明確、専門用語を使用",
        "ko": "학술 스타일 - 공식적이고 엄격하며 논리적으로 명확한 전문 용어 사용",
        "fr": "Style académique - formel, rigoureux, logique, utiliser une terminologie professionnelle",
        "de": "Akademischer Stil - formell, streng, logisch klar, Fachbegriffe verwenden",
        "es": "Estilo académico - formal, riguroso, lógicamente claro, usar terminología profesional",
        "ru": "Академический стиль - формальный, строгий, логически ясный, использовать профессиональную терминологию",
        "pt": "Estilo acadêmico - formal, rigoroso, logicamente claro, usar terminologia profissional",
        "it": "Stile accademico - formale, rigoroso, logicamente chiaro, usare terminologia professionale",
        "ar": "أسلوب أكاديمي - رسمي، دقيق، واضح منطقياً، استخدام المصطلحات المهنية",
    },
    "business": {
        "zh": "商务风格 - 专业、简洁、有说服力，适合商业场景",
        "en": "Business style - professional, concise, persuasive, suitable for business scenarios",
        "ja": "ビジネススタイル - プロフェッショナルで簡潔、説得力があり、ビジネスシーンに適している",
        "ko": "비즈니스 스타일 - 전문적이고 간결하며 설득력 있으며 비즈니스 시나리오에 적합",
        "fr": "Style commercial - professionnel, concis, persuasif, adapté aux scénarios commerciaux",
        "de": "Geschäftsstil - professionell, prägnant, überzeugend, geeignet für Geschäftsszenarien",
        "es": "Estilo empresarial - profesional, conciso, persuasivo, adecuado para escenarios de negocios",
        "ru": "Деловой стиль - профессиональный, лаконичный, убедительный, подходит для бизнес-сценариев",
        "pt": "Estilo empresarial - profissional, conciso, persuasivo, adequado para cenários de negócios",
        "it": "Stile aziendale - professionale, conciso, persuasivo, adatto a scenari aziendali",
        "ar": "أسلوب تجاري - احترافي، موجز، مقنع، مناسب لسيناريوهات الأعمال",
    },
    "formal": {
        "zh": "正式风格 - 礼貌、规范、得体",
        "en": "Formal style - polite, standardized, appropriate",
        "ja": "フォーマルスタイル - 礼儀正しく、規範的で、適切",
        "ko": "공식 스타일 - 예의 바르고 표준화되며 적절함",
        "fr": "Style formel - poli, standardisé, approprié",
        "de": "Formeller Stil - höflich, standardisiert, angemessen",
        "es": "Estilo formal - educado, estandarizado, apropiado",
        "ru": "Формальный стиль - вежливый, стандартизированный, уместный",
        "pt": "Estilo formal - educado, padronizado, apropriado",
        "it": "Stile formale - educato, standardizzato, appropriato",
        "ar": "أسلوب رسمي - مهذب، موحد، مناسب",
    },
    "email_professor": {
        "zh": "给教授发邮件风格 - 礼貌、尊重、简洁",
        "en": "Email to professor style - polite, respectful, concise",
        "ja": "教授へのメールスタイル - 礼儀正しく、敬意を払い、簡潔",
        "ko": "교수님 이메일 스타일 - 예의 바르고 존중하며 간결함",
        "fr": "Style d'email au professeur - poli, respectueux, concis",
        "de": "E-Mail an Professor Stil - höflich, respektvoll, prägnant",
        "es": "Estilo de email al profesor - educado, respetuoso, conciso",
        "ru": "Стиль письма профессору - вежливый, уважительный, лаконичный",
        "pt": "Estilo de email para professor - educado, respeitoso, conciso",
        "it": "Stile email al professore - educato, rispettoso, conciso",
        "ar": "أسلوب البريد الإلكتروني للأستاذ - مهذب، محترم، موجز",
    },
    "casual": {
        "zh": "日常风格 - 自然、友好、轻松",
        "en": "Casual style - natural, friendly, relaxed",
        "ja": "カジュアルスタイル - 自然で友好的、リラックスした",
        "ko": "캐주얼 스타일 - 자연스럽고 친근하며 편안함",
        "fr": "Style décontracté - naturel, amical, détendu",
        "de": "Lässiger Stil - natürlich, freundlich, entspannt",
        "es": "Estilo casual - natural, amigable, relajado",
        "ru": "Повседневный стиль - естественный, дружелюбный, расслабленный",
        "pt": "Estilo casual - natural, amigável, descontraído",
        "it": "Stile casual - naturale, amichevole, rilassato",
        "ar": "أسلوب غير رسمي - طبيعي، ودود، مريح",
    },
}

POLLISH_PROMPTS = {
    "zh": "你是一个专业的多语言文本润色 AI。请根据用户需求对文本进行润色和翻译。\n\n润色要点：\n1. 提升语言流畅度和专业性\n2. 修正语法错误和不规范表达\n3. 保持原文核心意思不变\n4. 根据目标语言和风格进行调整\n\n输出格式：\n1. 先输出润色/翻译后的完整文本\n2. 如有重要修改，在括号中简要说明",
    "en": "You are a professional multilingual text polishing AI. Polish and translate the text according to user requirements.\n\nPolishing points:\n1. Improve language fluency and professionalism\n2. Fix grammar errors and non-standard expressions\n3. Keep the original core meaning unchanged\n4. Adjust according to target language and style\n\nOutput format:\n1. First output the polished/translated complete text\n2. Briefly explain important changes in parentheses",
    "ja": "あなたはプロの多言語テキスト校正AIです。ユーザーの要件に従ってテキストを校正・翻訳してください。\n\n校正ポイント：\n1. 言語の流暢さと専門性を向上させる\n2. 文法エラーや不適切な表現を修正する\n3. 原文の核心的な意味を変えない\n4. 対象言語とスタイルに合わせて調整する\n\n出力形式：\n1. 最初に校正・翻訳された完全なテキストを出力する\n2. 重要な修正があれば括弧内に簡単に説明する",
    "ko": "당신은 전문적인 다국어 텍스트 교정 AI입니다. 사용자 요구에 따라 텍스트를 교정하고 번역하세요.\n\n교정 포인트:\n1. 언어 유창성과 전문성 향상\n2. 문법 오류 및 비표준 표현 수정\n3. 원문의 핵심 의미 유지\n4. 대상 언어와 스타일에 맞게 조정\n\n출력 형식:\n1. 먼저 교정/번역된 완전한 텍스트 출력\n2. 중요한 수정 사항이 있으면 괄호 안에 간략히 설명",
    "fr": "Vous êtes une IA professionnelle de correction de texte multilingue. Corrigez et traduisez le texte selon les besoins de l'utilisateur.\n\nPoints de correction:\n1. Améliorer la fluidité et le professionnalisme du langage\n2. Corriger les erreurs grammaticales et les expressions non standard\n3. Garder le sens original inchangé\n4. Ajuster selon la langue et le style cibles\n\nFormat de sortie:\n1. D'abord sortir le texte complet corrigé/traduit\n2. Expliquer brièvement les modifications importantes entre parenthèses",
    "de": "Sie sind eine professionelle mehrsprachige Textkorrektur-KI. Korrigieren und übersetzen Sie den Text gemäß den Benutzeranforderungen.\n\nKorrekturpunkte:\n1. Sprachfluss und Professionalität verbessern\n2. Grammatikfehler und nicht standardmäßige Ausdrücke korrigieren\n3. Die ursprüngliche Kernbedeutung unverändert lassen\n4. An Zielsprache und -stil anpassen\n\nAusgabeformat:\n1. Zuerst den korrigierten/übersetzten vollständigen Text ausgeben\n2. Wichtige Änderungen kurz in Klammern erklären",
    "es": "Eres una IA profesional de corrección de texto multilingüe. Corrige y traduce el texto según los requisitos del usuario.\n\nPuntos de corrección:\n1. Mejorar la fluidez y profesionalidad del lenguaje\n2. Corregir errores gramaticales y expresiones no estándar\n3. Mantener el significado original sin cambios\n4. Ajustar según el idioma y estilo objetivo\n\nFormato de salida:\n1. Primero mostrar el texto completo corregido/traducido\n2. Explicar brevemente los cambios importantes entre paréntesis",
    "ru": "Вы профессиональный ИИ для коррекции многоязычного текста. Исправляйте и переводите текст в соответствии с требованиями пользователя.\n\nПункты коррекции:\n1. Улучшить беглость языка и профессионализм\n2. Исправить грамматические ошибки и нестандартные выражения\n3. Сохранить исходный смысл без изменений\n4. Настроить в соответствии с целевым языком и стилем\n\nФормат вывода:\n1. Сначала вывести исправленный/переведенный полный текст\n2. Кратко объяснить важные изменения в скобках",
    "pt": "Você é uma IA profissional de correção de texto multilíngue. Corrija e traduza o texto de acordo com os requisitos do usuário.\n\nPontos de correção:\n1. Melhorar a fluência e profissionalismo da linguagem\n2. Corrigir erros gramaticais e expressões não padronizadas\n3. Manter o significado original inalterado\n4. Ajustar de acordo com o idioma e estilo alvo\n\nFormato de saída:\n1. Primeiro exibir o texto completo corrigido/traduzido\n2. Explicar brevemente as alterações importantes entre parênteses",
    "it": "Sei un'IA professionale di correzione testi multilingue. Correggi e traduci il testo secondo i requisiti dell'utente.\n\nPunti di correzione:\n1. Migliorare la fluidità e professionalità del linguaggio\n2. Correggere errori grammaticali ed espressioni non standard\n3. Mantenere invariato il significato originale\n4. Adattare in base alla lingua e allo stile di destinazione\n\nFormato di output:\n1. Prima visualizzare il testo completo corretto/tradotto\n2. Spiegare brevemente le modifiche importanti tra parentesi",
    "ar": "أنت محترف في تصحيح النصوص متعددة اللغات بالذكاء الاصطناعي. قم بتصحيح وترجمة النص وفقاً لمتطلبات المستخدم.\n\nنقاط التصحيح:\n1. تحسين طلاقة اللغة واحترافيتها\n2. تصحيح الأخطاء النحوية والتعبيرات غير القياسية\n3. الحفاظ على المعنى الأصلي دون تغيير\n4. الضبط وفقاً للغة والأسلوب المستهدفين\n\nتنسيق الإخراج:\n1. أولاً إخراج النص الكامل المصحح/المترجم\n2. شرح التغييرات المهمة بإيجاز بين قوسين",
}


def _detect_source_language(text: str) -> dict:
    zh_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
    ja_chars = sum(1 for c in text if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff')
    ko_chars = sum(1 for c in text if '\uac00' <= c <= '\ud7af' or '\u1100' <= c <= '\u11ff')
    ar_chars = sum(1 for c in text if '\u0600' <= c <= '\u06ff')
    ru_chars = sum(1 for c in text if '\u0400' <= c <= '\u04ff')
    total = max(len(text), 1)

    if zh_chars > total * 0.15:
        return {"lang": "zh", "name": "中文", "confidence": min(zh_chars / total, 1.0)}
    if ja_chars > total * 0.1:
        return {"lang": "ja", "name": "日文", "confidence": min(ja_chars / total, 1.0)}
    if ko_chars > total * 0.15:
        return {"lang": "ko", "name": "韩文", "confidence": min(ko_chars / total, 1.0)}
    if ar_chars > total * 0.1:
        return {"lang": "ar", "name": "阿拉伯文", "confidence": min(ar_chars / total, 1.0)}
    if ru_chars > total * 0.1:
        return {"lang": "ru", "name": "俄文", "confidence": min(ru_chars / total, 1.0)}

    latin_text = ''.join(c for c in text if c.isalpha())
    if latin_text:
        common_en = {'the', 'is', 'are', 'was', 'were', 'and', 'for', 'that', 'this', 'with', 'have', 'has', 'from', 'they', 'will', 'would', 'should', 'could', 'been', 'being'}
        common_fr = {'le', 'la', 'les', 'des', 'est', 'sont', 'dans', 'pour', 'avec', 'une', 'que', 'pas', 'sur', 'qui', 'plus'}
        common_de = {'der', 'die', 'das', 'und', 'ist', 'sind', 'von', 'mit', 'auf', 'für', 'nicht', 'sich', 'auch', 'werden', 'ein', 'eine'}
        common_es = {'que', 'los', 'las', 'del', 'una', 'con', 'para', 'por', 'está', 'son', 'más', 'como', 'pero', 'entre'}
        common_pt = {'que', 'não', 'para', 'com', 'uma', 'está', 'são', 'dos', 'das', 'mas', 'como', 'pelo', 'pela'}
        common_it = {'che', 'non', 'una', 'sono', 'per', 'con', 'del', 'della', 'degli', 'delle', 'questo', 'quella'}

        words = set(latin_text.lower().split())
        scores = {
            "en": len(words & common_en),
            "fr": len(words & common_fr),
            "de": len(words & common_de),
            "es": len(words & common_es),
            "pt": len(words & common_pt),
            "it": len(words & common_it),
        }
        best = max(scores, key=scores.get)
        if scores[best] >= 2:
            lang_names = {"en": "英文", "fr": "法文", "de": "德文", "es": "西班牙文", "pt": "葡萄牙文", "it": "意大利文"}
            return {"lang": best, "name": lang_names.get(best, best), "confidence": 0.7}
        return {"lang": "en", "name": "英文", "confidence": 0.5}

    return {"lang": "en", "name": "英文", "confidence": 0.3}


def _get_prompt_lang(source_language: str | None = None) -> str:
    if source_language and source_language in LANGUAGE_MAP:
        return source_language
    return "en"


def _get_system_prompt(source_language: str | None = None) -> str:
    prompt_lang = _get_prompt_lang(source_language)
    return POLLISH_PROMPTS.get(prompt_lang, POLLISH_PROMPTS["en"])


def _get_style_desc(style: str, source_language: str | None = None) -> str:
    prompt_lang = _get_prompt_lang(source_language)
    style_info = STYLE_MAP.get(style, STYLE_MAP["academic"])
    return style_info.get(prompt_lang, style_info.get("en", str(style)))


def _build_polish_prompt(text: str, target_language: str, style: str, source_lang_info: dict | None = None) -> tuple[str, str]:
    source_lang = source_lang_info["lang"] if source_lang_info else "auto"
    prompt_lang = _get_prompt_lang(source_lang if source_lang != "auto" else None)
    style_desc = _get_style_desc(style, source_lang if source_lang != "auto" else None)
    lang_info = LANGUAGE_MAP.get(target_language, LANGUAGE_MAP["en"])

    needs_translation = False
    lang_mismatch = None
    if target_language != "auto" and source_lang_info:
        if source_lang_info["lang"] != target_language and source_lang_info["confidence"] > 0.3:
            needs_translation = True
            lang_mismatch = {
                "source_language": source_lang_info["lang"],
                "source_language_name": source_lang_info["name"],
                "target_language": target_language,
                "target_language_name": lang_info["name"],
                "message": f"检测到原文语言为{source_lang_info['name']}，但目标语言选择了{lang_info['name']}。是否需要翻译？",
            }

    if target_language == "auto":
        lang_desc_map = {
            "zh": "自动识别原文语言，保持与原文相同的语言输出",
            "en": "Auto-detect the source language and output in the same language",
            "ja": "原文の言語を自動検出し、同じ言語で出力する",
            "ko": "원문 언어를 자동 감지하고 동일한 언어로 출력",
        }
        lang_desc = lang_desc_map.get(prompt_lang, "Auto-detect and output in the same language")
    else:
        lang_desc_map = {
            "zh": f"目标输出语言：{lang_info['native']}（{lang_info['name']}）",
            "en": f"Target output language: {lang_info['native']} ({lang_info['name']})",
            "ja": f"目標出力言語：{lang_info['native']}（{lang_info['name']}）",
            "ko": f"대상 출력 언어: {lang_info['native']} ({lang_info['name']})",
            "fr": f"Langue de sortie cible: {lang_info['native']} ({lang_info['name']})",
            "de": f"Zielausgabesprache: {lang_info['native']} ({lang_info['name']})",
            "es": f"Idioma de salida objetivo: {lang_info['native']} ({lang_info['name']})",
            "ru": f"Целевой язык вывода: {lang_info['native']} ({lang_info['name']})",
            "pt": f"Idioma de saída alvo: {lang_info['native']} ({lang_info['name']})",
            "it": f"Lingua di output target: {lang_info['native']} ({lang_info['name']})",
            "ar": f"لغة الإخراج المستهدفة: {lang_info['native']} ({lang_info['name']})",
        }
        lang_desc = lang_desc_map.get(prompt_lang, f"Target output language: {lang_info['native']} ({lang_info['name']})")

    prompt_map = {
        "zh": f"请对以下文本进行润色。\n\n{style_desc}\n{lang_desc}\n\n原文：\n{text}",
        "en": f"Please polish the following text.\n\n{style_desc}\n{lang_desc}\n\nOriginal text:\n{text}",
        "ja": f"以下のテキストを校正してください。\n\n{style_desc}\n{lang_desc}\n\n原文：\n{text}",
        "ko": f"다음 텍스트를 교정해 주세요.\n\n{style_desc}\n{lang_desc}\n\n원문:\n{text}",
        "fr": f"Veuillez corriger le texte suivant.\n\n{style_desc}\n{lang_desc}\n\nTexte original:\n{text}",
        "de": f"Bitte korrigieren Sie den folgenden Text.\n\n{style_desc}\n{lang_desc}\n\nOriginaltext:\n{text}",
        "es": f"Por favor, corrija el siguiente texto.\n\n{style_desc}\n{lang_desc}\n\nTexto original:\n{text}",
        "ru": f"Пожалуйста, исправьте следующий текст.\n\n{style_desc}\n{lang_desc}\n\nИсходный текст:\n{text}",
        "pt": f"Por favor, corrija o seguinte texto.\n\n{style_desc}\n{lang_desc}\n\nTexto original:\n{text}",
        "it": f"Si prega di correggere il seguente testo.\n\n{style_desc}\n{lang_desc}\n\nTesto originale:\n{text}",
        "ar": f"يرجى تصحيح النص التالي.\n\n{style_desc}\n{lang_desc}\n\nالنص الأصلي:\n{text}",
    }

    prompt = prompt_map.get(prompt_lang, prompt_map["en"])
    return prompt, lang_mismatch, needs_translation


class DetectLanguageRequest(BaseModel):
    text: str


class PolishRequest(BaseModel):
    text: str
    target_language: str = "auto"
    style: str = "academic"
    model_override: str | None = None
    conv_id: str | None = None
    mode: str = "polish"
    ref_files: list[dict] | None = None
    skip_thinking: bool = False
    detect_source_lang: bool = False
    confirm_lang: bool = False


class PolishFileRequest(BaseModel):
    file_path: str
    target_language: str = "auto"
    style: str = "academic"
    user_instruction: str = ""
    inplace: bool = False
    model_override: str | None = None
    conv_id: str | None = None
    confirm_lang: bool = False
    skip_thinking: bool = False


@router.post("/detect-language")
async def detect_language(req: DetectLanguageRequest):
    source_lang_info = _detect_source_language(req.text)
    return source_lang_info


@router.post("/stream")
async def polish_stream(req: PolishRequest):
    async def generate():
        try:
            source_lang_info = None
            if req.detect_source_lang:
                source_lang_info = _detect_source_language(req.text)
                logger.info(f"Detected source language: {source_lang_info}")

            prompt, lang_mismatch, needs_translation = _build_polish_prompt(
                req.text, req.target_language, req.style, source_lang_info
            )

            if lang_mismatch and req.detect_source_lang and not req.confirm_lang:
                yield f"data: {json.dumps({'type': 'lang_mismatch', **lang_mismatch}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            suggestion = detect_mode_suggestion(req.text, "polish")
            if suggestion:
                yield f"data: {json.dumps(suggestion, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            resolved_source = source_lang_info["lang"] if source_lang_info else "auto"
            resolved_target = req.target_language
            if resolved_target == "auto" and source_lang_info:
                resolved_target = source_lang_info["lang"]
            is_translation = needs_translation or (resolved_source != resolved_target and resolved_source != "auto" and resolved_target != "auto")
            operation_type = "translation" if is_translation else "polish"

            polish_metadata = json.dumps({
                "source_language": resolved_source,
                "target_language": resolved_target,
                "style": req.style,
                "operation_type": operation_type,
            }, ensure_ascii=False)

            if req.conv_id:
                task_info = create_task("polish", req.text[:200])
                conv = get_conversation(req.conv_id)
                user_msg_count = len([m for m in conv.get("messages", []) if m["role"] == "user"]) if conv else 0
            system_prompt = _get_system_prompt(source_lang_info["lang"] if source_lang_info else None)

            rag_context = None
            try:
                rag_context = build_rag_context(query=req.text, mode="polish", conv_id=req.conv_id, top_k=5)
                if rag_context:
                    logger.info(f"[polish] RAG context built ({len(rag_context)} chars)")
            except Exception as e:
                logger.warning(f"[polish] RAG context failed: {e}")

            react_tools = get_tools_for_mode("polish")
            has_files = bool(req.ref_files and len(req.ref_files) > 0)
            enable_react = has_files
            logger.info(f"[polish] ReAct {'enabled' if enable_react else 'disabled'} (has_files={has_files}), tools: {[t['function']['name'] for t in react_tools]}")

            polished_file = None
            async for event in run_actor_critic_stream(
                user_message=prompt,
                system_prompt_override=system_prompt,
                conv_id=req.conv_id,
                mode="polish",
                skip_thinking=req.skip_thinking,
                rag_context=rag_context,
                enable_react=enable_react,
                react_tools=react_tools,
            ):
                if event.get("type") == "actor_done" and event.get("title") and req.conv_id:
                    try:
                        update_conversation_title(req.conv_id, event["title"], mode="polish")
                        event["title_generated"] = True
                    except Exception:
                        pass
                if event.get("type") == "complete":
                    output = event.get("output", "")
                    if req.conv_id:
                        add_message(req.conv_id, "actor", output, metadata=polish_metadata)
                    try:
                        update_task(task_info["task_id"], "completed", output[:500])
                    except Exception:
                        pass
                    auto_file = try_auto_generate_file(output, req.text, req.conv_id, "polish")
                    if auto_file:
                        event["file"] = auto_file
                        yield f"data: {json.dumps({'type': 'file_generated', 'file': auto_file}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Polish stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/upload")
async def upload_polish_file(
    file: UploadFile = File(...),
    mode: str = Form("polish"),
    conv_id: str | None = Form(None),
):
    file_info = await save_upload_file(file, conv_id, mode)
    try:
        file_content = read_text_file(file_info["file_path"])
        file_info["content"] = file_content[:1000]
        source_lang_info = _detect_source_language(file_content)
        file_info["detected_language"] = source_lang_info
    except Exception:
        file_info["content"] = ""
    return file_info


@router.post("/file")
async def polish_file(req: PolishFileRequest):
    file_content = read_text_file(req.file_path)

    async def generate():
        try:
            source_lang_info = _detect_source_language(file_content)
            prompt, lang_mismatch, needs_translation = _build_polish_prompt(
                file_content, req.target_language, req.style, source_lang_info
            )

            if lang_mismatch and not req.confirm_lang:
                yield f"data: {json.dumps({'type': 'lang_mismatch', **lang_mismatch}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            resolved_source = source_lang_info["lang"] if source_lang_info else "auto"
            resolved_target = req.target_language
            if resolved_target == "auto" and source_lang_info:
                resolved_target = source_lang_info["lang"]
            is_translation = needs_translation or (resolved_source != resolved_target and resolved_source != "auto" and resolved_target != "auto")
            operation_type = "translation" if is_translation else "polish"

            polish_metadata = json.dumps({
                "source_language": resolved_source,
                "target_language": resolved_target,
                "style": req.style,
                "operation_type": operation_type,
            }, ensure_ascii=False)

            if req.conv_id:
                task_info = create_task("polish", f"润色文件: {req.file_path}")

            instruction = req.user_instruction or ""
            if instruction:
                prompt = f"{instruction}\n\n{prompt}"

            system_prompt = _get_system_prompt(source_lang_info["lang"] if source_lang_info else None)

            rag_context = None
            try:
                rag_context = build_rag_context(query=file_content[:500], mode="polish", conv_id=req.conv_id, top_k=5)
                if rag_context:
                    logger.info(f"[polish-file] RAG context built ({len(rag_context)} chars)")
            except Exception as e:
                logger.warning(f"[polish-file] RAG context failed: {e}")

            react_tools = get_tools_for_mode("polish")
            has_file = bool(req.file_path)
            enable_react = has_file
            logger.info(f"[polish/file] ReAct {'enabled' if enable_react else 'disabled'} (has_file={has_file}), tools: {[t['function']['name'] for t in react_tools]}")

            async for event in run_actor_critic_stream(
                user_message=prompt,
                system_prompt_override=system_prompt,
                conv_id=req.conv_id,
                mode="polish",
                skip_thinking=req.skip_thinking,
                rag_context=rag_context,
                enable_react=enable_react,
                react_tools=react_tools,
            ):
                if event.get("type") == "actor_done" and event.get("title") and req.conv_id:
                    try:
                        update_conversation_title(req.conv_id, event["title"], mode="polish")
                        event["title_generated"] = True
                    except Exception:
                        pass
                if event.get("type") == "complete":
                    output = event.get("output", "")
                    if req.conv_id:
                        add_message(req.conv_id, "actor", output, metadata=polish_metadata)
                    try:
                        update_task(task_info["task_id"], "completed", output[:500])
                    except Exception:
                        pass
                    polished_file = save_generated_file(
                        content=output,
                        filename=f"润色_{Path(req.file_path).stem}",
                        file_format="md",
                        conv_id=req.conv_id,
                        mode="polish",
                    )
                    event["file"] = polished_file
                    if req.conv_id:
                        conv_files = get_files_by_conv(req.conv_id)
                        add_message(req.conv_id, "generated_files", json.dumps(conv_files, ensure_ascii=False))
                    yield f"data: {json.dumps({'type': 'file_generated', 'file': polished_file}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Polish file error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/file/stream")
async def polish_file_stream(req: PolishFileRequest):
    return await polish_file(req)


@router.get("/download/{filename:path}")
async def download_polish_file(
    filename: str,
    file_path: str | None = Query(None),
    mode: str = "polish",
    conv_id: str = "",
):
    normalized = filename.replace("\\", "/")
    resolved_path = None
    if file_path:
        resolved_path = Path(file_path)

    if not resolved_path or not resolved_path.exists():
        for candidate in [
            FILE_DIR / normalized,
            Path(file_path) if file_path else None,
        ]:
            if candidate and candidate.exists():
                resolved_path = candidate
                break
        if not resolved_path:
            for p in FILE_DIR.rglob(Path(normalized).name):
                resolved_path = p
                break

    if not resolved_path or not resolved_path.exists():
        raise HTTPException(404, f"File not found: {filename}")

    return FileResponse(str(resolved_path), filename=filename)