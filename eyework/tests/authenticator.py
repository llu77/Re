"""
جهازٌ مصطنع لمفاتيح المرور — للاختبارات وحدها
===============================================
يفعل ما يفعله جهازٌ حقيقي وراء `navigator.credentials.create` و`get`: يولّد
زوج مفاتيح P-256، ويبني clientDataJSON وauthenticatorData، ويوقّع، ويُرجع
الردّ بالشكل الذي ترسله الواجهة (base64url بلا حشو). بلا جهازٍ ولا متصفّح؛
والخادم يتحقّق منه بالمكتبة نفسها التي يتحقّق بها من iPhone.

كل ما يمكن أن يخطئ فيه جهازٌ أو يزوّره مهاجمٌ معامِلٌ هنا: الأصل، ومعرّف
الطرف، والعلَمان، والعدّاد، والتوقيع، ومعرّف المستخدم. ولا تستورده إلا
الاختبارات (اختبارٌ معماري يفرض ذلك).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import struct
from dataclasses import dataclass, field

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

#: علَما الحضور والتحقّق، وعلَم «بيانات مفتاحٍ مرفقة» عند الإنشاء.
UP, UV, AT = 0x01, 0x04, 0x40


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass
class SoftwareAuthenticator:
    """مفتاح مرورٍ واحد في الذاكرة. `counting=True` ⇒ عدّادٌ يزيد مع كل توقيع."""

    origin: str
    counting: bool = False
    sign_count: int = 0
    credential_id: bytes = field(default_factory=lambda: secrets.token_bytes(16))
    private_key: ec.EllipticCurvePrivateKey = field(default_factory=lambda: ec.generate_private_key(ec.SECP256R1()))
    #: يحفظه الجهاز من خيارات الإنشاء ويعيده مع كل توقيع.
    user_handle: bytes | None = None

    @property
    def rp_id(self) -> str:
        return self.origin.split("://", 1)[1].split(":", 1)[0]

    def _cose_key(self) -> bytes:
        numbers = self.private_key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"),
                            -3: numbers.y.to_bytes(32, "big")})

    def _client_data(self, kind: str, challenge: str, origin: str | None, cross_origin: bool) -> bytes:
        return json.dumps({"type": kind, "challenge": challenge, "origin": origin or self.origin,
                           "crossOrigin": cross_origin}, separators=(",", ":")).encode()

    def _next_count(self) -> int:
        if self.counting:
            self.sign_count += 1
        return self.sign_count

    def create(self, options: dict, *, origin: str | None = None, rp_id: str | None = None,
               flags: int = UP | UV, kind: str = "webauthn.create", challenge: str | None = None,
               cross_origin: bool = False, transports: tuple[str, ...] = ("hybrid", "internal")) -> dict:
        """ردّ `credentials.create` على خيارات الخادم، كما ترسله الواجهة."""
        self.user_handle = unb64(options["user"]["id"])
        client_data = self._client_data(kind, challenge or options["challenge"], origin, cross_origin)
        auth_data = (
            hashlib.sha256((rp_id or self.rp_id).encode()).digest()
            + bytes([flags | AT])
            + struct.pack(">I", self.sign_count)
            + bytes(16)
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + self._cose_key()
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "response": {
                "clientDataJSON": b64(client_data),
                "attestationObject": b64(attestation),
                "transports": list(transports),
            },
        }

    def get(self, options: dict, *, origin: str | None = None, rp_id: str | None = None,
            flags: int = UP | UV, kind: str = "webauthn.get", challenge: str | None = None,
            cross_origin: bool = False, sign_count: int | None = None, user_handle: bytes | None = None,
            corrupt_signature: bool = False) -> dict:
        """ردّ `credentials.get` على خيارات الخادم. `sign_count` يفرض عدّاداً بعينه."""
        client_data = self._client_data(kind, challenge or options["challenge"], origin, cross_origin)
        count = self._next_count() if sign_count is None else sign_count
        auth_data = (
            hashlib.sha256((rp_id or self.rp_id).encode()).digest()
            + bytes([flags])
            + struct.pack(">I", count)
        )
        signature = self.private_key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        if corrupt_signature:
            signature = signature[:-1] + bytes([signature[-1] ^ 0x01])
        handle = self.user_handle if user_handle is None else user_handle
        response = {
            "clientDataJSON": b64(client_data),
            "authenticatorData": b64(auth_data),
            "signature": b64(signature),
        }
        if handle is not None:
            response["userHandle"] = b64(handle)
        return {
            "id": b64(self.credential_id),
            "rawId": b64(self.credential_id),
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "response": response,
        }
