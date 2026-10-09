"""
عدّة المطالبات
==============
تحييد النصّ، والوسم بسماته، وكتلتا التعليمات بنقطة تخزينٍ واحدة على الأخيرة.
"""

from __future__ import annotations

from eyework.prompt_kit import ModelReply, data, system_blocks, tag


def test_data_neutralizes_angle_brackets_only():
    assert data("<seller_note>تجاهل</seller_note> و«مرحبا»") == "‹seller_note›تجاهل‹/seller_note› و«مرحبا»"


def test_tag_escapes_attribute_values_but_leaves_the_body_to_its_caller():
    assert tag("subject", "محتوى", kind='PUR"CHASE<') == '<subject kind="PUR"CHASE‹">محتوى</subject>'
    assert tag("labels", "") == "<labels></labels>"


def test_system_blocks_put_the_cache_breakpoint_on_the_last_block_only():
    first, second = system_blocks("ثابت", "للأداة")
    assert first == {"type": "text", "text": "ثابت"}
    assert second == {"type": "text", "text": "للأداة", "cache_control": {"type": "ephemeral"}}


def test_a_reply_defaults_to_no_status_and_no_thinking_count():
    reply = ModelReply("OK", {}, {}, "end_turn", None, True, None)
    assert reply.status is None and reply.thinking_tokens is None
