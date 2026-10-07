"""
فحصٌ يدوي قبل الإطلاق — استدعاءٌ حقيقي واحد
==========================================
يمرّ صورةً محلّية بمسار الإنتاج نفسه (التنظيف ثم الكاتب الحقيقي) ويطبع
النتيجة. لا يعمل في CI ولا يلمس القاعدة، ويكلّف استدعاءً واحداً.

    EYEWORK_ANTHROPIC_API_KEY=… python -m eyework.scripts.copy_smoke صورة.jpg

يُستعمل للتحقّق من أن المفتاح ومساحة العمل والنموذج والبديل من جهة الخادم
تعمل معاً، ولقراءة نصٍّ حقيقي قبل أن يقرأه مستخدم.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from eyework.copywriter import AnthropicCopywriter
from eyework.images import ImageRejected, process
from eyework.prompt import CopyRequest


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("الاستخدام: python -m eyework.scripts.copy_smoke <صورة>", file=sys.stderr)
        return 2
    key = os.environ.get("EYEWORK_ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("EYEWORK_ANTHROPIC_API_KEY غير مضبوط", file=sys.stderr)
        return 2
    try:
        image = process(Path(argv[0]).read_bytes())
    except ImageRejected as exc:
        print(f"رُفضت الصورة: {exc.code}", file=sys.stderr)
        return 1
    outcome = AnthropicCopywriter(key).write(CopyRequest(jpeg=image.jpeg))
    print(f"النتيجة: {outcome.outcome}")
    print(f"النموذج: {outcome.served_model}   الطلب: {outcome.request_id}")
    print(f"الرموز: {outcome.input_tokens} داخل / {outcome.output_tokens} خارج")
    if outcome.outcome == "OK":
        print(f"\n{outcome.title}\n\n{outcome.description}")
    if outcome.note:
        print(f"\nسيمبول: {outcome.note}")
        if outcome.warnings:
            print(f"\nتنبيهات: {', '.join(w.value for w in outcome.warnings)}")
    elif outcome.reason:
        print(f"السبب: {outcome.reason}")
    return 0 if outcome.outcome in ("OK", "UNUSABLE_PHOTO") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
